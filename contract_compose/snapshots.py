# -*- coding: utf-8 -*-
"""回归快照：把生成结果转成可比对的文本（tests/snapshots/*.txt）。

快照内容：生成报告（选用写法、未填变量、不适用）+ 每个 Word 部件（正文、编号、样式、页眉页脚）的 SHA-256
+ 正文逐段文字（样式、编号、文字），便于看出差异在哪。
用例：configs/*.yaml、tests/cases/*.yaml，以及每种合同类型的母本回归（--母本）和变量标注版（--标注）。
"""
import os, io, re, glob, hashlib, zipfile
import yaml
from lxml import etree

from . import paths
from .assembler import build
from .library import list_types

SNAP = os.path.join(paths.ROOT, 'tests', 'snapshots')
CASES_DIR = os.path.join(paths.ROOT, 'tests', 'cases')
W = '{http://schemas.openxmlformats.org/wordprocessingml/2006/main}'


def config_files():
    return sorted(glob.glob(os.path.join(paths.CONFIGS, '*.yaml'))) + sorted(glob.glob(os.path.join(CASES_DIR, '*.yaml')))


def cases():
    """[(快照名, 类别, 参数)]；类别：config（配置文件）/ regress（--母本）/ annotate（--标注）"""
    out = [(f'config_{os.path.splitext(os.path.basename(p))[0]}', 'config', p) for p in config_files()]
    for t in list_types():
        out += [(f'regress_{t}', 'regress', t), (f'annotate_{t}', 'annotate', t)]
    return out


def build_case(kind, arg):
    if kind == 'config':
        return build(yaml.safe_load(open(arg, encoding='utf-8')))
    return build({'合同类型': arg}, regress=True, mark_vars=(kind == 'annotate'))


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


def update():
    """重新生成全部快照（全部生成成功后再写），返回有变化的快照名"""
    out = {name: dump(build_case(kind, arg)) for name, kind, arg in cases()}
    os.makedirs(SNAP, exist_ok=True)
    changed = [n for n, t in out.items() if not os.path.exists(snap_path(n)) or open(snap_path(n), encoding='utf-8').read() != t]
    for f in glob.glob(os.path.join(SNAP, '*.txt')):
        if os.path.splitext(os.path.basename(f))[0] not in out: os.remove(f)
    for name, text in out.items():
        open(snap_path(name), 'w', encoding='utf-8').write(text)
    return changed
