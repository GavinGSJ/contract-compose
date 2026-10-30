# -*- coding: utf-8 -*-
"""
合同组装器：按 配方 + 选项库 + 变量 把原子组装成 Word 合同。

各步骤所在模块：
    library.py      读取内容库（原子、配方、变量字典、选项库、付款条款库、预存库）
    options.py      选项变量取哪种写法
    payment.py      付款节点与单据
    values.py       派生变量（价款、技术协议）、替换 {{变量}} / {{选项:…}}
    annexes.py      合同附件：编号、有/无、引用
    docx_writer.py  写 Word（样式段落、编号、块、表格、目录）
    本文件          条款编号、不适用标注、整体组装流程（第一部分条款 + 第二部分附件）

命令行用法见 cli.py。
"""
import os, re

from . import paths, annexes
from .constants import LABEL_MISSING, LABEL_ANNOTATE
from .library import load_library
from .options import choose
from .values import derive_values, expand_options, resolve_values
from .money import parse_amount, fmt_money
from .docx_writer import Writer, fill_xml


def numbering(atoms, order, start=1):
    """按顺序计算条款号：章 N、条款 N.M、子条款 N.M.K → {原子ID: 编号}"""
    refs = {}; ch = start - 1; c1 = c2 = 0
    for aid in order:
        lv = atoms[aid]['meta']['层级']
        if lv == '章': ch += 1; c1 = 0; refs[aid] = str(ch)
        elif lv == '条款': c1 += 1; c2 = 0; refs[aid] = f'{ch}.{c1}'
        else: c2 += 1; refs[aid] = f'{ch}.{c1}.{c2}'
    return refs


# 段落级条件：行首写 <仅当 选项名=取值>，选项不符时该段保留并在开头标注不适用（如设备类合同才适用的段落）
COND = re.compile(r'^<(仅当|不出现于) ([^=>]+)=([^>]+)> ?')   # <仅当 选项=值>：不符时标注不适用；<不出现于 选项=值>：相符时整段不出现；值可写“甲|乙”表示任一


def split_conditions(line):
    """行首的段落条件（可连写多个）→ ([(种类, 选项名, 取值)], 去掉条件后的行)"""
    conds = []
    while True:
        m = COND.match(line)
        if not m:
            return conds, line
        conds.append((m.group(1), m.group(2).strip(), m.group(3).strip()))
        line = line[m.end():]
NA_LINE = '\u0004'                                        # 内部标记：不适用的段落（其中的“N/A%”写成“N/A”）
LEAD = re.compile(r'^(### |## |# |  - |  \+ |- |\+ |<顶格> |<居中> |    |  )?')


GOODS_COLS = ['产品名称', '规格型号', '数量', '单位', '重量', '单价', '总金额', '备注']       # 货物明细的列（重量为可选列）


def goods_rows(rows):
    """多行货物表：[{产品名称, 规格型号, 数量, 单位, 重量, 单价, 总金额, 备注}] → (表格行, 总金额合计)。
    总金额未填时按 单价 × 数量 计算（数量未填按 1）；数量、重量按填写的原样显示"""
    out, ta = [], 0
    for i, r in enumerate(rows or [], 1):
        price, qty, amt = parse_amount(r.get('单价')), parse_amount(r.get('数量')), parse_amount(r.get('总金额'))
        if amt is None and price is not None:
            amt = price * (qty if qty is not None else 1)
        ta += amt or 0
        row = {'行.序号': str(i), '行.单价': fmt_money(price, '') if price is not None else '',
               '行.总金额': fmt_money(amt, '') if amt is not None else ''}
        for c in ('产品名称', '规格型号', '数量', '单位', '重量', '备注'):
            row['行.' + c] = str(r.get(c) or '').strip()
        out.append(row)
    return out, ta


def matches(chosen, want):
    """选项取值是否符合条件：want 可以是单个值、“甲|乙”（任一）或列表"""
    wants = want if isinstance(want, (list, tuple)) else str(want).split('|')
    return chosen in [str(w).strip() for w in wants]


def build(cfg, regress=False, keep=None, mark_vars=False):
    """组装一份合同。
    cfg：合同配置（合同类型、买方主体、变量、选项、条件、不适用、附件）；合同类型为空时取第一个类型
    regress：用母本值/默认值组装（与母本比对）；mark_vars：变量标注版（所有变量黄色标出变量名）
    返回 (doc, used 选用的写法, missing 未填变量, order 原子顺序, shown 标注不适用的原子)"""
    lib = load_library(cfg.get('合同类型'))
    atoms, opts, V, recipe, entities = lib.atoms, lib.opts, lib.V, lib.recipe, lib.entities
    settings = lib.settings
    label = LABEL_ANNOTATE if mark_vars else LABEL_MISSING
    values = dict(cfg.get('变量') or {})
    ent = cfg.get('买方主体') or (next(iter(entities)) if entities else None)
    if ent:
        if ent not in entities:
            raise SystemExit(f'预存库“买方主体”中没有“{ent}”，可选：{list(entities)}')
        for k, v in entities[ent].items(): values.setdefault(k, v)
    proj = lib.projects.get(str(values.get('项目编号', '')).strip().upper()) or {}      # 预存库“项目信息”：填了项目编号即带入项目名称、业主、设施等
    for k in lib.project_vars:
        if proj.get(k) not in (None, ''): values.setdefault(k, proj[k])
    if settings['项目附件字段']:                          # 各项目在附件库之后的附加附件（预存库中每行“中文名 | 英文名”）
        annexes.add_extra(lib, 'ANX-P', annexes.parse_extra(proj.get(settings['项目附件字段'])))
    annexes.rename(lib, cfg.get('附件名称'))             # 本合同中改过名称的附件（目录、附件清单、附件标题）
    annexes.add_extra(lib, 'ANX-X', [(str(a.get('名称') or '').strip(), str(a.get('名称_en') or '').strip())    # 本合同另加的附件
                                     for a in cfg.get('自定义附件') or []])
    goods = []
    if settings.get('货物明细'):                       # 多行货物表：含税总价 = 各行总金额之和
        goods, ta = goods_rows(cfg.get('货物'))
        if goods:
            values['含税总价'] = str(ta); values['价款_合计'] = fmt_money(ta, '')
            values['价格表样式'] = ('含重量' if any(g['行.重量'] for g in goods) else '标准') \
                + ('' if any(g['行.备注'] for g in goods) else '-无备注')                # 填了重量才出现重量列；没有备注时去掉备注列
            units = {g['行.单位'] for g in goods}
            if values.get('计价单位'):                                                    # 表头已有“元/”，填了“元/船套”也只取“船套”
                values['计价单位'] = re.sub(r'^\s*元\s*/\s*', '', str(values['计价单位']))
            elif len(units) == 1 and units != {''}:                                     # 单价单位：未填时取货物明细的单位
                values['计价单位'] = units.pop()
    if regress: values = {}
    else: values.update(derive_values(values, V))
    choices = cfg.get('选项') or {}
    for name, o in opts.items():                      # 选项的预设变量：该写法带出的变量值（如 付款方案 → 各节点比例），明确给出的值优先
        if any(v.get('预设变量') for v in o['选项'].values()):
            for var, val in (o['选项'][choose(name, o, values, choices)].get('预设变量') or {}).items():
                values.setdefault(var, str(val))
    cond_used = set()
    if not regress:                                    # 配方中写了“不符时: 不出现”的条款：选项不符时整条（整章）不出现，不标注不适用
        shown_items = []
        for it in recipe['顺序']:
            wants = {k: v for k, v in (it.get('仅当选项') or {}).items() if k in opts} if it.get('不符时') == '不出现' else {}
            cond_used.update(wants)
            if all(matches(choose(k, opts[k], values, choices), v) for k, v in wants.items()):
                shown_items.append(it)
        recipe = {**recipe, '顺序': shown_items}
    conds = set(cfg.get('条件') or [])
    # 所有条款一律保留；条件不成立或列入“不适用”的条款标注不适用（付款条款除外）
    order = [it['原子'] for it in recipe['顺序'] if '原子' in it]
    na = set() if regress else {it['原子'] for it in recipe['顺序']
                                if '原子' in it and it.get('条件') and it['条件'] not in conds}
    if not regress:
        na |= set(cfg.get('不适用') or [])
        for it in recipe['顺序']:                  # 仅在某选项取某值时适用（如 仲裁细则 仅当 争议解决=仲裁）
            for k, v in (it.get('仅当选项') or {}).items():
                if k in opts:
                    cond_used.add(k)
                    if not matches(choose(k, opts[k], values, choices), v):
                        na.add(it['原子'])
    na -= set(settings['付款条款'])
    chap = {a['meta']['章']: aid for aid, a in atoms.items() if a['meta']['层级'] == '章'}
    inherit = {aid for aid in order if chap.get(atoms[aid]['meta']['章']) in na}   # 整章不适用
    refs = numbering(atoms, order, settings['编号起始'])
    ast = annexes.states(lib, values, None if regress else cfg.get('附件'))   # {附件ID: 有/无}
    anums = annexes.numbers(lib, ast)
    used, missing = {}, set()
    na_mark = settings['不适用标注']

    def conditions(text):
        """段落级条件：<仅当 名称=值> 不符时在段落开头标注不适用"""
        out = []
        for line in text.split('\n'):
            conds, line = split_conditions(line)
            hide = na_line = False
            for kind, k, v in conds:
                if k not in opts: continue
                cond_used.add(k)
                ok = matches(choose(k, opts[k], values, choices), v)
                hide |= kind == '不出现于' and ok
                na_line |= kind == '仅当' and not ok
            if hide:
                continue
            if na_line:
                lead = LEAD.match(line).group(1) or ''
                line = NA_LINE + lead + na_mark + line[len(lead):]
            out.append(line)
        return '\n'.join(out)

    def fill(text, is_na=False):
        t = annexes.replace_refs(lib, text, anums, ast)
        for _ in range(3):                             # 选项文字中还可以再用选项（如 交货期方式 中的 交货期单位）
            t = expand_options(lib, t, values, choices, used)
            if '{{选项' not in t: break
        t = annexes.replace_refs(lib, t, anums, ast)       # 选项、付款条款文字中的附件引用
        t = resolve_values(t, V, values, missing, regress, keep, is_na, mark_vars)
        t = resolve_values(t, V, values, missing, regress, keep, is_na, mark_vars)   # 计算变量中嵌套的 {{变量}}
        return re.sub(r'\{\{ref:([^}]+)\}\}', lambda m: refs[m.group(1)], t)

    def fill_e(e):
        fill_xml(e, fill, label)

    def mark(aid, t):
        if aid in na or aid in inherit:
            t = t.replace('N/A%', 'N/A')
        if aid not in na or (aid in inherit and atoms[aid]['meta']['层级'] != '章'):
            return t                                   # 整章不适用时只在章标题标注
        first, _, rest = t.partition('\n')
        m = re.match(r'(#+ |<顶格> )?(.*)', first.rstrip())
        lead, head = m.group(1) or '', m.group(2)
        first = lead + (head + na_mark if len(head) <= 80 else na_mark + head)   # 长条款文字：标注放在开头
        return first + ('\n' + rest if rest else '')

    w = Writer(os.path.join(lib.dir, settings['样式模板']), label)
    def plain(t):
        """不适用的段落（conditions 标记）：其中的“N/A%”写成“N/A”；去掉内部标记"""
        return '\n'.join(l[1:].replace('N/A%', 'N/A') if l.startswith(NA_LINE) else l for l in t.split('\n'))

    rendered = [(aid, mark(aid, plain(fill(conditions(atoms[aid]['body']), aid in na or aid in inherit)))) for aid in order]
    body_of = dict(rendered)

    def write_lines(text):
        for line in text.split('\n'):
            if not line.strip():
                continue
            m = re.fullmatch(r'\s*\{\{(table|block):([^}]+)\}\}\s*', line)
            if m:
                def tv(x):                              # 表格名中的 $变量（如 PO-SCO-$价款_计税）
                    k = x.group(1); v = V.get(k, {})
                    return str(values.get(k) or v.get('母本值') or v.get('默认值') or '')
                tid = re.sub(r'\$([\w一-鿿]+)', tv, m.group(2))
                path = os.path.join(lib.dir, paths.TABLES if m.group(1) == 'table' else paths.BLOCKS, tid + '.xml')
                if '{{行.' in open(path, encoding='utf-8').read():       # 多行货物表：按货物逐行复制
                    w.table_rows(path, goods or [{'行.序号': '1', '行.产品名称': '{{货物明细}}'}], fill_e)
                else:
                    w.block(path, fill_e)
                w.prev = 'TABLE'
            else:
                w.line(line)

    for item in recipe['顺序']:                       # 按配方顺序输出：块、目录、条款、附件列表
        if '原子' in item:
            write_lines(body_of[item['原子']])
        elif '附件列表' in item:                         # 合同末尾列出“有”的附件：附件一 廉洁承诺书
            for a in lib.annexes:
                if ast[a]:
                    w.para('合同-正文（顶格）', annexes.title(lib, a, nums=anums))
        elif '块' in item:
            w.block(os.path.join(lib.dir, paths.BLOCKS, item['块'] + '.xml'), fill_e)
        elif '目录' in item:
            heads = [(refs[aid], re.sub(r'^# ', '', t.split('\n')[0]).replace('**', ''))
                     for aid, t in rendered if atoms[aid]['meta']['层级'] == '章']
            w.toc(heads, item.get('标题', '目录'), item.get('前置行') or [], item.get('编号格式', '{n}'))
            if item.get('附加块'):
                p = os.path.join(lib.dir, paths.BLOCKS, item['附加块'] + '.xml')
                if '{{行.' in open(p, encoding='utf-8').read():       # 附件目录：块中含 {{行.英文}}、{{行.中文}} 的段落按附件逐个复制
                    w.block_rows(p, annexes.toc_rows(lib, ast, anums, na_mark), fill_e)
                else:
                    w.block(p, fill_e)
            if item.get('附件行') and lib.annexes:          # 目录中的第二部分与各附件（无的附件标注不适用）
                sec = recipe['附件']
                w.toc_lines([fill(sec['目录行'])] + [annexes.full_title(lib, a, anums) + ('' if ast[a] else na_mark)
                                                    for a in lib.annexes])

    if lib.annexes:                                    # 第二部分 合同附件：附件清单表 + 有正文且“有”的附件（没有标题时不生成第二部分）
        sec = recipe['附件']
        if sec.get('标题'):
            zh, en = sec['标题']
            w.para('合同-部分标题', zh); w.para('合同-部分标题（英文）', en)
        if sec.get('清单说明'):
            w.para('合同-正文（顶格）', fill(sec['清单说明']))
        if sec.get('清单表'):
            rows = [{'附件序号': annexes.label(lib, a, nums=anums), '附件名称': lib.annexes[a]['meta']['名称'],
                     '附件名称_en': lib.annexes[a]['meta'].get('名称_en') or '', '附件提供': annexes.checkbox(ast[a])}
                    for a in lib.annexes]
            w.table_rows(os.path.join(lib.dir, paths.TABLES, sec['清单表'] + '.xml'), rows, fill_e)
        w.plain = '合同-正文（顶格）'
        for a in lib.annexes:
            if not (ast[a] and annexes.has_body(lib, a)):
                continue
            w.heading('合同-附件标题', [annexes.full_title(lib, a, anums)],
                      page_break=bool(lib.annexes[a]['meta'].get('另起一页')))
            write_lines(fill(lib.annexes[a]['body']))
        w.plain = '合同-正文'
        used['附件'] = annexes.summary(lib, ast)
    # 页眉页脚
    for rel in w.doc.part.rels.values():
        if rel.reltype.endswith(('/header', '/footer')):
            fill_e(rel.target_part.element)
    for k in sorted(cond_used):                                # 段落条件、“仅当选项”用到的选项也写入报告（放在最后，不改变已有顺序）
        used.setdefault(k, choose(k, opts[k], values, choices))
    shown = [a for a in order if a in na and not (a in inherit and atoms[a]['meta']['层级'] != '章')]
    return w.doc, used, missing, order, shown
