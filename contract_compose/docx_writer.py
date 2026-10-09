# -*- coding: utf-8 -*-
"""Word 写入：把带行首标记的条款文字写成样式段落，插入块 / 表格 XML，替换 XML 中的变量。"""
import re, copy
from docx import Document
from docx.oxml.ns import qn
from lxml import etree

from .constants import MISS_L, MISS_R, LABEL_MISSING

XML_SPACE = '{http://www.w3.org/XML/1998/namespace}space'


class Writer:
    MARKS = [('### ', '合同-子条款', 'C2'), ('## ', '合同-条款', 'C1'), ('# ', '合同-章标题', 'H1'),
             ('  - ', '合同-列项二级', 'L2'), ('  + ', '合同-列项二级', 'N2'), ('- ', '合同-列项', 'L1'),
             ('+ ', '合同-列项', 'N1'), ('<顶格> ', '合同-正文（顶格）', 'P'), ('<居中> ', '合同-正文（居中）', 'P'),
             ('    ', '合同-正文（二级续行）', 'CONT'), ('  ', '合同-正文（列项续行）', 'CONT')]
    FALLBACK = {'合同-正文（二级续行）': '合同-正文（列项续行）', '合同-正文（居中）': '合同-正文（顶格）',
                '合同-附件标题': '合同-部分标题（英文）'}
    PAGE = '<分页>'                                             # 单独一行：分页

    def __init__(self, template, label=LABEL_MISSING):
        self.label = label                                      # 未填变量的标签：待填 / 变量（标注版）
        self.doc = Document(template)
        self.body = self.doc.element.body
        self.sect = self.body.find(qn('w:sectPr'))
        for e in list(self.body):
            if e is not self.sect:
                self.body.remove(e)
        self.sid = {s.name: s.style_id for s in self.doc.styles}
        self.numxml = self.doc.part.numbering_part.element
        # 模板中已有的编号实例保留（1 = 章节/条款/列项主编号；其他为块中使用的独立列项）
        self.next_num = max([int(n.get(qn('w:numId'))) for n in self.numxml.findall(qn('w:num'))] + [1]) + 1
        self.list_num = None; self.groups = 0; self.prev = 'H1'
        self.plain = '合同-正文'                                 # 无标记行的样式（附件正文中为顶格）

    def add(self, e):
        self.sect.addprevious(e); return e

    def new_num(self):
        nid = str(self.next_num); self.next_num += 1
        n = etree.SubElement(self.numxml, qn('w:num')); n.set(qn('w:numId'), nid)
        a = etree.SubElement(n, qn('w:abstractNumId')); a.set(qn('w:val'), '0')
        for lv in ('3', '4', '5', '6'):
            o = etree.SubElement(n, qn('w:lvlOverride')); o.set(qn('w:ilvl'), lv)
            s = etree.SubElement(o, qn('w:startOverride')); s.set(qn('w:val'), '1')
        return nid

    def runs(self, p, text):
        text = text.replace('\\*', '\u0003')
        bold = und = False
        for tok in re.split(r'(\*\*|<u>|</u>|<br>|\t|\u0001[^\u0002]*\u0002)', text):
            if not tok:
                continue
            if tok == '**': bold = not bold; continue
            if tok == '<u>': und = True; continue
            if tok == '</u>': und = False; continue
            r = etree.SubElement(p, qn('w:r'))
            rp = etree.SubElement(r, qn('w:rPr'))
            if bold: etree.SubElement(rp, qn('w:b'))
            if und: etree.SubElement(rp, qn('w:u')).set(qn('w:val'), 'single')
            if tok == '<br>': etree.SubElement(r, qn('w:br'))
            elif tok == '\t': etree.SubElement(r, qn('w:tab'))
            elif tok.startswith(MISS_L):
                etree.SubElement(rp, qn('w:highlight')).set(qn('w:val'), 'yellow')
                t = etree.SubElement(r, qn('w:t')); t.text = '【' + self.label + '：' + tok[1:-1] + '】'
            else:
                t = etree.SubElement(r, qn('w:t')); t.text = tok.replace('\u0003', '*')
                t.set(XML_SPACE, 'preserve')
            if not len(rp): r.remove(rp)

    def style_id(self, style):
        while style not in self.sid and style in self.FALLBACK:     # 样式模板中没有时按 FALLBACK 退回
            style = self.FALLBACK[style]
        return self.sid.get(style) or self.sid['合同-正文']

    def para(self, style, text, num=None, page_break=False):
        p = etree.Element(qn('w:p')); ppr = etree.SubElement(p, qn('w:pPr'))
        etree.SubElement(ppr, qn('w:pStyle')).set(qn('w:val'), self.style_id(style))
        if page_break:
            etree.SubElement(ppr, qn('w:pageBreakBefore'))
        if num:
            n = etree.SubElement(ppr, qn('w:numPr'))
            etree.SubElement(n, qn('w:ilvl')).set(qn('w:val'), num[1])
            etree.SubElement(n, qn('w:numId')).set(qn('w:val'), num[0])
        self.runs(p, text)
        return self.add(p)

    def page_break(self):
        p = etree.Element(qn('w:p')); r = etree.SubElement(p, qn('w:r'))
        etree.SubElement(r, qn('w:br')).set(qn('w:type'), 'page')
        return self.add(p)

    def heading(self, style, lines, page_break=False):
        """不编号的标题（如附件标题）；其后的列项重新从 a) / 1) 开始编号"""
        for i, t in enumerate(lines):
            self.para(style, t, page_break=page_break and i == 0)
        self.list_num = None; self.groups = 1; self.prev = 'H1'

    def line(self, line):
        if line.strip() == self.PAGE:
            self.page_break(); return
        for mark, style, kind in self.MARKS:
            if line.startswith(mark):
                text = line[len(mark):]; break
        else:
            style, kind, text = self.plain, 'P', line
        num = None
        if kind in ('H1', 'C1', 'C2'):
            self.list_num = None; self.groups = 0
        elif kind in ('L1', 'N1'):
            if self.prev not in ('L1', 'L2', 'N1', 'N2', 'CONT'):      # 新的一组列项
                self.groups += 1
                self.list_num = self.new_num() if self.groups > 1 else None
            if kind == 'N1': num = (self.list_num or '1', '5')       # 数字列项 1) 2)：显式编号
            elif self.list_num: num = (self.list_num, '3')
        elif kind in ('L2', 'N2'):
            if self.prev not in ('L1', 'L2', 'N1', 'N2', 'CONT'):      # 直接以二级列项开头的一组：重新编号
                self.groups += 1
                self.list_num = self.new_num() if self.groups > 1 else None
            if kind == 'N2': num = (self.list_num or '1', '6')
            elif self.list_num: num = (self.list_num, '4')
        self.para(style, text.strip(), num)
        self.prev = kind

    def block(self, path, fill):
        root = etree.parse(path).getroot()
        for e in root:
            e = copy.deepcopy(e)
            strip_ids(e); fill(e)
            self.add(e)

    def table_rows(self, path, rows, fill):
        """插入表格，最后一行为行模板：按 rows（[{占位名: 值}]）逐行复制并替换其中的 {{占位名}}"""
        root = etree.parse(path).getroot()
        for e in root:
            e = copy.deepcopy(e); strip_ids(e)
            if e.tag == qn('w:tbl'):
                trs = e.findall(qn('w:tr'))                         # 行模板：含 {{行.…}} 的行，否则为最后一行
                tpl = next((tr for tr in trs if '{{行.' in ''.join(t.text or '' for t in tr.iter(qn('w:t')))), trs[-1])
                for row in rows:
                    tr = copy.deepcopy(tpl)
                    for t in tr.iter(qn('w:t')):
                        for k, v in row.items():
                            if t.text and '{{%s}}' % k in t.text:
                                t.text = t.text.replace('{{%s}}' % k, v)
                    tpl.addprevious(tr)
                e.remove(tpl)
            fill(e)
            self.add(e)

    def toc_lines(self, lines, first_before=200):
        """目录中的附加行（不带页码），第一行前加段前距"""
        for i, t in enumerate(lines):
            p = self.para('toc 1', t)
            if i == 0 and first_before:
                etree.SubElement(p.find(qn('w:pPr')), qn('w:spacing')).set(qn('w:before'), str(first_before))

    def toc(self, heads, title, lead_lines, nfmt):
        """目录：标题、前置行、各章（编号 + 标题），整体包在一个 TOC 域中"""
        self.para('合同-目录标题', title)
        for x in lead_lines:
            self.para('toc 1', x)
        for i, (n, h) in enumerate(heads):
            p = etree.Element(qn('w:p')); ppr = etree.SubElement(p, qn('w:pPr'))
            etree.SubElement(ppr, qn('w:pStyle')).set(qn('w:val'), self.sid['toc 1'])
            r = etree.SubElement(p, qn('w:r'))
            if i == 0:
                etree.SubElement(r, qn('w:fldChar')).set(qn('w:fldCharType'), 'begin')
                it = etree.SubElement(r, qn('w:instrText')); it.set(XML_SPACE, 'preserve')
                it.text = ' TOC \\o "1-1" \\n \\h \\z \\u '
                etree.SubElement(r, qn('w:fldChar')).set(qn('w:fldCharType'), 'separate')
            etree.SubElement(r, qn('w:t')).text = nfmt.format(n=n)
            etree.SubElement(r, qn('w:tab'))
            t = etree.SubElement(r, qn('w:t')); t.text = h; t.set(XML_SPACE, 'preserve')
            if i == len(heads) - 1:
                etree.SubElement(r, qn('w:fldChar')).set(qn('w:fldCharType'), 'end')
            self.add(p)


def strip_ids(e):
    W14 = '{http://schemas.microsoft.com/office/word/2010/wordml}'
    for x in e.iter():
        for a in (W14 + 'paraId', W14 + 'textId'):
            if a in x.attrib: del x.attrib[a]


def fill_xml(e, fn, label=LABEL_MISSING):
    """替换 XML 中 w:t 文本里的 {{变量}}；未填变量所在的 run 标黄"""
    for t in e.iter(qn('w:t')):
        if t.text and '{{' in t.text:
            new = fn(t.text)
            if MISS_L in new:
                r = t.getparent(); rp = r.find(qn('w:rPr'))
                if rp is None: rp = etree.Element(qn('w:rPr')); r.insert(0, rp)
                if rp.find(qn('w:highlight')) is None:
                    etree.SubElement(rp, qn('w:highlight')).set(qn('w:val'), 'yellow')
                new = re.sub(MISS_L + r'([^' + MISS_R + r']*)' + MISS_R, '【' + label + r'：\1】', new)
            t.text = new
