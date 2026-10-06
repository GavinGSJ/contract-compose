# -*- coding: utf-8 -*-
"""回归测试：组装结果必须与 tests/snapshots/ 中的快照逐字一致。

用法（在项目根目录运行）：
    python -m pytest tests            # 检查
    python tests/test_regression.py --update   # 有意修改条款/模板后，重新生成快照

快照内容：生成报告（选用写法、未填变量、不适用）+ 每个 Word 部件（正文、编号、页眉页脚）的 SHA-256
+ 正文逐段文字（样式、编号、文字），便于看出差异在哪。
"""
import os, sys, io, re, glob, hashlib, zipfile
import yaml
from lxml import etree

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SNAP = os.path.join(ROOT, 'tests', 'snapshots')
CASES_DIR = os.path.join(ROOT, 'tests', 'cases')
W = '{http://schemas.openxmlformats.org/wordprocessingml/2006/main}'


# ---------------- 用例 ----------------


def _config_files():
    return sorted(glob.glob(os.path.join(ROOT, 'configs', '*.yaml'))) + sorted(glob.glob(os.path.join(CASES_DIR, '*.yaml')))


def build_case(kind, arg):
    """kind: config（合同配置文件）/ regress（--母本）/ annotate（--标注）。返回 (doc, used, missing, order, na)"""
    from contract_compose import build
    if kind == 'config':
        return build(yaml.safe_load(open(arg, encoding='utf-8')))
    return build({'合同类型': arg}, regress=True, mark_vars=(kind == 'annotate'))


# ---------------- 快照 ----------------
def cases():
    out = [(f'config_{os.path.splitext(os.path.basename(p))[0]}', 'config', p) for p in _config_files()]
    for t in ('FA', 'PO'):
        out += [(f'regress_{t}', 'regress', t), (f'annotate_{t}', 'annotate', t)]
    return out


def _text(e):
    s = []
    for x in e.iter(W + 't', W + 'tab', W + 'br'):
        s.append((x.text or '') if x.tag == W + 't' else ('\t' if x.tag == W + 'tab' else '⏎'))
    return ''.join(s)


def dump(result):
    doc, used, missing, order, na = result
    buf = io.BytesIO(); doc.save(buf)
    z = zipfile.ZipFile(buf)
    parts = sorted(n for n in z.namelist() if re.fullmatch(r'word/(document|numbering|styles|header\d*|footer\d*)\.xml', n))
    L = ['选用的写法：' + '、'.join(f'{k}={v}' for k, v in used.items()),
         '未填变量：' + '、'.join(sorted(missing)),
         f'条款原子：{len(order)}',
         '标注不适用：' + '、'.join(na), '']
    L += [f'sha256 {n}: {hashlib.sha256(z.read(n)).hexdigest()}' for n in parts]
    L += ['', '---- 正文 ----']
    body = etree.fromstring(z.read('word/document.xml')).find(W + 'body')
    for e in body:
        if e.tag == W + 'p':
            st = e.find(f'{W}pPr/{W}pStyle'); num = e.find(f'{W}pPr/{W}numPr')
            tag = st.get(W + 'val') if st is not None else ''
            if num is not None:
                tag += f"#{num.find(W + 'numId').get(W + 'val')}.{num.find(W + 'ilvl').get(W + 'val')}"
            L.append(f'[{tag}] {_text(e)}')
        elif e.tag == W + 'tbl':
            for tr in e.iter(W + 'tr'):
                L.append('[表] ' + ' | '.join(_text(tc) for tc in tr.iter(W + 'tc')))
    return '\n'.join(L) + '\n'


def snap_path(name):
    return os.path.join(SNAP, name + '.txt')


# ---------------- pytest ----------------
import pytest


@pytest.mark.parametrize('name,kind,arg', cases(), ids=[c[0] for c in cases()])
def test_snapshot(name, kind, arg):
    p = snap_path(name)
    assert os.path.exists(p), f'缺少快照 {p}，请运行 python tests/test_regression.py --update'
    got = dump(build_case(kind, arg))
    exp = open(p, encoding='utf-8').read()
    if got != exp:
        import difflib
        diff = ''.join(list(difflib.unified_diff(exp.splitlines(True), got.splitlines(True), 'snapshot', 'now'))[:80])
        pytest.fail(f'{name} 与快照不一致：\n{diff}')


if __name__ == '__main__':
    if '--update' not in sys.argv:
        sys.exit(pytest.main([__file__, '-q']))
    sys.path.insert(0, ROOT)                       # 直接运行本文件时也能 import contract_compose
    out = {name: dump(build_case(kind, arg)) for name, kind, arg in cases()}   # 全部生成成功后再写
    os.makedirs(SNAP, exist_ok=True)
    for f in glob.glob(os.path.join(SNAP, '*.txt')): os.remove(f)
    for name, text in out.items():
        open(snap_path(name), 'w', encoding='utf-8').write(text)
        print('已更新', name)
