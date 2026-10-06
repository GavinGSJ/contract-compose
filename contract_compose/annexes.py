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
"""
import re

from .constants import YES
from .money import num_cn

REF = re.compile(r'\{\{(附件|附件_en|附件号):([^}]+)\}\}')
HAVE, HAVE_NOT = '有', '无'


def numbers(lib):
    """{附件ID: 序号}，从 1 起"""
    return {aid: i for i, aid in enumerate(lib.annexes, 1)}


def cn_no(n):
    return num_cn(n)


def label(lib, aid, en=False, nums=None):
    n = (nums or numbers(lib))[aid]
    return f'Annex {n}' if en else f'附件{cn_no(n)}'


def replace_refs(lib, text, nums=None):
    """把 {{附件:ID}}、{{附件_en:ID}}、{{附件号:ID}} 换成实际编号"""
    if '{{附件' not in text:
        return text
    nums = nums or numbers(lib)

    def rep(m):
        kind, aid = m.group(1), m.group(2).strip()
        if aid not in nums:
            raise SystemExit(f'引用的附件“{aid}”不在 library/{lib.ctype} 配方的“附件/顺序”中，已有：{list(nums)}')
        n = nums[aid]
        return {'附件': f'附件{cn_no(n)}', '附件_en': f'Annex {n}', '附件号': str(n)}[kind]
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
    return f"{label(lib, aid, en, nums)} {m['名称_en' if en else '名称']}"


def full_title(lib, aid, nums=None):
    """同一行的中英文标题：附件十 项目特殊条款 Annex 10 Project Special Requirements"""
    return f'{title(lib, aid, nums=nums)} {title(lib, aid, en=True, nums=nums)}'


def checkbox(on):
    return '有 ☑    无 □' if on else '有 □    无 ☑'


def summary(lib, st):
    """生成报告用：无的附件"""
    nums = numbers(lib)
    off = [label(lib, a, nums=nums) for a, on in st.items() if not on]
    return ('不提供：' + '、'.join(off)) if off else '全部提供'
