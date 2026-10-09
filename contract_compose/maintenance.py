# -*- coding: utf-8 -*-
"""条款维护（表单“条款维护”页面使用，也可在命令行 / AI 中直接调用）。

    rows = items(lib, '条款')                  # 按合同顺序列出条款（附件用 '附件'）
    errors, warnings = check(lib, '条款', 'QUA-04', new_body)
    html = preview_html(lib, '条款', 'QUA-04', new_body)
    html = diff_html(old_body, new_body)
    save(lib, '条款', 'QUA-04', new_body, reason='质保期改为 24 个月')

保存时：旧文件先备份到 library/backups/<类型>/…；写入后用该类型的示例配置试生成，失败则自动还原；
成功则在 library/<类型>/修订记录.md 的“条款维护记录”中记一条，并刷新回归快照。
"""
import os, re, glob, html, difflib, datetime, shutil
import yaml

from . import paths, annexes
from .constants import MISS_L, MISS_R
from .assembler import numbering, COND
from .values import expand_options, resolve_values
from .library import list_types

KINDS = {'条款': paths.ATOMS, '附件': paths.ANNEXES}
LOG_HEAD = '## 条款维护记录'
UNUSED = '（未使用）'


# ======================= 列表与查找 =======================
def items(lib, kind):
    """[{id, no, name, level, chapter, file, body}]：条款按配方顺序（不在配方中的排在最后，编号为“（未使用）”）；附件按附件顺序"""
    rows = []
    if kind == '附件':
        nums = annexes.numbers(lib)
        for aid, a in lib.annexes.items():
            m = a['meta']
            rows.append({'id': aid, 'no': annexes.label(lib, aid, nums=nums), 'name': m['名称'], 'level': m.get('类型', '正文'),
                         'chapter': '附件', 'file': a['file'], 'body': a['body']})
        return rows
    order = [it['原子'] for it in lib.recipe['顺序'] if '原子' in it]
    refs = numbering(lib.atoms, order, lib.settings['编号起始'])
    for aid in order + sorted(a for a in lib.atoms if a not in refs):
        a = lib.atoms[aid]; m = a['meta']
        rows.append({'id': aid, 'no': refs.get(aid, UNUSED), 'name': m['名称'], 'level': m['层级'],
                     'chapter': m.get('章', ''), 'file': a['file'], 'body': a['body']})
    return rows


def search(rows, keyword):
    """按编号、ID、名称、正文查找（不区分大小写）"""
    k = (keyword or '').strip().lower()
    if not k:
        return rows
    return [r for r in rows if any(k in str(r[f]).lower() for f in ('no', 'id', 'name', 'body'))]


def chapters(rows):
    """[(章编号, 章名称, [该章的行])]，供页面按章浏览"""
    out = []
    for r in rows:
        if r['level'] == '章' or not out or (r['no'] == UNUSED and out[-1][0] != UNUSED):
            key = UNUSED if r['no'] == UNUSED else r['no']
            out.append((key, '未使用的条款' if key == UNUSED else r['name'], []))
        out[-1][2].append(r)
    return out


# ======================= 文件读写 =======================
def path_of(lib, kind, aid):
    src = lib.annexes if kind == '附件' else lib.atoms
    return os.path.join(lib.dir, KINDS[kind], src[aid]['file'])


def split_file(text):
    """'---头信息---正文' → (头信息, 正文)；头信息原样保留"""
    _, fm, body = text.split('---', 2)
    return fm, body


def join_file(fm, body):
    body = body.replace('\r\n', '\n').strip('\n')
    return '---' + fm + '---\n' + ('\n' + body + '\n' if body else '')


def set_name(fm, name):
    line = yaml.safe_dump({'名称': name}, allow_unicode=True, width=10000).strip()
    return re.sub(r'(?m)^名称:.*$', lambda m: line, fm, count=1)


# ======================= 检查 =======================
PH = re.compile(r'\{\{([^}]+)\}\}')


def check(lib, kind, aid, body):
    """返回 (错误, 提醒)：错误时不能保存"""
    errors, warns = [], []
    body = body.replace('\r\n', '\n')
    src = lib.annexes if kind == '附件' else lib.atoms
    if body.count('{{') != body.count('}}'):
        errors.append('“{{”与“}}”数量不一致，请检查占位符是否写完整')
    for k in PH.findall(body):
        k = k.strip()
        if k.startswith('ref:'):
            if k[4:] not in lib.atoms: errors.append(f'引用的条款 {k[4:]} 不存在')
        elif k.startswith(('table:', 'block:')):
            sub = paths.TABLES if k.startswith('table:') else paths.BLOCKS
            pat = re.sub(r'\$[\w一-鿿]+', '*', k.split(':', 1)[1])
            if not glob.glob(os.path.join(lib.dir, sub, pat + '.xml')):
                errors.append(f'{sub}/ 中找不到 {k.split(":", 1)[1]}.xml')
        elif k.startswith(('附件:', '附件_en:', '附件号:')):
            if k.split(':', 1)[1] not in lib.annexes: errors.append(f'引用的附件 {k.split(":", 1)[1]} 不存在')
        elif k.startswith(('选项:', '选项列表:')):
            n = k.split(':', 1)[1]; n = n[:-3] if n.endswith('_en') else n
            if n not in lib.opts: errors.append(f'选项库中没有“{n}”')
        elif k.startswith(('英文数字:', '中文数字:')):
            if k.split(':', 1)[1] not in lib.V: errors.append(f'变量“{k.split(":", 1)[1]}”不在变量字典中')
        elif k not in lib.V and k != '本节点比例':
            errors.append(f'变量“{k}”不在变量字典中（新增变量请先在变量字典中登记）')
    for i, line in enumerate(body.split('\n'), 1):
        m = COND.match(line)                           # 段落条件 <仅当 选项名=取值>
        if m:
            o = lib.opts.get(m.group(1).strip())
            if o is None: errors.append(f'第 {i} 行：选项库中没有“{m.group(1).strip()}”')
            elif m.group(2).strip() not in o['选项']: errors.append(f'第 {i} 行：“{m.group(1).strip()}”没有取值“{m.group(2).strip()}”')
        if line.count('**') % 2:
            warns.append(f'第 {i} 行的“**”（加粗）没有成对')
        if line.count('<u>') != line.count('</u>'):
            warns.append(f'第 {i} 行的“<u>”（下划线）没有成对')
    old = src[aid]['body'] if aid in src else body
    lead = lambda t: (re.match(r'(#+ |<顶格> |- |\+ )?', COND.sub('', next((x for x in t.split('\n') if x.strip()), ''))).group(1) or '')
    if kind == '条款' and lead(old) != lead(body):
        warns.append(f'首行标记由“{lead(old).strip() or "无"}”变为“{lead(body).strip() or "无"}”，条款的层级 / 编号会变化')
    if not body.strip() and (kind == '条款' or (aid in lib.annexes and annexes.has_body(lib, aid))):
        errors.append('正文不能为空')
    return errors, warns


# ======================= 预览与对比 =======================
VAR_L, VAR_R = '\u0005', '\u0006'                 # 预览中变量值的标记


def preview_text(lib, kind, aid, body):
    """按默认值填入变量、引用换成编号；变量值用 VAR 标记包住，未填的用 MISS 标记"""
    order = [it['原子'] for it in lib.recipe['顺序'] if '原子' in it]
    refs = numbering(lib.atoms, order, lib.settings['编号起始'])
    t = annexes.replace_refs(lib, body.replace('\r\n', '\n'))
    t = expand_options(lib, t, {}, {}, {})
    t = re.sub(r'\{\{ref:([^}]+)\}\}', lambda m: refs.get(m.group(1), MISS_L + m.group(1) + MISS_R), t)
    t = re.sub(r'\{\{(table|block):([^}]+)\}\}', lambda m: f'［{"表格" if m.group(1) == "table" else "块"} {m.group(2)}］', t)

    def var(m):
        k = m.group(1)
        v = resolve_values('{{%s}}' % k, lib.V, {}, set())
        v = resolve_values(v, lib.V, {}, set())
        return v if MISS_L in v else VAR_L + v + VAR_R
    return PH.sub(var, t)


def _inline(s):
    s = html.escape(s)
    s = re.sub(r'\*\*(.+?)\*\*', r'<b>\1</b>', s)
    s = s.replace('&lt;u&gt;', '<u>').replace('&lt;/u&gt;', '</u>').replace('&lt;br&gt;', '<br>').replace('\\*', '*')
    s = re.sub(MISS_L + '([^' + MISS_R + ']*)' + MISS_R, r'<mark style="background:#fff3a3">【\1】</mark>', s)
    s = re.sub(VAR_L + '([^' + VAR_R + ']*)' + VAR_R, r'<span style="background:#dbeafe">\1</span>', s)
    return s


def preview_html(lib, kind, aid, body):
    """简化的版面预览（样式近似 Word）：蓝底为变量的默认值，黄底为未填变量"""
    rows = {r['id']: r for r in items(lib, kind)}
    no = rows[aid]['no'] if aid in rows else ''
    out, n1, n2, prev = [], 0, 0, 'P'
    letters = 'abcdefghijklmnopqrstuvwxyz'
    for line in preview_text(lib, kind, aid, body).split('\n'):
        if not line.strip():
            continue
        m = COND.match(line)                           # 段落条件：去掉前缀，在段落开头灰字注明
        cond = f'<span style="color:#888">〔仅当{html.escape(m.group(1).strip())}={html.escape(m.group(2).strip())}〕</span>' if m else ''
        line = line[m.end():] if m else line
        if line.strip() == '<分页>':
            out.append('<hr style="border-top:1px dashed #999">'); continue
        ind, label, style = (0 if kind == '附件' else 2), '', ''
        if line.startswith(('# ', '## ', '### ')):
            mark, text = line.split(' ', 1)
            label = '' if no == UNUSED else no + ' '
            style = 'font-weight:700;' + ('font-size:1.1em;' if mark == '#' else '')
            prev = 'H'
        elif line.startswith(('- ', '+ ')):
            n1 = n1 + 1 if prev in ('L1', 'L2', 'CONT') else 1
            text, ind, prev = line[2:], 2, 'L1'
            label = f'{letters[(n1 - 1) % 26]}) ' if line[0] == '-' else f'{n1}. '
        elif line.startswith(('  - ', '  + ')):
            n2 = n2 + 1 if prev in ('L2', 'CONT2') else 1
            text, ind, prev = line[4:], 4, 'L2'
            label = f'{n2}) ' if line[2] == '-' else f'{letters[(n2 - 1) % 26]}) '
        elif line.startswith('    '):
            text, ind, prev = line.strip(), 6, 'CONT2'
        elif line.startswith('  '):
            text, ind = line.strip(), 4 if prev in ('L2', 'CONT2') else 3
            prev = 'CONT2' if prev in ('L2', 'CONT2') else 'CONT'
        elif line.startswith('<居中> '):
            text, style, prev = line[5:], 'text-align:center;', 'P'
        elif line.startswith('<顶格> '):
            text, ind, prev = line[5:], 0, 'P'
        else:
            text, prev = line, 'P'
        out.append(f'<p style="margin:0 0 6px {ind}em;{style}">{cond}{html.escape(label)}{_inline(text)}</p>')
    return '\n'.join(out)


def diff_html(old, new):
    """逐段对比：删除的文字红底删除线，新增的文字绿底"""
    a = [x for x in old.replace('\r\n', '\n').split('\n') if x.strip()]
    b = [x for x in new.replace('\r\n', '\n').split('\n') if x.strip()]
    out = []
    for op, i1, i2, j1, j2 in difflib.SequenceMatcher(None, a, b, autojunk=False).get_opcodes():
        if op == 'equal':
            continue
        if op == 'replace' and i2 - i1 == j2 - j1:
            for x, y in zip(a[i1:i2], b[j1:j2]):
                out.append(_char_diff(x, y))
            continue
        for x in a[i1:i2]: out.append(f'<p><del style="background:#fde2e2">{html.escape(x)}</del></p>')
        for y in b[j1:j2]: out.append(f'<p><ins style="background:#dcfce7;text-decoration:none">{html.escape(y)}</ins></p>')
    return '\n'.join(out)


TOKEN = re.compile(r'[A-Za-z0-9.%]+|\{\{[^}]*\}\}|\s+|.')     # 数字 / 英文词 / 占位符整体比较，汉字逐字


def _char_diff(x, y):
    tx, ty = TOKEN.findall(x), TOKEN.findall(y)
    s = []
    for op, i1, i2, j1, j2 in difflib.SequenceMatcher(None, tx, ty, autojunk=False).get_opcodes():
        a, b = ''.join(tx[i1:i2]), ''.join(ty[j1:j2])
        if op == 'equal': s.append(html.escape(a)); continue
        if a: s.append(f'<del style="background:#fde2e2">{html.escape(a)}</del>')
        if b: s.append(f'<ins style="background:#dcfce7;text-decoration:none">{html.escape(b)}</ins>')
    return '<p>' + ''.join(s) + '</p>'


# ======================= 保存、历史、恢复 =======================
def backup_dir(lib, kind):
    return os.path.join(paths.CONTENT_BACKUPS, lib.ctype, KINDS[kind])


def history(lib, kind, aid):
    """该条款 / 附件的备份：[(时间, 路径)]，新的在前"""
    out = []
    for p in glob.glob(os.path.join(backup_dir(lib, kind), f'{aid}_*.md')):
        m = re.search(r'_(\d{8}-\d{6})\.md$', p)
        if m:
            out.append((datetime.datetime.strptime(m.group(1), '%Y%m%d-%H%M%S').strftime('%Y-%m-%d %H:%M:%S'), p))
    return sorted(out, reverse=True)


def read_backup(p):
    fm, body = split_file(open(p, encoding='utf-8').read())
    m = re.search(r'(?m)^名称:\s*(.*)$', fm)
    return (yaml.safe_load(m.group(1)) if m else ''), body.strip('\n')


def log_change(lib, line):
    p = os.path.join(lib.dir, '修订记录.md')
    s = open(p, encoding='utf-8').read() if os.path.exists(p) else f'# {lib.ctype} 修订记录\n'
    if LOG_HEAD not in s:
        s = s.rstrip('\n') + f'\n\n{LOG_HEAD}\n\n通过表单“条款维护”页面保存的修改（自动记录，新的在后）。\n'
    s = s.rstrip('\n') + '\n' + line + '\n'
    open(p, 'w', encoding='utf-8').write(s)


def verify(ctypes):
    """用这些类型的全部示例 / 测试配置和母本回归试生成；返回错误信息（无错误返回 None）"""
    from .snapshots import cases, build_case
    ctypes = [ctypes] if isinstance(ctypes, str) else list(ctypes)
    for name, k, arg in cases():
        t = (yaml.safe_load(open(arg, encoding='utf-8')) or {}).get('合同类型') if k == 'config' else arg
        if (t or list_types()[0]) not in ctypes:
            continue
        try:
            build_case(k, arg)
        except SystemExit as e:
            return f'{name}：{e}'
        except Exception as e:                          # noqa: BLE001  保存失败时给出原因
            return f'{name}：{type(e).__name__}: {e}'
    return None


def transaction(lib, writes, log_line, update_snapshots=True):
    """一次修改：writes = {路径: 新内容（None 为删除）}。写入后试生成，失败则全部还原；成功则记修订记录、更新快照。
    改到共用库（library/common）时，所有合同类型都要试生成。返回 {'ok', 'message', 'snapshots'}"""
    olds = {p: (open(p, encoding='utf-8').read() if os.path.exists(p) else None) for p in writes}
    for p, text in writes.items():
        if text is None:
            if os.path.exists(p): os.remove(p)
        else:
            os.makedirs(os.path.dirname(p), exist_ok=True)
            open(p, 'w', encoding='utf-8').write(text)
    common = any(os.path.abspath(p).startswith(os.path.abspath(paths.COMMON)) for p in writes)
    err = verify(list_types() if common else lib.ctype)
    if err:
        for p, text in olds.items():
            if text is None:
                if os.path.exists(p): os.remove(p)
            else:
                open(p, 'w', encoding='utf-8').write(text)
        return {'ok': False, 'message': f'修改后试生成失败，已还原：{err}'}
    log_change(lib, log_line)
    changed = []
    if update_snapshots:
        from .snapshots import update
        changed = update()
    return {'ok': True, 'message': '已保存', 'snapshots': changed}


def backup_item(lib, kind, aid, now=None):
    """条款 / 附件文件备份（历史版本），返回备份路径"""
    now = now or datetime.datetime.now()
    os.makedirs(backup_dir(lib, kind), exist_ok=True)
    bak = os.path.join(backup_dir(lib, kind), f'{aid}_{now:%Y%m%d-%H%M%S}.md')
    shutil.copy2(path_of(lib, kind, aid), bak)
    return bak


def stamp(now=None):
    return f'{(now or datetime.datetime.now()):%Y-%m-%d %H:%M}'


def save(lib, kind, aid, body, name=None, reason='', update_snapshots=True, now=None):
    """保存条款 / 附件正文（及名称）。返回 {'ok', 'message', 'backup', 'snapshots'}"""
    errors, _ = check(lib, kind, aid, body)
    if errors:
        return {'ok': False, 'message': '；'.join(errors)}
    p = path_of(lib, kind, aid)
    old_text = open(p, encoding='utf-8').read()
    fm, old_body = split_file(old_text)
    old_name = (lib.annexes if kind == '附件' else lib.atoms)[aid]['meta']['名称']
    new_fm = set_name(fm, name) if name and name != old_name else fm
    new_text = join_file(new_fm, body)
    if new_text == old_text:
        return {'ok': False, 'message': '内容没有变化'}
    bak = backup_item(lib, kind, aid, now)
    no = next((r['no'] for r in items(lib, kind) if r['id'] == aid), '')
    extra = f'；名称“{old_name}”改为“{name}”' if name and name != old_name else ''
    res = transaction(lib, {p: new_text}, f'- {stamp(now)}　{no} {old_name}（{aid}）：{reason.strip() or "（未填写原因）"}{extra}',
                      update_snapshots)
    if not res['ok']:
        os.remove(bak)
    return {**res, 'backup': bak}


def restore(lib, kind, aid, backup_path, reason=''):
    name, body = read_backup(backup_path)
    when = re.search(r'_(\d{8}-\d{6})\.md$', backup_path).group(1)
    return save(lib, kind, aid, body, name=name or None, reason=reason or f'恢复到 {when} 的版本')
