# -*- coding: utf-8 -*-
"""变量管理：变量用在哪里、修改默认值与说明、把条款 / 附件中的一段文字改成变量。

变量定义在 library/common/variables.yaml（各类型共用）和 library/<类型>/variables.yaml（本类型专属，同名时覆盖共用的）。
修改时只改相关的行（保留注释），并经过 maintenance.transaction（试生成失败自动还原，成功记修订记录、更新快照）。
"""
import os, re, glob
import yaml

from . import paths
from .constants import SPECIAL
from .maintenance import transaction, items, path_of, split_file, join_file, backup_item, stamp, UNUSED, PH, check

NAME_RE = re.compile(r'^[\w一-鿿.]+$')


def type_file(lib):
    return os.path.join(lib.dir, paths.VARIABLES)


def common_file():
    return os.path.join(paths.COMMON, paths.VARIABLES)


def _load(p):
    return (yaml.safe_load(open(p, encoding='utf-8')) or {}) if os.path.exists(p) else {}


def defined_in(lib, var):
    """'本类型' / '共用' / '共用+本类型覆盖' / ''"""
    t, c = var in _load(type_file(lib)), var in _load(common_file())
    return '共用+本类型覆盖' if t and c else '本类型' if t else '共用' if c else ''


# ======================= 用在哪里 =======================
def _names(text):
    for k in PH.findall(text):
        k = k.strip()
        if k.startswith(SPECIAL) or k.startswith(('选项:', '选项列表:')):
            continue
        yield k.split(':', 1)[1] if k.startswith(('英文数字:', '中文数字:')) else k


def usage(lib):
    """{变量: [位置说明]}；英文变量（xxx_en）的位置并入中文变量"""
    src = []
    src += [(f"{r['no']} {r['name']}", r['body']) for r in items(lib, '条款') if r['no'] != UNUSED]
    src += [(f"{r['no']} {r['name']}", r['body']) for r in items(lib, '附件')]
    for d in (paths.COMMON, lib.dir):
        for p in sorted(glob.glob(os.path.join(d, paths.OPTIONS, '*.yaml'))):
            src.append((f'选项库：{os.path.splitext(os.path.basename(p))[0]}', open(p, encoding='utf-8').read()))
    src.append(('付款条款库', open(os.path.join(paths.COMMON, paths.PAYMENT_TERMS), encoding='utf-8').read()))
    for sub, lab in ((paths.BLOCKS, '块'), (paths.TABLES, '表格')):
        for p in sorted(glob.glob(os.path.join(lib.dir, sub, '*.xml'))):
            src.append((f'{lab} {os.path.splitext(os.path.basename(p))[0]}', open(p, encoding='utf-8').read()))
    out = {}
    for label, text in src:
        for k in _names(text):
            base = k[:-3] if k.endswith('_en') and k[:-3] in lib.V else k
            out.setdefault(base, [])
            if label not in out[base]: out[base].append(label)
    return out


def rows(lib):
    """变量列表（英文变量并入中文变量一行）"""
    use = usage(lib)
    out = []
    for k, v in lib.V.items():
        if k.endswith('_en') and k[:-3] in lib.V:
            continue
        out.append({'name': k, '类别': v.get('类别', ''), '类型': v.get('类型', ''), '默认值': v.get('默认值', ''),
                    '说明': v.get('说明', ''), '英文': (k + '_en') in lib.V, '定义在': defined_in(lib, k), '用在': use.get(k, [])})
    return out


# ======================= 行级编辑 =======================
def _dump(key, value):
    return yaml.safe_dump({key: value}, allow_unicode=True, width=10 ** 6).rstrip('\n')


def _block(lines, var):
    head = {f'{var}:', f"'{var}':", f'"{var}":'}
    i = next((n for n, l in enumerate(lines) if l.rstrip() in head), None)
    if i is None:
        return None, None
    j = i + 1
    while j < len(lines) and not re.match(r'^\S', lines[j]):
        j += 1
    return i, j


def set_fields(text, var, fields):
    """在 variables.yaml 文本中设置某变量的若干字段（没有该变量则在末尾新建）"""
    lines = text.split('\n')
    i, j = _block(lines, var)
    if i is None:
        body = [f'{var}:'] + ['  ' + _dump(k, v) for k, v in fields.items()]
        return text.rstrip('\n') + '\n' + '\n'.join(body) + '\n'
    for k, v in fields.items():
        hit = next((n for n in range(i + 1, j) if re.match(rf'^  {re.escape(k)}:', lines[n])), None)
        if hit is None:
            lines.insert(i + 1, '  ' + _dump(k, v)); j += 1
        else:
            lines[hit] = '  ' + _dump(k, v)
    return '\n'.join(lines)


def set_default(lib, var, value, desc=None, scope='auto', reason=''):
    """修改默认值（及说明）。scope：auto（改在定义它的文件）/ type（写入本类型，覆盖共用的）"""
    if var not in lib.V:
        return {'ok': False, 'message': f'没有变量“{var}”'}
    value = str(value).replace('\n', ' ').strip()
    where = defined_in(lib, var)
    p = type_file(lib) if scope == 'type' or where in ('本类型', '共用+本类型覆盖') else common_file()
    fields = {'默认值': value}
    if desc is not None and desc.strip() != str(lib.V[var].get('说明', '')).strip():
        fields['说明'] = desc.strip()
    old = lib.V[var].get('默认值', '')
    new_text = set_fields(open(p, encoding='utf-8').read() if os.path.exists(p) else '', var, fields)
    if (yaml.safe_load(new_text) or {}).get(var, {}).get('默认值') != value:
        return {'ok': False, 'message': '写入后校验失败，未保存'}
    scope_txt = '共用，影响所有合同类型' if p == common_file() else f'{lib.ctype} 专属'
    res = transaction(lib, {p: new_text},
                      f'- {stamp()}　变量“{var}”默认值：“{old}” → “{value}”（{scope_txt}）：{reason.strip() or "（未填写原因）"}')
    return {**res, 'message': f'已修改“{var}”的默认值（{scope_txt}）' if res['ok'] else res['message']}


# ======================= 把文字改成变量 =======================
def make_variable(lib, kind, aid, text, var, default=None, desc='', scope='type', replace_all=True, reason=''):
    """把条款 / 附件正文中的 text 换成 {{var}}。var 不存在时新建（默认值默认为原文字，合同内容不变）"""
    text, var = (text or '').strip('\n'), (var or '').strip()
    src = lib.annexes if kind == '附件' else lib.atoms
    body = src[aid]['body']
    if not text:
        return {'ok': False, 'message': '请填写要改成变量的文字'}
    n = body.count(text)
    if not n:
        return {'ok': False, 'message': '正文中找不到这段文字（请从“修改”页复制，注意空格和标点）'}
    if '{{' in text or '}}' in text:
        return {'ok': False, 'message': '这段文字中已经有占位符，请只选普通文字'}
    if not NAME_RE.match(var) or var.startswith(SPECIAL):
        return {'ok': False, 'message': '变量名只能用中文、英文、数字、下划线和点，如“质保月数”“卖方.传真”'}
    default = text if default is None else str(default)
    new_body = body.replace(text, '{{%s}}' % var, -1 if replace_all else 1)
    writes = {}
    if var not in lib.V:
        p = type_file(lib) if scope == 'type' else common_file()
        fields = {'默认值': default, '说明': desc.strip() or f'由条款维护页面新建（原文：{text[:30]}）', '原子': [aid],
                  '类别': '有默认值' if default else '必填', '类型': '值', '母本值': text}
        cur = open(p, encoding='utf-8').read() if os.path.exists(p) else ''
        new_text = cur.rstrip('\n') + '\n' + yaml.safe_dump({var: fields}, allow_unicode=True, sort_keys=False, width=10 ** 6)
        writes[p] = new_text
        lib.V[var] = fields                                  # 供下面的检查使用
    errors, _ = check(lib, kind, aid, new_body)
    if errors:
        return {'ok': False, 'message': '；'.join(errors)}
    fp = path_of(lib, kind, aid)
    fm, _ = split_file(open(fp, encoding='utf-8').read())
    writes[fp] = join_file(fm, new_body)
    backup_item(lib, kind, aid)
    no = next((r['no'] for r in items(lib, kind) if r['id'] == aid), '')
    what = '新建变量' if len(writes) > 1 else '使用已有变量'
    res = transaction(lib, writes, f'- {stamp()}　{no} {src[aid]["meta"]["名称"]}（{aid}）：“{text[:40]}”改为变量 {{{{{var}}}}}'
                                   f'（{what}，默认值“{default[:40]}”，替换 {n if replace_all else 1} 处）：{reason.strip() or "（未填写原因）"}')
    return {**res, 'message': f'已把 {n if replace_all else 1} 处文字改为变量“{var}”（{what}）' if res['ok'] else res['message']}
