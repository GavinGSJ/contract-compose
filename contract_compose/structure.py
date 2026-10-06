# -*- coding: utf-8 -*-
"""结构维护：条款的新增 / 移除 / 恢复 / 移动，附件的新增 / 移除 / 排序 / 默认有无。

只改 recipe.yaml 中相关的行（保留注释）和条款 / 附件文件；每次操作都经过 maintenance.transaction：
试生成失败自动还原，成功则记入修订记录并更新快照。条款号、附件号、目录和引用随顺序自动更新。

条款的层级：章 → 条款 → 子条款。“单元”指一个条款连同它下面的子条款（章则连同整章）。
移除只是从配方中去掉，文件保留（条款维护页面中显示为“未使用”，可随时恢复）。
"""
import os, re, glob

from . import paths, annexes
from .maintenance import transaction, join_file, split_file, check, path_of, backup_item, stamp

LEVELS = ['章', '条款', '子条款']
MARK = {'章': '# ', '条款': '## ', '子条款': '### '}


def ok(msg):
    return {'ok': True, 'message': msg}


def fail(msg):
    return {'ok': False, 'message': msg}


# ======================= 配方中的条款顺序 =======================
def recipe_path(lib):
    return os.path.join(lib.dir, paths.RECIPE)


def atom_region(lines):
    """配方“顺序”中条款项所在的行：(起始行, 结束行, {原子ID: [行]})；每项包括其下缩进的行（如“条件”）和注释"""
    blocks, first, end, cur = {}, None, None, None
    in_seq = False
    for i, line in enumerate(lines):
        if re.match(r'^顺序:\s*$', line):
            in_seq = True; continue
        if not in_seq:
            continue
        if re.match(r'^[^\s#-]', line):                    # 下一个顶层键：“顺序”结束
            break
        m = re.match(r'^- 原子:\s*(\S+)', line)
        if m:
            cur = m.group(1); blocks[cur] = [line]
            first = i if first is None else first
            end = i + 1
        elif line.startswith('- '):
            cur = None
        elif cur is not None and line.strip():
            blocks[cur].append(line); end = i + 1
    return first, end, blocks


def write_order(lib, order, new_blocks=None):
    """按新的条款顺序重写配方中的条款项，返回新文本"""
    lines = open(recipe_path(lib), encoding='utf-8').read().split('\n')
    first, end, blocks = atom_region(lines)
    blocks.update(new_blocks or {})
    out = lines[:first]
    for a in order:
        out += blocks.get(a) or [f'- 原子: {a}']
    return '\n'.join(out + lines[end:])


def current_order(lib):
    return [it['原子'] for it in lib.recipe['顺序'] if '原子' in it]


def level(lib, aid):
    return lib.atoms[aid]['meta']['层级']


def unit_end(lib, order, i):
    """order[i] 这一单元结束的位置（不含）"""
    lv = LEVELS.index(level(lib, order[i])); j = i + 1
    while j < len(order) and LEVELS.index(level(lib, order[j])) > lv:
        j += 1
    return j


def validate(lib, order, extra_levels=None):
    """顺序是否合法：条款前要有章，子条款前要有条款（同一章内）"""
    lv = lambda a: (extra_levels or {}).get(a) or level(lib, a)
    chapter = clause = False
    for a in order:
        if lv(a) == '章':
            chapter, clause = True, False
        elif lv(a) == '条款':
            if not chapter: return f'{a} 前面没有章'
            clause = True
        elif not clause:
            return f'子条款 {a} 必须放在条款之后'
    return None


def chapter_of(lib, order, i, extra=None):
    """order[i] 所在章的“章”名称"""
    for a in reversed(order[:i + 1]):
        m = (extra or {}).get(a) or lib.atoms[a]['meta']
        if m['层级'] == '章':
            return m['章']
    return ''


def insert_pos(lib, order, after, lv, extra=None):
    """在 after 之后插入层级为 lv 的条目时的位置"""
    lvl = lambda a: (extra or {}).get(a, {}).get('层级') or level(lib, a)
    i = order.index(after)
    if lv == '章':                                         # 放在 after 所在章的末尾
        j = i + 1
        while j < len(order) and lvl(order[j]) != '章': j += 1
        return j
    if lv == '条款':
        if lvl(after) == '章': return i + 1
        j = i + 1
        while j < len(order) and lvl(order[j]) == '子条款': j += 1
        return j
    if lvl(after) == '章':
        raise ValueError('子条款不能直接放在章标题之后，请选一个条款')
    return i + 1


def fix_chapters(lib, order, moved):
    """移动到其他章的条款：更新文件头信息中的“章”。返回 {路径: 新内容}"""
    writes = {}
    for a in moved:
        m = lib.atoms[a]['meta']
        if m['层级'] == '章':
            continue
        ch = chapter_of(lib, order, order.index(a))
        if ch and ch != m.get('章'):
            p = path_of(lib, '条款', a)
            fm, body = split_file(open(p, encoding='utf-8').read())
            fm = re.sub(r'(?m)^章:.*$', f'章: {ch}', fm, count=1)
            writes[p] = join_file(fm, body)
    return writes


def label_of(lib, order, aid, extra=None):
    from .assembler import numbering
    atoms = dict(lib.atoms)
    for k, m in (extra or {}).items():
        atoms[k] = {'meta': m}
    return numbering(atoms, order, lib.settings['编号起始']).get(aid, '')


# ======================= 新建条款 =======================
def new_atom_id(lib, order, pos, lv, code=None, parent=None):
    if lv == '章':
        code = (code or '').strip().upper()
        if not re.fullmatch(r'[A-Z]{2,4}', code):
            raise ValueError('新章需要 2–4 个大写英文字母的章代码，如 WAR')
        if any(a.split('-')[0] == code for a in lib.atoms):
            raise ValueError(f'章代码 {code} 已被使用')
        return f'{code}-00'
    if lv == '条款':
        ch = next(a for a in reversed(order[:pos]) if level(lib, a) == '章')
        code = ch.split('-')[0]
        nums = [int(m.group(1)) for a in lib.atoms for m in [re.fullmatch(code + r'-(\d+)', a)] if m]
        return f'{code}-{max(nums + [0]) + 1:02d}'
    parent = parent or next(a for a in reversed(order[:pos]) if level(lib, a) == '条款')
    nums = [int(m.group(1)) for a in lib.atoms for m in [re.fullmatch(re.escape(parent) + r'-(\d+)', a)] if m]
    return f'{parent}-{max(nums + [0]) + 1}'


def safe_name(name, n=16):
    return re.sub(r'[\\/:*?"<>|\s，。、；：（）()“”‘’《》【】]', '', name)[:n] or 'new'


def insert_atom(lib, after, lv, name, body='', code=None, reason=''):
    """在 after 之后新增章 / 条款 / 子条款。返回 {'ok', 'message', 'id'}"""
    name = (name or '').strip()
    if not name:
        return fail('请填写名称')
    order = current_order(lib)
    if after not in order:
        return fail(f'{after} 不在合同中')
    try:
        pos = insert_pos(lib, order, after, lv)
        aid = new_atom_id(lib, order, pos, lv, code)
    except (ValueError, StopIteration) as e:
        return fail(str(e) or '找不到所属的章或条款')
    ch = name if lv == '章' else chapter_of(lib, order, pos - 1)
    meta = {'id': aid, '名称': name, '层级': lv, '章': ch, '适用': [lib.ctype], '版本': '条款维护'}
    body = body.strip('\n') or (MARK[lv] + name)
    if not body.lstrip().startswith('#'):
        body = MARK[lv] + name + '\n\n' + body
    new_order = order[:pos] + [aid] + order[pos:]
    err = validate(lib, new_order, {aid: lv})
    if err:
        return fail(err)
    errors, _ = check(lib, '条款', aid, body)
    if errors:
        return fail('；'.join(errors))
    import yaml
    fm = '\n' + yaml.safe_dump(meta, allow_unicode=True, sort_keys=False, width=10000)
    p = os.path.join(lib.dir, paths.ATOMS, f'{aid}_{safe_name(name)}.md')
    no = label_of(lib, new_order, aid, {aid: meta})
    res = transaction(lib, {p: join_file(fm, body), recipe_path(lib): write_order(lib, new_order)},
                      f'- {stamp()}　新增{lv} {no} {name}（{aid}）：{reason.strip() or "（未填写原因）"}')
    return {**res, 'id': aid, 'message': f'已新增{lv} {no} {name}（{aid}）' if res['ok'] else res['message']}


# ======================= 移除 / 恢复 =======================
def references(lib, token):
    """内容库中引用了某个占位（如 {{ref:QUA-03}}）的位置：[说明]"""
    out = []
    order = current_order(lib)
    for a in order:
        if token in lib.atoms[a]['body']: out.append(f'条款 {a}')
    for a, x in lib.annexes.items():
        if token in x['body']: out.append(f'附件 {a}')
    for p in glob.glob(os.path.join(lib.dir, '**', '*.*'), recursive=True) + \
            glob.glob(os.path.join(paths.COMMON, '**', '*.yaml'), recursive=True):
        if p.endswith(('.yaml', '.xml')) and os.sep + 'backups' + os.sep not in p and token in open(p, encoding='utf-8').read():
            out.append(os.path.relpath(p, paths.LIBRARY))
    return out


def remove_atom(lib, aid, reason=''):
    order = current_order(lib)
    if aid not in order:
        return fail(f'{aid} 已不在合同中')
    i = order.index(aid)
    if level(lib, aid) != '子条款' and unit_end(lib, order, i) > i + 1:
        return fail('请先移除或移走它下面的' + ('条款' if level(lib, aid) == '章' else '子条款'))
    if aid in lib.settings['付款条款'] or aid == lib.settings['履约保函条款']:
        return fail(f'{aid} 在 type.yaml 中被设为付款条款 / 履约保函条款，不能移除')
    used = references(lib, '{{ref:%s}}' % aid)
    if used:
        return fail(f'以下内容引用了 {aid} 的条款号，请先修改：' + '、'.join(used))
    no, name = label_of(lib, order, aid), lib.atoms[aid]['meta']['名称']
    new_order = order[:i] + order[i + 1:]
    err = validate(lib, new_order)
    if err:
        return fail(err)
    res = transaction(lib, {recipe_path(lib): write_order(lib, new_order)},
                      f'- {stamp()}　移除{level(lib, aid)} {no} {name}（{aid}，文件保留）：{reason.strip() or "（未填写原因）"}')
    return {**res, 'message': f'已从合同中移除 {no} {name}（文件保留，可在“未使用的条款”中恢复）' if res['ok'] else res['message']}


def readd_atom(lib, aid, after, reason=''):
    """把未使用的条款放回合同，放在 after 之后"""
    order = current_order(lib)
    if aid in order:
        return fail(f'{aid} 已在合同中')
    return _place(lib, order, [aid], after, f'恢复{level(lib, aid)}', reason)


def _place(lib, order, unit, after, verb, reason):
    try:
        pos = insert_pos(lib, order, after, level(lib, unit[0]))
    except ValueError as e:
        return fail(str(e))
    new_order = order[:pos] + unit + order[pos:]
    err = validate(lib, new_order)
    if err:
        return fail(err)
    writes = {recipe_path(lib): write_order(lib, new_order)}
    writes.update(fix_chapters(lib, new_order, unit))
    aid = unit[0]; name = lib.atoms[aid]['meta']['名称']
    no = label_of(lib, new_order, aid)
    res = transaction(lib, writes, f'- {stamp()}　{verb} {name}（{aid}）到 {no}：{reason.strip() or "（未填写原因）"}')
    return {**res, 'message': f'已{verb}：{name} 现在是 {no}' if res['ok'] else res['message']}


# ======================= 移动 =======================
def move_atom(lib, aid, direction, reason=''):
    """上移 / 下移（与同级的前一个 / 后一个交换，连同下属子条款）"""
    order = current_order(lib)
    i = order.index(aid); e = unit_end(lib, order, i); lv = LEVELS.index(level(lib, aid))
    if direction == 'up':
        j = i - 1
        while j >= 0 and LEVELS.index(level(lib, order[j])) > lv: j -= 1
        if j < 0 or LEVELS.index(level(lib, order[j])) < lv:
            return fail('已经是第一个了（不能移出所在的章 / 条款，请用“移到…之后”）')
        new_order = order[:j] + order[i:e] + order[j:i] + order[e:]
    else:
        if e >= len(order) or LEVELS.index(level(lib, order[e])) != lv:
            return fail('已经是最后一个了（不能移出所在的章 / 条款，请用“移到…之后”）')
        e2 = unit_end(lib, order, e)
        new_order = order[:i] + order[e:e2] + order[i:e] + order[e2:]
    name = lib.atoms[aid]['meta']['名称']
    old_no, no = label_of(lib, order, aid), label_of(lib, new_order, aid)
    res = transaction(lib, {recipe_path(lib): write_order(lib, new_order)},
                      f'- {stamp()}　{"上移" if direction == "up" else "下移"} {name}（{aid}）：{old_no} → {no}；{reason.strip() or "（未填写原因）"}')
    return {**res, 'message': f'已移动：{name} {old_no} → {no}' if res['ok'] else res['message']}


def move_atom_after(lib, aid, target, reason=''):
    """连同下属子条款移到 target 之后（可跨章，所属章自动更新）"""
    order = current_order(lib)
    i = order.index(aid); e = unit_end(lib, order, i)
    unit = order[i:e]
    if target in unit:
        return fail('不能移到自己或自己的子条款之后')
    rest = order[:i] + order[e:]
    return _place(lib, rest, unit, target, '移动', reason)


# ======================= 附件 =======================
def annex_lines(lines):
    """配方“附件/顺序”中各附件所在的行号 {附件ID: 行号}"""
    out, in_annex, in_seq = {}, False, False
    for i, line in enumerate(lines):
        if re.match(r'^附件:\s*$', line):
            in_annex = True; continue
        if in_annex and re.match(r'^[^\s#]', line):
            break
        if in_annex and re.match(r'^\s+顺序:\s*$', line):
            in_seq = True; continue
        if in_seq:
            m = re.match(r'^\s+- (\S+)', line)
            if m: out[m.group(1)] = i
            elif line.strip() and not line.strip().startswith('#'): in_seq = False
    return out


def move_annex(lib, aid, direction, reason=''):
    lines = open(recipe_path(lib), encoding='utf-8').read().split('\n')
    pos = annex_lines(lines); ids = list(pos)
    k = ids.index(aid); k2 = k - 1 if direction == 'up' else k + 1
    if not 0 <= k2 < len(ids):
        return fail('已经是第一个了' if direction == 'up' else '已经是最后一个了')
    a, b = pos[ids[k]], pos[ids[k2]]
    lines[a], lines[b] = lines[b], lines[a]
    old = annexes.label(lib, aid); new = f'附件{annexes.cn_no(k2 + 1)}'
    res = transaction(lib, {recipe_path(lib): '\n'.join(lines)},
                      f'- {stamp()}　附件顺序：{lib.annexes[aid]["meta"]["名称"]}（{aid}）{old} → {new}；{reason.strip() or "（未填写原因）"}')
    return {**res, 'message': f'已移动：{lib.annexes[aid]["meta"]["名称"]} {old} → {new}（引用该附件的编号已自动更新）' if res['ok'] else res['message']}


def set_annex_default(lib, aid, on, reason=''):
    m = lib.annexes[aid]['meta']
    if m.get('跟随变量'):
        return fail(f'该附件随“{m["跟随变量"]}”自动决定有无，不能单独设置默认')
    p = path_of(lib, '附件', aid)
    fm, body = split_file(open(p, encoding='utf-8').read())
    val = annexes.HAVE if on else annexes.HAVE_NOT
    fm = re.sub(r'(?m)^默认:.*$', f'默认: {val}', fm, count=1) if re.search(r'(?m)^默认:', fm) else fm.rstrip('\n') + f'\n默认: {val}\n'
    backup_item(lib, '附件', aid)
    res = transaction(lib, {p: join_file(fm, body)},
                      f'- {stamp()}　附件默认：{annexes.label(lib, aid)} {m["名称"]}（{aid}）默认改为“{val}”；{reason.strip() or "（未填写原因）"}')
    return {**res, 'message': f'已设为默认“{val}”' if res['ok'] else res['message']}


def add_annex(lib, after, name, name_en, typ='正文', default='有', body='', reason=''):
    """新增附件，放在 after 之后（after 为空则放最后）"""
    name, name_en = (name or '').strip(), (name_en or '').strip()
    if not name or not name_en:
        return fail('请填写中文和英文名称')
    nums = [int(m.group(1)) for a in lib.annexes for m in [re.fullmatch(r'ANX-(\d+)', a)] if m]
    existing = {os.path.basename(p).split('_')[0] for p in glob.glob(os.path.join(lib.dir, paths.ANNEXES, '*.md'))}
    n = max(nums + [0]) + 1
    while f'ANX-{n:02d}' in existing: n += 1
    aid = f'ANX-{n:02d}'
    lines = open(recipe_path(lib), encoding='utf-8').read().split('\n')
    pos = annex_lines(lines)
    if not pos:
        return fail('配方中还没有“附件/顺序”，请先由 AI 建立附件库')
    at = pos[after] if after in pos else max(pos.values())
    indent = re.match(r'^(\s+)-', lines[at]).group(1)
    lines.insert(at + 1, f'{indent}- {aid}')
    import yaml
    meta = {'id': aid, '名称': name, '名称_en': name_en, '类型': typ, '默认': default}
    fm = '\n' + yaml.safe_dump(meta, allow_unicode=True, sort_keys=False, width=10000)
    if typ == '正文':
        errors, _ = check(lib, '附件', aid, body or '（待补充）')
        if errors:
            return fail('；'.join(errors))
    p = os.path.join(lib.dir, paths.ANNEXES, f'{aid}_{safe_name(name)}.md')
    res = transaction(lib, {p: join_file(fm, body if typ == '正文' else ''), recipe_path(lib): '\n'.join(lines)},
                      f'- {stamp()}　新增附件 {name} {name_en}（{aid}）：{reason.strip() or "（未填写原因）"}')
    return {**res, 'id': aid, 'message': f'已新增附件 {name}（{aid}）' if res['ok'] else res['message']}


def remove_annex(lib, aid, reason=''):
    m = lib.annexes[aid]['meta']
    used = [u for t in ('附件', '附件_en', '附件号') for u in references(lib, '{{%s:%s}}' % (t, aid))]
    used = [u for u in dict.fromkeys(used) if u != f'附件 {aid}']
    if used:
        return fail('以下内容引用了该附件的编号，请先修改：' + '、'.join(used))
    lines = open(recipe_path(lib), encoding='utf-8').read().split('\n')
    pos = annex_lines(lines)
    del lines[pos[aid]]
    res = transaction(lib, {recipe_path(lib): '\n'.join(lines)},
                      f'- {stamp()}　移除附件 {annexes.label(lib, aid)} {m["名称"]}（{aid}，文件保留）：{reason.strip() or "（未填写原因）"}')
    return {**res, 'message': f'已移除附件 {m["名称"]}（文件保留；后面的附件编号已自动前移）' if res['ok'] else res['message']}


def unused_annexes(lib):
    """annexes/ 中有文件、但不在“附件/顺序”中的附件 ID"""
    ids = {os.path.basename(p).split('_')[0]: p for p in glob.glob(os.path.join(lib.dir, paths.ANNEXES, '*.md'))}
    return sorted(a for a in ids if a not in lib.annexes)


def readd_annex(lib, aid, after, reason=''):
    lines = open(recipe_path(lib), encoding='utf-8').read().split('\n')
    pos = annex_lines(lines)
    at = pos[after] if after in pos else max(pos.values())
    indent = re.match(r'^(\s+)-', lines[at]).group(1)
    lines.insert(at + 1, f'{indent}- {aid}')
    return transaction(lib, {recipe_path(lib): '\n'.join(lines)}, f'- {stamp()}　恢复附件 {aid}：{reason.strip() or "（未填写原因）"}')

