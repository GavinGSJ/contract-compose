# -*- coding: utf-8 -*-
"""
合同组装器：按 配方 + 选项库 + 变量 把原子组装成 Word 合同。

各步骤所在模块：
    library.py      读取内容库（原子、配方、变量字典、选项库、付款条款库、预存库）
    options.py      选项变量取哪种写法
    payment.py      付款节点与单据
    values.py       派生变量（价款、技术协议）、替换 {{变量}} / {{选项:…}}
    docx_writer.py  写 Word（样式段落、编号、块、表格、目录）
    本文件          条款编号、不适用标注、整体组装流程

命令行用法见 cli.py。
"""
import os, re

from . import paths
from .constants import NA_MARK, NA_EXCLUDE, LABEL_MISSING, LABEL_ANNOTATE
from .library import load_library
from .options import choose
from .values import derive_values, expand_options, resolve_values
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


def build(cfg, regress=False, keep=None, mark_vars=False):
    """组装一份合同。
    cfg：合同配置（合同类型、买方主体、变量、选项、条件、不适用）
    regress：用母本值/默认值组装（与母本比对）；mark_vars：变量标注版（所有变量黄色标出变量名）
    返回 (doc, used 选用的写法, missing 未填变量, order 原子顺序, shown 标注不适用的原子)"""
    lib = load_library(cfg.get('合同类型') or 'FA')
    atoms, opts, V, recipe, entities = lib.atoms, lib.opts, lib.V, lib.recipe, lib.entities
    label = LABEL_ANNOTATE if mark_vars else LABEL_MISSING
    values = dict(cfg.get('变量') or {})
    ent = cfg.get('买方主体') or (next(iter(entities)) if entities else None)
    if ent:
        if ent not in entities:
            raise SystemExit(f'预存库“买方主体”中没有“{ent}”，可选：{list(entities)}')
        for k, v in entities[ent].items(): values.setdefault(k, v)
    if regress: values = {}
    else: values.update(derive_values(values))
    choices = cfg.get('选项') or {}
    conds = set(cfg.get('条件') or [])
    # 所有条款一律保留；条件不成立或列入“不适用”的条款标注不适用（付款条款除外）
    order = [it['原子'] for it in recipe['顺序'] if '原子' in it]
    na = set() if regress else {it['原子'] for it in recipe['顺序']
                                if '原子' in it and it.get('条件') and it['条件'] not in conds}
    if not regress:
        na |= set(cfg.get('不适用') or [])
        for it in recipe['顺序']:                  # 仅在某选项取某值时适用（如 仲裁细则 仅当 争议解决=仲裁）
            for k, v in (it.get('仅当选项') or {}).items():
                if k in opts and choose(k, opts[k], values, choices) != str(v):
                    na.add(it['原子'])
    na -= set(NA_EXCLUDE)
    chap = {a['meta']['章']: aid for aid, a in atoms.items() if a['meta']['层级'] == '章'}
    inherit = {aid for aid in order if chap.get(atoms[aid]['meta']['章']) in na}   # 整章不适用
    refs = numbering(atoms, order, recipe.get('编号起始', 1))
    used, missing = {}, set()

    def fill(text, is_na=False):
        t = expand_options(lib, text, values, choices, used)
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
        first = lead + (head + NA_MARK if len(head) <= 80 else NA_MARK + head)   # 长条款文字：标注放在开头
        return first + ('\n' + rest if rest else '')

    w = Writer(os.path.join(lib.dir, recipe['样式模板']), label)
    rendered = [(aid, mark(aid, fill(atoms[aid]['body'], aid in na or aid in inherit))) for aid in order]
    for item in recipe['顺序']:
        if '块' in item:
            w.block(os.path.join(lib.dir, paths.BLOCKS, item['块'] + '.xml'), fill_e)
        elif '目录' in item:
            heads = [(refs[aid], re.sub(r'^# ', '', t.split('\n')[0]).replace('**', ''))
                     for aid, t in rendered if atoms[aid]['meta']['层级'] == '章']
            w.toc(heads, item.get('标题', '目录CONTENT'),
                  item.get('前置行', ['第一部分 合同条款 Part I Contract Text']), item.get('编号格式', '{n}'))
            if item.get('附加块'):
                w.block(os.path.join(lib.dir, paths.BLOCKS, item['附加块'] + '.xml'), fill_e)
    for aid, text in rendered:
        for line in text.split('\n'):
            if not line.strip():
                continue
            m = re.fullmatch(r'\s*\{\{table:([^}]+)\}\}\s*', line)
            if m:
                def tv(x):                              # 表格名中的 $变量（如 PO-SCO-$价款_计税）
                    k = x.group(1); v = V.get(k, {})
                    return str(values.get(k) or v.get('母本值') or v.get('默认值') or '')
                tid = re.sub(r'\$([\w一-鿿]+)', tv, m.group(1))
                w.block(os.path.join(lib.dir, paths.TABLES, tid + '.xml'), fill_e)
                w.prev = 'TABLE'
            else:
                w.line(line)
    # 页眉页脚
    for rel in w.doc.part.rels.values():
        if rel.reltype.endswith(('/header', '/footer')):
            fill_e(rel.target_part.element)
    shown = [a for a in order if a in na and not (a in inherit and atoms[a]['meta']['层级'] != '章')]
    return w.doc, used, missing, order, shown
