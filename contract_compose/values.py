# -*- coding: utf-8 -*-
"""变量：由表单值计算派生变量（价款、技术协议等），以及把条款中的 {{变量}}、{{选项:…}} 替换成文字。"""
import re

from .constants import MISS_L, MISS_R, NA_MARK, YES
from .money import CURRENCIES, price_calc, fmt_money, cn_upper, en_words, num_en, num_cn
from .options import end_punct, choose
from .payment import render_payment


def derive_values(values):
    """由表单填写的值计算出合同中使用的变量（不覆盖已有的同名计算变量以外的内容）"""
    d = {}
    # ---- 质保期自定义：补句号
    for k, en in (('质保期_自定义', False), ('质保期_自定义_en', True)):
        if values.get(k): d[k] = end_punct(values[k], en)
    # ---- 技术协议
    if str(values.get('有技术协议', '是')) in [str(y) for y in YES]:
        d['技术协议说明'] = ('（编号 No.：{{技术协议号}}；版本 Rev.：{{技术协议版本}}；日期 Date：{{技术协议日期}}）')
        d['技术协议目录标注'] = ''
    else:
        d['技术协议说明'] = d['技术协议目录标注'] = NA_MARK
        if not values.get('技术协议号'): d['技术协议号'] = 'N/A'
    # ---- 合同价款
    c = price_calc(values.get('含税总价'), values.get('币种') or 'RMB', values.get('增值税率'))
    sym, cn, code = CURRENCIES[c['币种']]
    d['价款_币种中文'], d['价款_币种代码'] = cn, code
    d['价款_计税'] = '含税' if c['计税'] else '不含税'        # PO 价格表：含增值税行 / 不含增值税行
    d['增值税率'] = (c['税率'] if str(c['税率']).endswith('%') else f"{c['税率']}%") if c['计税'] else 'N/A'
    if '含税' in c:
        d['价款_含税_表'] = fmt_money(c['含税'], sym)
        d['价款_不含税_表'] = fmt_money(c['不含税'], sym)
        d['价款_税额_表'] = fmt_money(c['税额'], sym) if c['计税'] else 'N/A'
        d['价款_大写'] = cn_upper(c['含税'])
        d['价款_英文大写'] = en_words(c['含税'])
    else:
        for k in ('价款_含税_表', '价款_不含税_表', '价款_税额_表', '价款_大写', '价款_英文大写'):
            d[k] = '{{含税总价}}'
        if not c['计税']: d['价款_税额_表'] = 'N/A'
    return d


def expand_options(lib, text, values, choices, used):
    """替换选项变量：整行的 {{选项:付款方式}} / 段落选项整段替换；行内的 {{选项:名称}}、{{选项列表:名称}}"""
    opts = lib.opts
    lines = []
    for line in text.split('\n'):
        m = re.fullmatch(r'\s*\{\{选项:([^}]+)\}\}\s*', line)
        if m and m.group(1) in opts and opts[m.group(1)]['类型'] == '付款方案':
            o = opts[m.group(1)]; k = choose(m.group(1), o, values, choices); used[m.group(1)] = k
            lines.append(render_payment(lib, o, k, values, choices, used))
        elif m and m.group(1) in opts and opts[m.group(1)]['类型'] == '段落':
            o = opts[m.group(1)]; k = choose(m.group(1), o, values, choices); used[m.group(1)] = k
            lines.append(o['选项'][k]['正文'])
        else:
            lines.append(line)
    text = '\n'.join(lines)

    def rep(m):
        kind, name = m.group(1), m.group(2)
        en = name.endswith('_en'); base = name[:-3] if en else name
        o = opts[base]; k = choose(base, o, values, choices); used[base] = k
        if kind == '选项':
            if o['类型'] == '字母选择':
                return k
            opt = o['选项'][k]
            if opt.get('状态') == '待补':
                return f'{MISS_L}选项“{base}/{k}”尚无文字{MISS_R}'
            return opt['英文' if en else '中文']
        items = list(o['选项'].items())
        if o.get('列表格式') == '逐项':
            return '\n\n'.join('- ' + v['列表文字'] for _, v in items)
        if en:
            return '; '.join(f'{kk}) {v["英文"]}' for kk, v in items) + '.'
        return '；'.join(f'{kk}) {v["中文"]}' for kk, v in items) + '。'
    return re.sub(r'\{\{(选项|选项列表):([^}]+)\}\}', rep, text)


def resolve_values(text, V, values, missing, regress=False, keep=None, na=False, mark_vars=False):
    """替换值变量 {{变量}}。取值顺序：明确给出的值 → （回归时）母本值 → 默认值 → 未填。
    mark_vars：变量标注版，所有变量显示为“名称｜母本值”；na：不适用条款中未填变量写 N/A。"""
    def rep(m):
        k = m.group(1)
        if k.startswith(('ref:', 'table:')):
            return m.group(0)
        if k.startswith(('英文数字:', '中文数字:')):      # {{英文数字:付款天数}} → sixty
            kind, var = k.split(':', 1)
            val = resolve_values('{{%s}}' % var, V, values, missing, regress, keep, na, mark_vars)
            if MISS_L in val or val.startswith('{{'):
                return val
            return (num_en if kind == '英文数字' else num_cn)(val)
        if mark_vars and not k.startswith('选项'):
            v = V.get(k, {})
            ref = v.get('母本值') if v.get('母本值') not in (None, '') else v.get('默认值')
            return MISS_L + k + ('｜' + str(ref) if ref not in (None, '') else '') + MISS_R
        if k in values and values[k] is not None:      # 明确给出的值（含空值）直接使用
            return str(values[k])
        v = V.get(k, {})
        if regress:
            if v.get('类别') == '自动（主体库）':
                return m.group(0)
            if v.get('母本值') not in (None, ''):
                return str(v['母本值'])
            if keep is not None and k not in keep and v.get('默认值') in (None, ''):
                return ''
        if v.get('默认值') not in (None, ''):
            return str(v['默认值'])
        if na:                                         # 不适用条款：未填变量写 N/A，不计入待填
            return 'N/A'
        missing.add(k)
        return m.group(0) if regress else f'{MISS_L}{k}{MISS_R}'
    return re.sub(r'\{\{([^}]+)\}\}', rep, text)
