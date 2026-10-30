# -*- coding: utf-8 -*-
"""合同附件：编号、有/无、引用，以及目录附件行、附件清单表、附件正文的内容。

附件在 library/<类型>/annexes/ 中一个附件一个 .md；顺序与编号由配方 recipe.yaml 的“附件/顺序”决定
（第 1 个为附件一 / Annex 1，依次类推）。每个附件头信息：
    id、名称、名称_en
    类型：正文（在合同第二部分生成正文）/ 文件（单独的 PDF 等，只在附件清单中打钩）
    默认：有 / 无；跟随变量：如“有技术协议”（该变量为“是”时有）
    另起一页：true 时附件正文从新的一页开始
每份合同在配置的“附件”中写 {附件ID: 有/无} 覆盖默认。

条款中引用附件（编号随顺序自动变化）：
    {{附件:ID}} → 附件五    {{附件_en:ID}} → Annex 5    {{附件号:ID}} → 5
    类型设置“附件编号格式: 字母”时：附件B / ATTACHMENT B / B（PO）。ID 写“末位”表示最后一个附件（如“附件C至{{附件号:末位}}”）
每份合同可以在配置的“附件名称”中改附件的中 / 英文名称（目录、附件清单、附件标题同步）。
每份合同可以带额外的附件：项目预设（预存库“项目信息”中类型设置“项目附件字段”指定的字段，每行“中文名 | 英文名”）和配置中的“自定义附件”。
"""
import re

from .constants import YES
from .money import num_cn

REF = re.compile(r'\{\{(附件|附件_en|附件号):([^}]+)\}\}')
HAVE, HAVE_NOT = '有', '无'


def numbers(lib, st=None):
    """{附件ID: 序号}，从 1 起。类型设置“附件编号: 仅提供的”时，只给“有”的附件依次编号（st 为 {附件ID: 有/无}），
    没有编号的附件在引用处写“附件/”"""
    ids = [a for a in lib.annexes if st is None or st.get(a)] if lib.settings.get('附件编号') == '仅提供的' else list(lib.annexes)
    return {aid: i for i, aid in enumerate(ids, 1)}


def cn_no(n):
    return num_cn(n)


def no_text(lib, n):
    """编号文字：数字（5）或字母（E，类型设置“附件编号格式: 字母”）"""
    return chr(64 + n) if lib.settings.get('附件编号格式') == '字母' else str(n)


def label_n(lib, n, en=False):
    """第 n 个附件的称呼：附件五 / Annex 5（字母格式：附件E / ATTACHMENT E）"""
    if lib.settings.get('附件编号格式') == '字母':
        return f'ATTACHMENT {no_text(lib, n)}' if en else f'附件{no_text(lib, n)}'
    return f'Annex {n}' if en else f'附件{cn_no(n)}'


def label(lib, aid, en=False, nums=None):
    """附件五 / Annex 5；没有编号的附件（不提供，且按提供的附件编号）为空"""
    n = (nums if nums is not None else numbers(lib)).get(aid)
    if n is None:
        return ''
    return label_n(lib, n, en)


def parse_extra(text):
    """项目预设中的附加附件：每行“中文名 | 英文名”（没有“|”时按第一个“ / ”分开）→ [(中文名, 英文名)]"""
    out = []
    for line in str(text or '').replace('\r', '').split('\n'):
        line = line.strip()
        if not line:
            continue
        sep = '|' if '|' in line else (' / ' if ' / ' in line else None)
        zh, _, en = line.partition(sep) if sep else (line, '', '')
        out.append((zh.strip(), en.strip()))
    return out


def add_extra(lib, prefix, items):
    """把额外的附件（[(中文名, 英文名)]）接在附件库之后，ID 为 prefix1、prefix2…"""
    for i, (zh, en) in enumerate(items, 1):
        if zh:
            aid = f'{prefix}{i}'
            lib.annexes[aid] = {'meta': {'id': aid, '名称': zh, '名称_en': en, '类型': '文件', '默认': HAVE}, 'body': '', 'file': None}


def rename(lib, names):
    """本合同中改过名称的附件：{附件ID: {名称, 名称_en}}（只写改过的；英文名留空即不改）"""
    for aid, n in (names or {}).items():
        if aid not in lib.annexes:
            raise SystemExit(f'配置“附件名称”中有未知的附件：{aid}，已有：{list(lib.annexes)}')
        m = lib.annexes[aid]['meta']
        if str(n.get('名称') or '').strip():
            m['名称'] = str(n['名称']).strip()
        if str(n.get('名称_en') or '').strip():
            m['名称_en'] = str(n['名称_en']).strip()


def toc_rows(lib, st, nums, na_mark):
    """目录中的附件行（英文一行、中文一行）：ATTACHMENT B: TECHNICAL AGREEMENT / 附件B：技术协议（没有提供的附件在中文行后标注不适用）"""
    rows = []
    for aid, a in lib.annexes.items():
        m = a['meta']
        rows.append({'行.英文': f"{label(lib, aid, True, nums)}: {m.get('名称_en') or ''}".rstrip(': '),
                     '行.中文': f"{label(lib, aid, False, nums)}：{m['名称']}" + ('' if st.get(aid) else na_mark)})
    return rows


def replace_refs(lib, text, nums=None, st=None):
    """把 {{附件:ID}}、{{附件_en:ID}}、{{附件号:ID}} 换成实际编号（没有编号的附件写“附件/”）"""
    if '{{附件' not in text:
        return text
    nums = nums if nums is not None else numbers(lib, st)

    def rep(m):
        kind, aid = m.group(1), m.group(2).strip()
        if aid == '末位':                                   # 最后一个有编号的附件
            n = max(nums.values(), default=0)
        elif aid not in lib.annexes:
            raise SystemExit(f'引用的附件“{aid}”不在 library/{lib.ctype} 配方的“附件/顺序”中，已有：{list(lib.annexes)}')
        elif aid not in nums:                                # 没有提供的附件：写“附件/”
            return {'附件': '附件/', '附件_en': label_n(lib, 0, True).rsplit(' ', 1)[0] + ' /', '附件号': '/'}[kind]
        else:
            n = nums[aid]
        return {'附件': label_n(lib, n), '附件_en': label_n(lib, n, True), '附件号': no_text(lib, n)}[kind]
    return REF.sub(rep, text)


def default_state(lib, aid, values):
    """附件默认有/无：跟随变量 → 头信息“默认” → 有"""
    m = lib.annexes[aid]['meta']
    if m.get('跟随变量'):
        return str(values.get(m['跟随变量'], '是')) in [str(y) for y in YES]
    return str(m.get('默认', HAVE)) != HAVE_NOT


def follows(lib, aid):
    """该附件的有/无是否跟随变量（表单中不单独勾选）"""
    return bool(lib.annexes[aid]['meta'].get('跟随变量'))


def states(lib, values, chosen=None):
    """{附件ID: True(有)/False(无)}；chosen 为配置中的“附件”{ID: 有/无}，跟随变量的附件不受其影响"""
    chosen = chosen or {}
    unknown = [a for a in chosen if a not in lib.annexes]
    if unknown:
        raise SystemExit(f'配置“附件”中有未知的附件：{unknown}，已有：{list(lib.annexes)}')
    out = {}
    for aid in lib.annexes:
        if aid in chosen and not follows(lib, aid):
            out[aid] = str(chosen[aid]) != HAVE_NOT
        else:
            out[aid] = default_state(lib, aid, values)
    return out


def has_body(lib, aid):
    return lib.annexes[aid]['meta'].get('类型', '正文') == '正文'


def title(lib, aid, en=False, nums=None):
    """附件一 供货明细表 / Annex 1 Detailed Price List"""
    m = lib.annexes[aid]['meta']
    return f"{label(lib, aid, en, nums)} {m.get('名称_en' if en else '名称') or ''}".strip()


def full_title(lib, aid, nums=None):
    """同一行的中英文标题：附件十 项目特殊条款 Annex 10 Project Special Requirements（没有英文名称时只有中文）"""
    en = title(lib, aid, en=True, nums=nums) if lib.annexes[aid]['meta'].get('名称_en') else ''
    return f'{title(lib, aid, nums=nums)} {en}'.strip()


def checkbox(on):
    return '有 ☑    无 □' if on else '有 □    无 ☑'


def summary(lib, st):
    """生成报告用：无的附件（只给提供的附件编号时写名称）"""
    nums = numbers(lib)
    off = [(label(lib, a, nums=nums) if lib.settings.get('附件编号') != '仅提供的' else lib.annexes[a]['meta']['名称'])
           for a, on in st.items() if not on]
    return ('不提供：' + '、'.join(off)) if off else '全部提供'
