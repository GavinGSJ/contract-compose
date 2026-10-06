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
