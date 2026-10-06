# 让测试能 import contract_compose（项目根目录加入 sys.path）
import os, sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


import shutil
import pytest


@pytest.fixture
def lib_copy(tmp_path, monkeypatch):
    """内容库的临时副本（样式模板也复制），程序读写都指向副本；不影响真实的 library/"""
    from contract_compose import paths
    lib = tmp_path / 'library'
    shutil.copytree(paths.LIBRARY, lib, ignore=shutil.ignore_patterns('*.docx', 'reference', 'backups'))
    for t in ('FA', 'PO'):                                   # 样式模板要保留
        shutil.copytree(os.path.join(paths.type_dir(t), 'templates'), lib / t / 'templates', dirs_exist_ok=True)
    monkeypatch.setattr(paths, 'LIBRARY', str(lib))
    monkeypatch.setattr(paths, 'COMMON', str(lib / 'common'))
    monkeypatch.setattr(paths, 'PRESETS', str(lib / 'common' / 'presets'))
    monkeypatch.setattr(paths, 'PRESET_BACKUPS', str(tmp_path / 'backups'))
    monkeypatch.setattr(paths, 'CONTENT_BACKUPS', str(tmp_path / 'content_backups'))
    return lib
