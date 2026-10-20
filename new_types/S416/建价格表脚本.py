# -*- coding: utf-8 -*-
"""S416 价格表（一次性脚本，留作追溯）。

由 S416-PRICE-底稿.xml（母本 7 列价格表：序号/产品名称/规格型号/单位/单价/总金额/备注）生成两张表：
    library/S416/tables/S416-PRICE-标准.xml    序号/产品名称/规格型号/数量/单位/单价/总金额/备注
    library/S416/tables/S416-PRICE-含重量.xml  序号/产品名称/规格型号/数量/单位/重量（KG）/单价/总金额/备注
合计行只留总金额（单价相加没有意义）。组装时按货物明细里是否填了“重量”选用哪张（变量 价格表样式）。

用法（项目根目录）：python -I new_types/S416/建价格表脚本.py
"""
import os, copy
from lxml import etree

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
W = 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'
q = lambda t: '{%s}%s' % (W, t)
TOTAL = 9026                                                    # 表格总宽（A4，页边距 2.54 厘米）

# (键, 表头, 宽度)
STANDARD = [('序号', '序号', 520), ('产品名称', '产品名称', 1300), ('规格型号', '规格/型号', 1750), ('数量', '数量', 800),
            ('单位', '单位', 700), ('单价', '单价（元/{{计价单位}}）', 1400), ('总金额', '总金额（元）', 1550), ('备注', '备注', 1006)]
WEIGHT = [('序号', '序号', 520), ('产品名称', '产品名称', 1000), ('规格型号', '规格/型号', 1350), ('数量', '数量', 700),
          ('单位', '单位', 650), ('重量', '重量（KG）', 1100), ('单价', '单价（元/{{计价单位}}）', 1200), ('总金额', '总金额（元）', 1400),
          ('备注', '备注', 1106)]
assert sum(w for _, _, w in STANDARD) == TOTAL and sum(w for _, _, w in WEIGHT) == TOTAL


def set_text(tc, text):
    ts = list(tc.iter(q('t')))
    if not ts:                                                  # 空单元格（合计行的备注列）
        assert not text
        return
    ts[0].text = text
    for t in ts[1:]:
        t.text = ''


def cell(tpl, width, text, span=1):
    tc = copy.deepcopy(tpl)
    pr = tc.find(q('tcPr'))
    pr.find(q('tcW')).set(q('w'), str(width))
    g = pr.find(q('gridSpan'))
    if span > 1:
        if g is None:
            g = etree.Element(q('gridSpan')); pr.find(q('tcW')).addnext(g)
        g.set(q('val'), str(span))
    elif g is not None:
        pr.remove(g)
    set_text(tc, text)
    return tc


def build(base, cols):
    tbl = copy.deepcopy(base)
    trs = tbl.findall(q('tr'))
    hdr, row, tot, big = (list(tr.findall(q('tc'))) for tr in trs)
    h_tpl, r_tpl = hdr[3], row[3]                              # 以“单位”列为模板：居中，表头加粗底色
    t_label, t_money, t_blank = tot[0], tot[2], tot[3]
    b_label, b_text = big[0], big[1]
    grid = tbl.find(q('tblGrid'))
    for g in list(grid): grid.remove(g)
    for _, _, w in cols:
        etree.SubElement(grid, q('gridCol')).set(q('w'), str(w))
    for tr in trs:
        for tc in tr.findall(q('tc')): tr.remove(tc)
    idx = [k for k, _, _ in cols].index('总金额')
    before = sum(w for _, _, w in cols[:idx])
    after = sum(w for _, _, w in cols[idx + 1:])
    for k, title, w in cols:
        trs[0].append(cell(h_tpl, w, title))
        trs[1].append(cell(r_tpl, w, '{{行.%s}}' % k))
    trs[2].append(cell(t_label, before, '合 计（元）', idx))
    trs[2].append(cell(t_money, cols[idx][2], '{{价款_合计}}'))
    trs[2].append(cell(t_blank, after, '', len(cols) - idx - 1))
    first = sum(w for _, _, w in cols[:3])                      # “总金额（大写）”占前三列，其后为大写金额
    trs[3].append(cell(b_label, first, '总金额（大写）', 3))
    trs[3].append(cell(b_text, TOTAL - first, '人民币（大写）：{{价款_大写}}', len(cols) - 3))
    return tbl


if __name__ == '__main__':
    src = os.path.join(ROOT, 'new_types', 'S416', 'S416-PRICE-底稿.xml')
    base = etree.parse(src).getroot()[0]
    for name, cols in (('标准', STANDARD), ('含重量', WEIGHT)):
        root = etree.Element('block', nsmap={'w': W})
        root.append(build(base, cols))
        out = os.path.join(ROOT, 'library', 'S416', 'tables', f'S416-PRICE-{name}.xml')
        open(out, 'wb').write(etree.tostring(root, encoding='utf-8', xml_declaration=True))
        print('已生成', out)
