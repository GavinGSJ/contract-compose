# -*- coding: utf-8 -*-
"""表单运行期间更新代码：能识别进程中的旧模块并重新加载。"""
import os, sys, time, types

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from ui.stale import stale  # noqa: E402


def test_stale(tmp_path):
    (tmp_path / 'a.py').write_text('x = 1')
    assert not stale(None, str(tmp_path))                                  # 尚未加载
    assert stale(types.SimpleNamespace(), str(tmp_path))                   # 旧版模块（没有加载时间）
    fresh = types.SimpleNamespace(LOADED_AT=time.time() + 5)
    assert not stale(fresh, str(tmp_path))                                 # 加载后代码没变
    old = types.SimpleNamespace(LOADED_AT=time.time() - 60)
    assert stale(old, str(tmp_path))                                       # 加载后代码更新了


def test_current_package_not_stale():
    import contract_compose
    from contract_compose import paths
    assert not stale(contract_compose, os.path.dirname(paths.__file__))
