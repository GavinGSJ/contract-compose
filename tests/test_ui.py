# -*- coding: utf-8 -*-
"""表单冒烟测试：两个页面、两种合同类型都能正常渲染（不点“生成合同”，不写文件）。"""
import os
from streamlit.testing.v1 import AppTest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
APP = os.path.join(ROOT, 'app.py')


def _run(at):
    at.run(timeout=60)
    assert not at.exception, [e.value for e in at.exception]
    return at


def test_contract_page_each_type():
    at = _run(AppTest.from_file(APP))
    types = at.selectbox(key='ctype').options
    assert len(types) >= 2
    for t in types:
        at.selectbox(key='ctype').set_value(t)
        _run(at)
        assert at.button[0].label == '生成合同'


def test_open_saved_config():
    at = _run(AppTest.from_file(APP))
    saved = [x for x in at.selectbox(key='cfg_file').options if x != '（新合同）']
    assert saved
    for f in saved:
        at.selectbox(key='cfg_file').set_value(f)
        _run(at)
        _run(at)


def test_generate_from_saved_config(tmp_path, monkeypatch):
    """打开示例配置并点“生成合同”：配置与 Word 写到临时目录，生成结果与命令行一致"""
    import glob, shutil, yaml
    from contract_compose import paths
    cfg_dir, out_dir = tmp_path / 'configs', tmp_path / 'output'
    shutil.copytree(paths.CONFIGS, cfg_dir)
    monkeypatch.setattr(paths, 'CONFIGS', str(cfg_dir))
    monkeypatch.setattr(paths, 'OUTPUT', str(out_dir))
    at = _run(AppTest.from_file(APP))
    for f in [x for x in at.selectbox(key='cfg_file').options if x != '（新合同）']:
        at.selectbox(key='cfg_file').set_value(f)
        _run(at); _run(at)
        at.button[0].click()
        _run(at)
        assert any('已生成' in s.value for s in at.success)
    assert len(glob.glob(str(out_dir / '*.docx'))) >= 2
    saved = [p for p in glob.glob(str(cfg_dir / '*.yaml')) if open(p, encoding='utf-8').read().startswith('# 由表单保存')]
    assert sorted(yaml.safe_load(open(p, encoding='utf-8'))['合同类型'] for p in saved) == ['FA', 'PO']


def test_presets_page():
    at = _run(AppTest.from_file(APP))
    at.switch_page(os.path.join(ROOT, PRESET_PAGE))
    _run(at)
    assert any('预存信息管理' in h.value for h in at.header)


PRESET_PAGE = os.path.join('ui', 'preset_manager.py')


def test_annex_tab(tmp_path, monkeypatch):
    """④ 合同附件：取消勾选的附件写入配置为“无”；技术协议随“本合同有技术协议”"""
    import glob, yaml
    from contract_compose import paths
    monkeypatch.setattr(paths, 'CONFIGS', str(tmp_path / 'configs'))
    monkeypatch.setattr(paths, 'OUTPUT', str(tmp_path / 'output'))
    (tmp_path / 'configs').mkdir()
    at = _run(AppTest.from_file(APP))
    assert at.checkbox(key='ax::ANX-TA').disabled and at.checkbox(key='ax::ANX-TA').value
    at.checkbox(key='ta').uncheck(); _run(at)
    assert not at.checkbox(key='ax::ANX-TA').value
    at.checkbox(key='ax::ANX-HSE').uncheck(); _run(at)
    at.button[0].click(); _run(at)
    cfg = yaml.safe_load(open(glob.glob(str(tmp_path / 'configs' / '*.yaml'))[0], encoding='utf-8'))
    assert cfg['附件']['ANX-HSE'] == '无' and cfg['附件']['ANX-DOCS'] == '有' and 'ANX-TA' not in cfg['附件']
    assert cfg['变量']['有技术协议'] == '否'


def test_clause_editor(lib_copy, tmp_path, monkeypatch):
    """条款维护：查找 → 修改 → 对比 → 保存（写入临时副本）→ 历史版本恢复"""
    from contract_compose import snapshots, load_library
    monkeypatch.setattr(snapshots, 'SNAP', str(tmp_path / 'snapshots'))
    at = _run(AppTest.from_file(APP))
    at.switch_page(os.path.join(ROOT, 'ui', 'clause_editor.py')); _run(at)
    at.text_input(key='ed::kw').input('质量保证'); _run(at)
    at.radio(key='ed::sel::FA::条款').set_value('QUA-04'); _run(at)
    bk = 'ed::body::FA::条款::QUA-04'
    old = at.text_area(key=bk).value
    at.text_area(key=bk).input(old.replace('具体要求以技术协议为准', '具体要求以技术协议为准（页面测试）')); _run(at)
    assert any('页面测试' in m.value for m in at.markdown)              # 修改对比
    at.text_input(key='ed::reason::FA::条款::QUA-04').input('页面测试'); _run(at)
    next(b for b in at.button if b.label == '保存').click(); _run(at)
    assert any('已保存' in s.value for s in at.success), [e.value for e in at.error]
    assert '页面测试' in load_library('FA').atoms['QUA-04']['body']
    next(b for b in at.button if b.label == '恢复此版本').click(); _run(at)
    assert load_library('FA').atoms['QUA-04']['body'] == old
    assert len(list((tmp_path / 'snapshots').glob('*.txt'))) > 0      # 快照写到了临时目录


def test_clause_editor_rejects_unknown_variable(lib_copy):
    at = _run(AppTest.from_file(APP))
    at.switch_page(os.path.join(ROOT, 'ui', 'clause_editor.py')); _run(at)
    sel = at.radio(key='ed::sel::FA::条款').value
    bk = f'ed::body::FA::条款::{sel}'
    at.text_area(key=bk).input(at.text_area(key=bk).value + '\n\n{{没有这个变量}}'); _run(at)
    assert any('变量字典' in e.value for e in at.error)
    assert next(b for b in at.button if b.label == '保存').disabled


def _editor(lib_copy, tmp_path, monkeypatch):
    from contract_compose import snapshots
    monkeypatch.setattr(snapshots, 'SNAP', str(tmp_path / 'snapshots'))
    at = _run(AppTest.from_file(APP))
    at.switch_page(os.path.join(ROOT, 'ui', 'clause_editor.py'))
    return _run(at)


def _click(at, label):
    next(b for b in at.button if b.label == label).click()
    return _run(at)


def test_editor_insert_move_remove(lib_copy, tmp_path, monkeypatch):
    from contract_compose import load_library, maintenance as mt
    no = lambda a: {r['id']: r['no'] for r in mt.items(load_library('FA'), '条款')}[a]
    at = _editor(lib_copy, tmp_path, monkeypatch)
    at.text_input(key='ed::kw').input('质量要求'); _run(at)
    at.radio(key='ed::sel::FA::条款').set_value('QUA-01'); _run(at)
    at.text_input(key='ed::newname::FA::QUA-01').input('页面新增条款'); _run(at)
    _click(at, '新增')
    assert any('已新增条款' in s.value for s in at.success), [e.value for e in at.error]
    assert at.radio(key='ed::sel::FA::条款').value == 'QUA-05'           # 自动跳到新条款
    assert no('QUA-05') == '3.2'
    _click(at, '⬇ 下移')
    assert no('QUA-05') == '3.3'
    at.checkbox(key='ed::confirm::FA::条款::QUA-05').check(); _run(at)
    _click(at, '移除')
    assert no('QUA-05') == mt.UNUSED


def test_editor_make_variable_and_default(lib_copy, tmp_path, monkeypatch):
    from contract_compose import load_library
    at = _editor(lib_copy, tmp_path, monkeypatch)
    at.text_input(key='ed::kw').input('质量保证'); _run(at)
    at.radio(key='ed::sel::FA::条款').set_value('QUA-04'); _run(at)
    at.text_input(key='ed::mvtext::FA::条款::QUA-04').input('具体要求以技术协议为准'); _run(at)
    at.text_input(key='ed::mvname::FA::条款::QUA-04').input('涂层质保依据'); _run(at)
    _click(at, '改成变量')
    assert any('改为变量' in s.value for s in at.success), [e.value for e in at.error]
    assert '{{涂层质保依据}}' in load_library('FA').atoms['QUA-04']['body']
    at.radio(key='ed::kind').set_value('变量'); _run(at)
    at.text_input(key='ed::kw').input('涂层质保依据'); _run(at)
    at.text_input(key='ed::vdefault::FA::涂层质保依据').input('具体要求以技术协议及附件为准'); _run(at)
    _click(at, '保存')
    assert load_library('FA').V['涂层质保依据']['默认值'] == '具体要求以技术协议及附件为准'


def test_editor_annex_order(lib_copy, tmp_path, monkeypatch):
    from contract_compose import load_library
    at = _editor(lib_copy, tmp_path, monkeypatch)
    at.radio(key='ed::kind').set_value('附件'); _run(at)
    at.radio(key='ed::sel::FA::附件').set_value('ANX-RETURN'); _run(at)
    _click(at, '⬇ 下移')
    assert list(load_library('FA').annexes)[9] == 'ANX-RETURN'
    assert at.radio(key='ed::sel::FA::附件').value == 'ANX-RETURN'
