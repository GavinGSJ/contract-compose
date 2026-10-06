# -*- coding: utf-8 -*-
"""条款维护：列表、检查、预览、保存（备份 + 修订记录 + 试生成）、历史与恢复。"""
import glob, os
import yaml

from contract_compose import paths, load_library, build
from contract_compose import maintenance as mt
from contract_compose.snapshots import dump

CFG = os.path.join(paths.CONFIGS, '示例_FA_防腐油漆.yaml')


def test_files_round_trip():
    """不改内容时，读出再写回与原文件完全相同（保存不会带来格式噪声）"""
    for p in glob.glob(os.path.join(paths.LIBRARY, '*', 'atoms', '*.md')) + glob.glob(os.path.join(paths.LIBRARY, '*', 'annexes', '*.md')):
        text = open(p, encoding='utf-8').read()
        assert mt.join_file(*mt.split_file(text)) == text, p


def test_items_and_chapters():
    lib = load_library('FA')
    rows = mt.items(lib, '条款')
    assert len(rows) == len(lib.atoms) and rows[0]['no'] == '1'
    q = next(r for r in rows if r['id'] == 'QUA-04')
    assert q['no'] == '3.4'
    assert [r['id'] for r in mt.search(rows, '质量保证')][:1]
    chs = mt.chapters(rows)
    assert chs[0][0] == '1' and sum(len(c[2]) for c in chs) == len(rows)
    ax = mt.items(lib, '附件')
    assert ax[9]['no'] == '附件十' and ax[9]['id'] == 'ANX-SPECIAL'


def test_check():
    lib = load_library('FA')
    body = lib.atoms['QUA-04']['body']
    assert mt.check(lib, '条款', 'QUA-04', body) == ([], [])
    err, _ = mt.check(lib, '条款', 'QUA-04', body + '\n\n新增{{不存在的变量}}和{{ref:NOPE}}和{{附件:NOPE}}')
    assert len(err) == 3
    err, _ = mt.check(lib, '条款', 'QUA-04', body + '{{涂层质保月数')
    assert err
    _, warn = mt.check(lib, '条款', 'QUA-04', body.replace('## ', '', 1))
    assert any('首行标记' in w for w in warn)


def test_preview_and_diff():
    lib = load_library('FA')
    h = mt.preview_html(lib, '条款', 'QUA-04', lib.atoms['QUA-04']['body'])
    assert '3.4 ' in h and 'background:#dbeafe' in h            # 编号、变量默认值高亮
    d = mt.diff_html('质保期为12个月。', '质保期为24个月。')
    assert '<del' in d and '<ins' in d and '24' in d


def test_save_history_restore(lib_copy):
    lib = load_library('FA')
    old = lib.atoms['QUA-04']['body']
    new = old.replace('具体要求以技术协议为准', '具体要求以技术协议为准（维护测试）')
    assert new != old
    r = mt.save(lib, '条款', 'QUA-04', new, reason='测试修改', update_snapshots=False)
    assert r['ok'], r
    lib2 = load_library('FA')
    assert lib2.atoms['QUA-04']['body'] == new
    assert '维护测试' in dump(build(yaml.safe_load(open(CFG, encoding='utf-8'))))
    log = open(lib_copy / 'FA' / '修订记录.md', encoding='utf-8').read()
    assert mt.LOG_HEAD in log and '3.4 质量保证（QUA-04）：测试修改' in log
    hist = mt.history(lib2, '条款', 'QUA-04')
    assert len(hist) == 1
    r = mt.restore(lib2, '条款', 'QUA-04', hist[0][1])
    assert r['ok'], r
    assert load_library('FA').atoms['QUA-04']['body'] == old
    assert mt.save(load_library('FA'), '条款', 'QUA-04', old, update_snapshots=False)['message'] == '内容没有变化'


def test_save_rename_and_reject(lib_copy):
    lib = load_library('FA')
    r = mt.save(lib, '附件', 'ANX-RETURN', lib.annexes['ANX-RETURN']['body'], name='退货和回购条款', update_snapshots=False)
    assert r['ok'], r
    assert load_library('FA').annexes['ANX-RETURN']['meta']['名称'] == '退货和回购条款'
    r = mt.save(load_library('FA'), '条款', 'QUA-04', '## 质量保证 {{没有这个变量}}', update_snapshots=False)
    assert not r['ok'] and '变量字典' in r['message']
