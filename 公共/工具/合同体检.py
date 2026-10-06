# -*- coding: utf-8 -*-
"""合同母本体检：只读，不改文件。扫出编号、引用、待填位、文字疑点，生成 Markdown 报告 + JSON 数据。

用法：
    python 公共/工具/合同体检.py <母本.docx> [--out 目录]
默认输出到 合同生成/新增类型/<母本名>/ ：体检报告.md、段落.json

程序只“发现”，不“判断”：报告里标【需处理】的是几乎肯定有问题的，
标【请核对】的需要结合合同语义判断（交给 AI + 你确认）。
"""
import os, re, sys, json, argparse, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from 母本解析 import parse, classify, label_level, cjk

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CAP = 40                                   # 报告里每类最多列出的条数（完整数据在 JSON）

REF_ZH = re.compile(r'第\s*(\d+(?:\.\d+)*)\s*(?:条|款|章|项)')
REF_EN = re.compile(r'\b(?:Articles?|Clauses?|Sections?|Paragraphs?|Sub-?clauses?)\s+(\d+(?:\.\d+)*)', re.I)
PLACEHOLDER = [
    (re.compile(r'X{3,}|x{3,}'), 'XXX'), (re.compile(r'_{3,}'), '____'), (re.compile(r'…{2,}|\.{4,}'), '……'),
    (re.compile(r'\[[^\]]{0,40}\]'), '[方括号]'), (re.compile(r'【[^】]{0,40}】'), '【】'),
    (re.compile(r'\b(?:TBD|TBC|tbd|tbc)\b'), 'TBD/TBC'), (re.compile(r'[一-鿿]*[（(]\s*(?:如有|若有)\s*[）)]'), '（如有）'),
    (re.compile(r'\d{0,4}\s*年\s*月\s*日|\b[A-Z][a-z]+\s*,?\s*20\d\d\s*$'), '日期占位'),
    (re.compile(r'\(\s{1,6}\)|（\s{1,6}）'), '空括号'),
]
OK_DOUBLE = set('往常每刚渐种处点年天人事个慢好仅形纷日步步层层')
SENT_END = '。．.；;：:）)”"!！?？,，、'


def short(t, n=60):
    t = re.sub(r'\s+', ' ', t).strip()
    return t[:n] + ('…' if len(t) > n else '')


def loc(p):
    lab = p['label'] or p.get('manual') or ''
    return f"p{p['i']}" + (f" [{lab}]" if lab else '')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('docx'); ap.add_argument('--out')
    a = ap.parse_args()
    name = os.path.splitext(os.path.basename(a.docx))[0]
    out = a.out or os.path.join(ROOT, '新增类型', name)
    os.makedirs(out, exist_ok=True)
    m = parse(a.docx)
    P = [p for p in m['paras']]
    for p in P: p['层级'] = classify(p)
    # —— 目录条目：早出现的“章”，若后面有标题相近的“章”，视为目录（不参与后续检查，只做目录/正文核对）
    import difflib
    nz = lambda s: re.sub(r'[^0-9a-z一-鿿]', '', s.lower())
    cj = lambda s: ''.join(c for c in s if '一' <= c <= '鿿')
    chaps = [p for p in P if p['kind'] == 'p' and p['层级'] == '章']
    toc_pairs = []
    for e in chaps:
        best = None
        for b in chaps:
            if b['i'] > e['i'] + 3:
                r = difflib.SequenceMatcher(None, nz(e['text'])[:30], nz(b['text'])[:30]).ratio()
                if len(cj(e['text'])) >= 2 and len(cj(b['text'])) >= 2:
                    r = max(r, difflib.SequenceMatcher(None, cj(e['text']), cj(b['text'])).ratio())
                if r >= 0.75 and (best is None or r > best[0]): best = (r, b)
        if best: toc_pairs.append((e, best[1]))
    toc_ids = {id(e) for e, _ in toc_pairs}
    for p in P: p['toc'] = id(p) in toc_ids
    P = [p for p in P if not p['toc']]
    body = [p for p in P if p['kind'] == 'p']
    issues = collections.OrderedDict()                       # 标题 → (严重度, [条目])

    def add(title, sev, items):
        if items: issues[title] = (sev, items)

    tocm = []
    for e, b in toc_pairs:
        le, lb = (e['label'] or e['manual']).strip(), (b['label'] or b['manual']).strip()
        if le and lb and le != lb:
            tocm.append(f"目录“{le}”（p{e['i']}）≠ 正文“{lb}”（p{b['i']}）：{short(b['text'], 40)}")
        ce, cb = cj(e['text']), cj(b['text'])
        if ce and cb and ce != cb:
            tocm.append(f"目录标题“{short(ce, 20)}”与正文标题“{short(cb, 20)}”文字不同（p{e['i']} / p{b['i']}）")
    add('目录与正文不一致（编号或标题文字）', '需处理', tocm)

    # ---------------------------------------------------------- 1 手打编号 / 双重编号
    manual = [p for p in P if p['manual'] and not p['auto'] and p['层级'] in ('章', '条款', '子条款', '列项')]
    add('手打编号（该段没有 Word 自动编号，编号写在文字里）', '需处理',
        [f"{loc(p)} {short(p['text'])}" for p in manual if label_level(p['manual_val'] if p['manual_kind'] != 'dotted' else p['manual']) >= 2
         or p['manual_kind'] in ('dotted',)])
    add('手打字母/数字列项（没用自动编号）', '请核对',
        [f"{loc(p)} {short(p['text'])}" for p in manual if p['manual_kind'] in ('letter', 'paren', 'num_dot', 'num_paren', 'cn_dot', 'di')
         and not (label_level(p['manual']) >= 2)])
    add('双重编号（自动编号 + 文字里又写了编号，会显示两个编号）', '需处理',
        [f"{loc(p)} 自动“{p['label']}”+手打“{p['manual']}” {short(p['body'])}" for p in P
         if p['auto'] and p['manual'] and p['numfmt'] != 'bullet' and p['层级'] != '正文'
         and p['manual_kind'] in ('dotted', 'num_dot', 'di')])

    # ---------------------------------------------------------- 2 序号连续性
    seq_issues = []
    chap = None; clause_seen = collections.defaultdict(list); chap_labels = []
    for p in body:
        k = p['层级']
        lab = (p['label'] if p['auto'] and p['numfmt'] != 'bullet' else '') or p['manual']
        lab = lab.strip().rstrip('.．') if lab else ''
        if k == '章' and lab:
            chap_labels.append((p, lab)); chap = lab
        elif k in ('条款', '子条款') and lab:
            clause_seen[(chap, label_level(lab))].append((p, lab))
            if chap is not None and lab.split('.')[0] != chap:
                seq_issues.append(f"{loc(p)} 编号前缀与所在章（{chap}）不一致：{short(p['text'])}")
    # 章序号
    for (p0, l0), (p1, l1) in zip(chap_labels, chap_labels[1:]):
        if l0.isdigit() and l1.isdigit() and int(l1) != int(l0) + 1:
            seq_issues.append(f"章序号 {l0} → {l1}（{'重复' if int(l1) == int(l0) else '跳号/倒退'}）：{loc(p1)} {short(p1['text'])}")
    # 条款、子条款序号
    for (c, lv), lst in clause_seen.items():
        for (p0, l0), (p1, l1) in zip(lst, lst[1:]):
            a0, a1 = l0.split('.'), l1.split('.')
            if a0[:-1] != a1[:-1]:
                continue
            if int(a1[-1]) != int(a0[-1]) + 1:
                seq_issues.append(f"{l0} → {l1}（{'重复' if int(a1[-1]) == int(a0[-1]) else '跳号/倒退'}）：{loc(p1)} {short(p1['text'])}")
    add('序号不连续 / 重复 / 与所在章不符', '需处理', seq_issues)

    # 空的编号段
    add('空编号段（有编号但没内容）', '需处理',
        [f"{loc(p)}" for p in body if p['auto'] and not p['text'] and p['numfmt'] != 'bullet'])
    # 起点异常
    odd = collections.OrderedDict()
    for p in body:
        if p['auto'] and p['numfmt'] in ('decimal',) and p['ilvl'] == 0 and p['start'] not in (None, 1):
            odd.setdefault(p['numId'], f"编号列表 numId={p['numId']} 起点为 {p['start']}（首个出现在 {loc(p)}）")
    add('编号起点不是 1（可能是故意的，例如 PO 母本章号从 0 开始）', '请核对', list(odd.values()))

    # ---------------------------------------------------------- 3 引用
    label_set = {}
    for p in P:
        labs = []
        if p['auto'] and p['numfmt'] != 'bullet': labs.append(p['label'])
        if p['manual_kind'] == 'dotted': labs.append(p['manual'])
        for lab in labs:
            if lab: label_set.setdefault(lab.strip().rstrip('.．'), p)
    # 章号单独补充（"第5条"这种）
    broken, refs, cross = [], [], []
    plist = [p for p in P if p['text']]
    for idx, p in enumerate(plist):
        found = [(mm.group(0), mm.group(1)) for mm in REF_ZH.finditer(p['text'])] + \
                [(mm.group(0), mm.group(1)) for mm in REF_EN.finditer(p['text'])]
        if not found: continue
        nums = set()
        for raw, n in found:
            nums.add(n)
            tgt = label_set.get(n)
            if tgt is None:
                broken.append(f"{loc(p)} 引用“{raw}”，但文中找不到编号 {n}：{short(p['text'], 50)}")
            else:
                refs.append(f"{loc(p)} “{raw}” → {loc(tgt)} {short(tgt['text'], 40)}")
        # 中英文相邻段落引用是否一致
        for q2 in plist[max(0, idx - 1):idx + 2]:
            if q2 is p or q2['i'] == p['i'] and q2['text'] == p['text']: continue
            if (cjk(q2['text']) > 0.3) == (cjk(p['text']) > 0.3): continue
            n2 = {mm.group(1) for mm in REF_ZH.finditer(q2['text'])} | {mm.group(1) for mm in REF_EN.finditer(q2['text'])}
            if n2 and nums and nums != n2 and p['i'] < q2['i']:
                cross.append(f"{loc(p)} 引用 {sorted(nums)}，相邻的{'中文' if cjk(q2['text']) > 0.3 else '英文'}段 {loc(q2)} 引用 {sorted(n2)}")
    add('引用的条款号在文中不存在', '需处理', broken)
    add('中英文对照段落引用的条款号不一致', '需处理', cross)
    add('全部条款引用（请逐条核对“指向的内容”是否符合语义）', '请核对', refs)

    # ---------------------------------------------------------- 4 待填位
    ph = []
    for p in P:
        if not p['text']: continue
        if p['层级'] == '章' and p['kind'] == 'p' and 'XXX' not in p['text'] and not any(r.search(p['text']) for r, _ in PLACEHOLDER[:3]):
            pass
        for rx, nm in PLACEHOLDER:
            for mm in rx.finditer(p['text']):
                if nm == '日期占位' and not mm.group(0).strip(): continue
                ph.append(f"{loc(p)} {nm}“{short(mm.group(0), 30)}” ← {short(p['text'], 70)}")
                break
    add('疑似待填位 / 可变处（XXX、____、[ ]、【】、（如有）、日期空白…）→ 变量候选', '请核对', ph)

    # ---------------------------------------------------------- 5 文字疑点
    typo = []
    allw = collections.Counter(w.lower() for p in P for w in re.findall(r"[A-Za-z]{2,}", p['text']))
    vocab = {w for w, c in allw.items() if c >= 2 and len(w) >= 4}
    bi = collections.Counter(s[k:k + 2] for p in P for s in re.findall(r'[一-鿿]+', p['text']) for k in range(len(s) - 1))
    for p in P:
        t = p['text']
        if not t: continue
        for mm in re.finditer(r'([一-鿿])\1', t):
            c = mm.group(1); lft = t[mm.start() - 1] + c if mm.start() > 0 else ''; rgt = c + t[mm.end()] if mm.end() < len(t) else ''
            if lft and rgt and bi[lft] >= 3 and bi[rgt] >= 3: continue             # 如“符合合同”“合理理由”：两侧都是常见词，多半正常
            if c not in OK_DOUBLE: typo.append(f"{loc(p)} 汉字重复“{mm.group(0)}”：{short(t[max(0, mm.start() - 8):mm.end() + 10], 30)}")
        for mm in re.finditer(r'([一-鿿]{2,8})和/或\1', t):
            typo.append(f"{loc(p)} “{mm.group(0)}” 前后相同")
        for mm in re.finditer(r'\b([A-Za-z]{2,})\s+\1\b', t, re.I):
            typo.append(f"{loc(p)} 英文词重复“{mm.group(0)}”")
        for mm in re.finditer(r'\b([A-Za-z]{2,}) ([a-z]{1,4})\b', t):
            j = (mm.group(1) + mm.group(2)).lower()
            if j in vocab and allw.get(mm.group(2).lower(), 0) < 3:
                typo.append(f"{loc(p)} 疑似单词被拆开“{mm.group(0)}”（文中另有“{j}”）")
        for o, c, nm in (('（', '）', '全角括号'), ('(', ')', '半角括号'), ('《', '》', '书名号'), ('“', '”', '引号')):
            if t.count(o) != t.count(c): typo.append(f"{loc(p)} {nm}不成对：{short(t, 50)}")
        if re.search(r'[A-Za-z0-9]  +[A-Za-z]', t): pass
    add('文字疑点（重复字词、单词被拆开、括号引号不成对）', '请核对', typo)
    add('句末缺标点（正文超过 60 字、末尾不是句号/分号/冒号）', '请核对',
        [f"{loc(p)} …{p['text'][-20:]}" for p in body if p['层级'] in ('条款', '子条款', '正文', '列项') and len(p['text']) >= 60
         and p['text'][-1] not in SENT_END and not re.search(r'(and|or|and/or|和|或|和/或|以及)$', p['text'].strip(), re.I)])
    add('连续空格（两个及以上，可能是排版用空格）', '请核对',
        [f"{loc(p)} {short(p['text'], 50)}" for p in body if re.search(r'\S {2,}\S', p['text']) and p['层级'] != '章'])

    # ---------------------------------------------------------- 6 结构大纲 / 概览
    L = []
    stl = collections.Counter(p['style'] for p in body if p['text'])
    cnt = collections.Counter(p['层级'] for p in body)
    L += [f"# 母本体检报告：{name}", '',
          f"- 正文段落 {len(body)}（有文字 {sum(1 for p in body if p['text'])}），表格 {len(m['tables'])}，"
          f"未处理修订 {m['stats']['ins'] + m['stats']['del']} 处（插入 {m['stats']['ins']} / 删除 {m['stats']['del']}），批注 {m['stats']['comments']} 条",
          f"- 层级判定：" + '，'.join(f'{k} {v}' for k, v in cnt.items() if k != '空'),
          f"- 使用最多的样式：" + '，'.join(f'{k}×{v}' for k, v in stl.most_common(8)), '']
    L += ['## 问题汇总', '', '| 严重度 | 问题 | 条数 |', '|---|---|---|']
    for t, (sev, items) in issues.items():
        L.append(f'| {sev} | {t} | {len(items)} |')
    L.append('')
    L += ['## 结构大纲（按 Word 实际显示的编号）', '', '| 编号 | 标题 | 位置 | 条款数 |', '|---|---|---|---|']
    heads = [p for p in body if p['层级'] == '章']
    for k, h in enumerate(heads):
        nxt = heads[k + 1]['i'] if k + 1 < len(heads) else 10 ** 9
        nc = sum(1 for p in body if h['i'] < p['i'] < nxt and p['层级'] in ('条款', '子条款'))
        L.append(f"| {h['label'] or h['manual']} | {short(h['text'], 50)} | p{h['i']} | {nc} |")
    if m['tables']:
        L += ['', '## 表格', '', '| 位置 | 行×列 | 首行 |', '|---|---|---|']
        L += [f"| p{t['i']} | {t['rows']}×{t['cols']} | {short(t['first'], 40)} |" for t in m['tables']]
    if m['headers']:
        L += ['', '## 页眉页脚文字', ''] + [f'- {k}: {short(v, 100)}' for k, v in m['headers'].items()]
    L.append('')
    for t, (sev, items) in issues.items():
        L += [f'## 【{sev}】{t}（{len(items)}）', '']
        L += [f'- {x}' for x in items[:(12 if '连续空格' in t else CAP)]]
        if len(items) > CAP: L.append(f'- …… 另有 {len(items) - CAP} 条，见 段落.json / 完整输出')
        L.append('')
    open(os.path.join(out, '体检报告.md'), 'w', encoding='utf-8').write('\n'.join(L))
    json.dump({'paras': P, 'tables': m['tables'], 'headers': m['headers'], 'issues': {k: v[1] for k, v in issues.items()}},
              open(os.path.join(out, '段落.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=0)
    print(f'体检完成：{out}')
    for t, (sev, items) in issues.items():
        print(f'  [{sev}] {t}：{len(items)}')


if __name__ == '__main__':
    main()
