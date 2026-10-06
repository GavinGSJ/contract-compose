# -*- coding: utf-8 -*-
"""付款条款：按所选付款方案与质保方式，从付款条款库（payment_terms.yaml）组装付款节点与单据。

lib 为 library.Library；o 为付款方案所在的选项（opts['付款方式']），k 为所选方案。
"""
import re

from .constants import SPECIAL
from .library import for_type, list_types
from .options import choose


def pay_node(lib, n):
    """取付款节点在当前合同类型下的定义（公共字段 + 类型专属字段）；该类型不适用时返回 None"""
    nd = lib.pay['节点'].get(n)
    if not nd:
        return None
    types = list_types()
    part = nd.get(lib.ctype)
    if any(t in nd for t in types) and part is None:
        return None
    base = {k: v for k, v in nd.items() if k not in types}
    return {**base, **(part or {})}


def pay_nodes_available(lib):
    return [n for n in (for_type(lib.pay.get('顺序'), lib.ctype) or []) if pay_node(lib, n)]


def payment_nodes(lib, o, k, values, choices):
    """返回 (节点列表, 质保方式)"""
    pay, ct, opts = lib.pay, lib.ctype, lib.opts
    nodes = list(o['选项'][k].get('节点') or [])
    if k == '自定义':
        nodes = list(choices.get('付款节点') or [])
    mode = choose('质保方式', opts['质保方式'], values, choices) if '质保方式' in opts else '质保函'
    add = for_type(pay.get('质保金模式追加'), ct)
    if mode == '质保金' and add and add not in nodes:
        nodes.append(add)
    seq = for_type(pay.get('顺序_质保金' if mode == '质保金' else '顺序'), ct) \
        or for_type(pay.get('顺序'), ct) or []
    nodes = [n for n in seq if n in nodes] + [n for n in nodes if n not in seq]
    nodes = [n for n in nodes if pay_node(lib, n) and pay_node(lib, n).get('仅当质保方式') in (None, mode)]
    return nodes, mode


def pay_optional_docs(lib, nodes):
    """所选节点中可选的单据：[(单据ID, 显示文字)]"""
    out, docs = [], lib.pay['单据']
    def walk(ids):
        for d in ids:
            d = d['单据'] if isinstance(d, dict) else d
            v = docs.get(d)
            if isinstance(v, dict):
                if '组' in v: walk(v['组']); continue
                if v.get('可选') and d not in [x for x, _ in out]:
                    t = v.get('正文', ''); t = t[0] if isinstance(t, list) else t
                    out.append((d, t))
                walk(v.get('子项') or [])
    for n in nodes:
        nd = pay_node(lib, n) or {}
        walk(nd.get('单据', []) + (nd.get('单据_质保金') or []))
    return out


def pay_fields(lib, o, k, choices):
    """付款方案用到的变量：先各节点比例，再其他“付款”类变量（如付款天数、主材名称），按出现顺序"""
    nodes, _ = payment_nodes(lib, o, k, {}, choices)
    text = render_payment(lib, o, k, {}, choices, {})
    names = []
    for m in re.findall(r'\{\{([^}]+)\}\}', text):
        m = m.split(':', 1)[1] if m.startswith(('英文数字:', '中文数字:')) else m
        if m not in names and not m.startswith(SPECIAL): names.append(m)
    ratios = [pay_node(lib, n)['比例变量'] for n in nodes]
    return ratios + [x for x in names if x not in ratios]


def render_payment(lib, o, k, values, choices, used):
    """按合同类型的排版输出付款节点：FA 为 4.2 下的 a) b)（单据为 1) 2)），PO 为 3.2.1 子条款（单据为 a. b.）"""
    nodes, mode = payment_nodes(lib, o, k, values, choices)
    used['质保方式'] = mode
    extra = set(choices.get('付款可选单据') or [])
    docs = lib.pay['单据']
    sub = for_type(lib.pay.get('排版'), lib.ctype) == '子条款'
    T, B, D, DC, D2 = ('### ', '', '- ', '  ', '  - ') if sub else ('- ', '  ', '  - ', '    ', '    - ')

    def doc_lines(ids, ratio, lv=D, cont=DC):
        out = []
        for d in ids:
            if isinstance(d, dict):
                if d.get('质保方式') and d['质保方式'] != mode: continue
                if d.get('无节点') and d['无节点'] in nodes: continue
                if d.get('有节点') and d['有节点'] not in nodes: continue
                d = d['单据']
            v = docs[d]
            if isinstance(v, dict) and '组' in v:
                out += doc_lines(v['组'], ratio, lv, cont); continue
            table = None; children = []
            if isinstance(v, dict):
                if v.get('可选') and d not in extra: continue
                table, children = v.get('表格'), v.get('子项') or []
                v = v.get('正文', '')
            lines = v if isinstance(v, list) else [v]
            lines = [x.replace('{{本节点比例}}', '{{%s}}' % ratio) for x in lines]
            out.append(lv + lines[0])
            out += [cont + x for x in lines[1:]]
            if children:
                out += doc_lines(children, ratio, D2, '      ' if not sub else '    ')
            if table:
                out.append('{{table:%s}}' % table)
        return out
    parts = []
    for n in nodes:
        nd = pay_node(lib, n)
        body = nd.get('正文_质保金') if mode == '质保金' and nd.get('正文_质保金') else nd.get('正文', [])
        ratio = nd.get('比例变量', '')
        parts.append(T + nd['标题'])
        parts += [B + x.replace('{{本节点比例}}', '{{%s}}' % ratio) for x in body]
        dl = nd.get('单据_质保金') if mode == '质保金' and nd.get('单据_质保金') is not None else nd.get('单据', [])
        parts += doc_lines(dl, ratio)
    return '\n\n'.join(parts)
