# -*- coding: utf-8 -*-
"""读取合同母本 docx：逐段还原“Word 实际显示的编号”、样式、手打编号、表格、页眉页脚。
供 health_check.py（体检）及今后的新建合同类型工具共用，不做任何修改。

用法（当模块用）：
    from contract_compose.master_parser import parse
    m = parse('母本.docx')
    for p in m['paras']: print(p['i'], p['label'], p['kind'], p['text'][:40])
"""
import re, zipfile
from lxml import etree

W = 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'
MC = 'http://schemas.openxmlformats.org/markup-compatibility/2006'
q = lambda t: '{%s}%s' % (W, t)
cjk = lambda s: sum('一' <= c <= '鿿' for c in s) / max(1, len(s))

HEAD_STYLE = re.compile(r'标题|heading|小标题|title|^\d级$|章', re.I)


# ------------------------------------------------------------ 编号格式
CN = '零一二三四五六七八九十'

def _cn(n):
    if n <= 10: return CN[n]
    if n < 20: return '十' + (CN[n - 10] if n > 10 else '')
    if n < 100: return CN[n // 10] + '十' + (CN[n % 10] if n % 10 else '')
    return str(n)

def _letters(n, upper=False):
    s = ''
    while n > 0:
        n, r = divmod(n - 1, 26); s = chr(97 + r) + s
    return s.upper() if upper else s

def _roman(n, upper=False):
    out = ''
    for v, r in [(1000, 'm'), (900, 'cm'), (500, 'd'), (400, 'cd'), (100, 'c'), (90, 'xc'), (50, 'l'), (40, 'xl'),
                 (10, 'x'), (9, 'ix'), (5, 'v'), (4, 'iv'), (1, 'i')]:
        while n >= v: out += r; n -= v
    return out.upper() if upper else out

def fmt_num(n, f):
    if f == 'decimal': return str(n)
    if f == 'decimalZero': return f'{n:02d}'
    if f == 'lowerLetter': return _letters(n)
    if f == 'upperLetter': return _letters(n, True)
    if f == 'lowerRoman': return _roman(n)
    if f == 'upperRoman': return _roman(n, True)
    if f in ('chineseCounting', 'chineseCountingThousand', 'ideographTraditional', 'chineseLegalSimplified'): return _cn(n)
    if f in ('bullet', 'none'): return ''
    return str(n)


# ------------------------------------------------------------ 手打编号
MANUAL = [
    (re.compile(r'^\s*(\d+(?:\.\d+)+)\.?(?=\s|[一-鿿])\s*'), 'dotted'),     # 3.2.1 / 17.1
    (re.compile(r'^\s*第\s*([一二三四五六七八九十百零\d]+)\s*[条章款节项]\s*'), 'di'),    # 第一条
    (re.compile(r'^\s*(\d+)\s*[\.、．]\s+(?=\S)'), 'num_dot'),                       # 1. xxx / 1、xxx
    (re.compile(r'^\s*(\d+)\s*\)\s*(?=\S)'), 'num_paren'),                         # 1) xxx
    (re.compile(r'^\s*[（(]\s*([a-zA-Z]{1,2}|[ivxIVX]{1,4}|\d{1,2}|[一二三四五六七八九十]{1,3})\s*[）)]\s*'), 'paren'),  # (a) （一）
    (re.compile(r'^\s*([a-zA-Z])\s*[\.．\)]\s+(?=\S)'), 'letter'),                  # a. xxx / a) xxx
    (re.compile(r'^\s*([一二三四五六七八九十]{1,3})\s*[、．\.]\s*(?=\S)'), 'cn_dot'),   # 一、
]

def manual_label(text):
    for rx, kind in MANUAL:
        m = rx.match(text)
        if m:
            return m.group(0).strip(), m.group(1), kind
    return None


def label_level(label):
    """'3.2.1'→3，'3'/'3.'→1（可能是章，也可能是数字列项），其余→0"""
    l = label.strip().rstrip('.．')
    if re.fullmatch(r'\d+', l): return 1
    if re.fullmatch(r'\d+\.\d+', l): return 2
    if re.fullmatch(r'\d+(\.\d+){2}', l): return 3
    if re.fullmatch(r'\d+(\.\d+){3,}', l): return 4
    return 0


# ------------------------------------------------------------ 文本
def para_text(p):
    out = []
    def walk(e):
        for c in e:
            tag = c.tag
            if tag in (q('del'), '{%s}Fallback' % MC, q('pPr'), q('rPrChange')):
                continue
            if tag == q('t'): out.append(c.text or '')
            elif tag == q('tab'): out.append('\t')
            elif tag in (q('br'), q('cr')):
                if c.get(q('type')) != 'page': out.append(' ')
            elif tag == q('noBreakHyphen'): out.append('-')
            else: walk(c)
    walk(p)
    return ''.join(out).replace(' ', ' ')


def bold_ratio(p, style_bold):
    tot = b = 0
    for r in p.iter(q('r')):
        txt = ''.join(t.text or '' for t in r.iter(q('t')))
        if not txt: continue
        rp = r.find(q('rPr')); on = style_bold
        if rp is not None:
            x = rp.find(q('b'))
            if x is not None: on = x.get(q('val')) not in ('0', 'false')
        tot += len(txt); b += len(txt) if on else 0
    return b / tot if tot else 0.0


# ------------------------------------------------------------ 主入口
def parse(path):
    z = zipfile.ZipFile(path)
    doc = etree.fromstring(z.read('word/document.xml'))
    sty = etree.fromstring(z.read('word/styles.xml'))
    num = etree.fromstring(z.read('word/numbering.xml')) if 'word/numbering.xml' in z.namelist() else None
    body = doc.find(q('body'))

    # —— 样式
    styles = {}
    default_p = None
    for s in sty.findall(q('style')):
        sid = s.get(q('styleId')); nm = s.find(q('name'))
        base = s.find(q('basedOn')); ppr = s.find(q('pPr')); rpr = s.find(q('rPr'))
        numpr = ppr.find(q('numPr')) if ppr is not None else None
        d = {'name': nm.get(q('val')) if nm is not None else sid, 'based': base.get(q('val')) if base is not None else None,
             'numId': None, 'ilvl': None, 'bold': False}
        if numpr is not None:
            ni = numpr.find(q('numId')); il = numpr.find(q('ilvl'))
            d['numId'] = ni.get(q('val')) if ni is not None else None
            d['ilvl'] = il.get(q('val')) if il is not None else None
        if rpr is not None and rpr.find(q('b')) is not None:
            d['bold'] = rpr.find(q('b')).get(q('val')) not in ('0', 'false')
        styles[sid] = d
        if s.get(q('type')) == 'paragraph' and s.get(q('default')) == '1': default_p = sid

    def eff_style(sid, key, seen=None):
        seen = seen or set()
        while sid and sid in styles and sid not in seen:
            seen.add(sid)
            if styles[sid][key] not in (None, False): return styles[sid][key]
            sid = styles[sid]['based']
        return None

    # —— 编号定义
    absn, nums, pstyle_link = {}, {}, {}
    if num is not None:
        for a in num.findall(q('abstractNum')):
            aid = a.get(q('abstractNumId')); lv = {}
            for l in a.findall(q('lvl')):
                il = int(l.get(q('ilvl')))
                g = lambda t, k='val': (l.find(q(t)).get(q(k)) if l.find(q(t)) is not None else None)
                lv[il] = {'start': int(g('start') if g('start') is not None else 0), 'fmt': g('numFmt') or 'decimal', 'text': g('lvlText') or '',
                          'restart': g('lvlRestart'), 'pStyle': g('pStyle')}
                if g('pStyle'): pstyle_link[g('pStyle')] = (aid, il)
            absn[aid] = lv
        for n in num.findall(q('num')):
            nid = n.get(q('numId')); ab = n.find(q('abstractNumId')).get(q('val')); ov = {}
            for o in n.findall(q('lvlOverride')):
                so = o.find(q('startOverride'))
                if so is not None: ov[int(o.get(q('ilvl')))] = int(so.get(q('val')))
            nums[nid] = {'abs': ab, 'ov': ov}

    counters, seen_num = {}, set()

    def next_label(nid, il):
        n = nums.get(nid)
        if not n or n['abs'] not in absn: return None, None
        ab = n['abs']; lv = absn[ab]
        if il not in lv: return None, None
        c = counters.setdefault(ab, {})
        if nid not in seen_num:                       # 该 numId 首次出现：应用 startOverride（重新开始）
            seen_num.add(nid)
            for k, v in n['ov'].items(): c[k] = v - 1
        c[il] = c.get(il, lv[il]['start'] - 1) + 1
        for k in list(c):
            if k > il:
                rs = lv.get(k, {}).get('restart')
                if rs is not None and int(rs) == 0: continue      # lvlRestart=0：不随上级重新开始
                del c[k]
        def cur(k):
            return c.get(k, lv.get(k, {'start': 0})['start'])
        txt = lv[il]['text']
        if lv[il]['fmt'] == 'bullet': return '•', {'start': lv[il]['start'], 'fmt': 'bullet', 'level': il, 'num': nid}
        lab = re.sub(r'%(\d)', lambda m: fmt_num(cur(int(m.group(1)) - 1), lv.get(int(m.group(1)) - 1, {'fmt': 'decimal'})['fmt']), txt)
        return lab, {'start': lv[il]['start'], 'fmt': lv[il]['fmt'], 'level': il, 'num': nid, 'raw_n': c[il]}

    paras, tables = [], []
    stats = {'ins': len(list(body.iter(q('ins')))), 'del': len(list(body.iter(q('del')))),
             'comments': len(list(body.iter(q('commentReference'))))}

    def do_para(p, i, kind, parent=None):
        ppr = p.find(q('pPr')); sid = default_p
        nid = il = None
        if ppr is not None:
            x = ppr.find(q('pStyle'))
            if x is not None: sid = x.get(q('val'))
            n = ppr.find(q('numPr'))
            if n is not None:
                ni = n.find(q('numId')); li = n.find(q('ilvl'))
                nid = ni.get(q('val')) if ni is not None else None
                il = li.get(q('val')) if li is not None else None
        direct = nid is not None
        if nid is None:
            nid = eff_style(sid, 'numId'); il = il if il is not None else eff_style(sid, 'ilvl')
        if il is None and sid in pstyle_link and nums.get(nid, {}).get('abs') == pstyle_link[sid][0]:
            il = str(pstyle_link[sid][1])
        if il is None: il = '0'
        label = info = None
        if nid not in (None, '0'):
            label, info = next_label(nid, int(il))
        text = para_text(p)
        sname = styles.get(sid, {}).get('name', sid or 'Normal')
        rec = {'i': i, 'kind': kind, 'parent': parent, 'style': sname, 'text': text.strip(), 'label': label or '',
               'auto': bool(label), 'numId': nid if label else None, 'ilvl': int(il) if label else None,
               'numfmt': info['fmt'] if info else None, 'start': info['start'] if info else None,
               'bold': bold_ratio(p, bool(eff_style(sid, 'bold'))) if text.strip() else 0.0,
               'is_head_style': bool(HEAD_STYLE.search(sname or ''))}
        m = manual_label(rec['text']) if rec['text'] else None
        if m:
            rec['manual'] = m[0]; rec['manual_val'] = m[1]; rec['manual_kind'] = m[2]
            rec['body'] = rec['text'][len(m[0]) if rec['text'].startswith(m[0]) else 0:].strip() \
                if rec['text'].lstrip().startswith(m[0]) else rec['text']
            mm = None
            for rx, k in MANUAL:
                mm = rx.match(rec['text'])
                if mm: break
            rec['body'] = rec['text'][mm.end():].strip()
        else:
            rec['manual'] = ''; rec['manual_val'] = ''; rec['manual_kind'] = ''; rec['body'] = rec['text']
        paras.append(rec)

    for i, e in enumerate(body):
        if e.tag == q('p'):
            do_para(e, i, 'p')
        elif e.tag == q('tbl'):
            rows = e.findall(q('tr'))
            first = ''.join(para_text(p) for p in rows[0].iter(q('p')))[:60] if rows else ''
            tables.append({'i': i, 'rows': len(rows), 'cols': len(rows[0].findall(q('tc'))) if rows else 0, 'first': first.strip()})
            for p in e.iter(q('p')):
                do_para(p, i, 'tp', parent=i)

    # —— 页眉页脚
    hf = {}
    for n in z.namelist():
        if re.match(r'word/(header|footer)\d*\.xml$', n):
            r = etree.fromstring(z.read(n))
            t = ' | '.join(x for x in (para_text(p).strip() for p in r.iter(q('p'))) if x)
            if t: hf[n.split('/')[-1]] = t
    return {'paras': paras, 'tables': tables, 'headers': hf, 'stats': stats,
            'styles_used': {}}


def classify(p):
    """给段落定“层级”：章 / 条款 / 子条款 / 列项 / 正文 / 空。依据 Word 显示编号或手打编号。"""
    if not p['text']:
        return '空'
    lab = p['label'] if p['auto'] and p['numfmt'] != 'bullet' else ''
    src = lab or p.get('manual') or ''
    lv = label_level(src) if src else 0
    shortish = len(p['text']) <= 100
    if lv == 1:
        if shortish and (p['is_head_style'] or p['bold'] > 0.8 or (p['body'].upper() == p['body'] and cjk(p['body']) < 0.3)):
            return '章'
        return '列项'
    if lv == 2: return '条款'
    if lv >= 3: return '子条款'
    if src: return '列项'
    if p['auto'] and p['numfmt'] == 'bullet': return '列项'
    if p['is_head_style'] and shortish: return '标题'
    return '正文'
