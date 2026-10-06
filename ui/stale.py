# -*- coding: utf-8 -*-
"""判断进程中已加载的 contract_compose 是否比磁盘上的代码旧（表单运行期间更新了代码时）。"""
import os, sys, glob


def stale(pkg, src_dir):
    """pkg 为已加载的 contract_compose 模块（未加载为 None）"""
    if pkg is None:
        return False
    loaded = getattr(pkg, 'LOADED_AT', None)
    if loaded is None:                                   # 旧版代码加载的模块没有加载时间：一定是旧的
        return True
    files = glob.glob(os.path.join(src_dir, '*.py'))
    return bool(files) and max(os.path.getmtime(p) for p in files) > loaded


def purge():
    """清掉已加载的 contract_compose 及其子模块，下次导入时读取磁盘上的新代码"""
    for name in [m for m in sys.modules if m == 'contract_compose' or m.startswith('contract_compose.')]:
        del sys.modules[name]
