# -*- coding: utf-8 -*-
"""回归测试：组装结果必须与 tests/snapshots/ 中的快照逐字一致（快照逻辑见 contract_compose/snapshots.py）。

用法（在项目根目录运行）：
    python -m pytest tests                     # 检查
    python tests/test_regression.py --update   # 有意修改条款/模板后，重新生成快照
"""
import os, sys, difflib

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from contract_compose.snapshots import cases, build_case, dump, snap_path, update   # noqa: E402

import pytest  # noqa: E402


@pytest.mark.parametrize('name,kind,arg', cases(), ids=[c[0] for c in cases()])
def test_snapshot(name, kind, arg):
    p = snap_path(name)
    assert os.path.exists(p), f'缺少快照 {p}，请运行 python tests/test_regression.py --update'
    got = dump(build_case(kind, arg))
    exp = open(p, encoding='utf-8').read()
    if got != exp:
        diff = ''.join(list(difflib.unified_diff(exp.splitlines(True), got.splitlines(True), 'snapshot', 'now'))[:80])
        pytest.fail(f'{name} 与快照不一致：\n{diff}')


if __name__ == '__main__':
    if '--update' not in sys.argv:
        sys.exit(pytest.main([__file__, '-q']))
    print('有变化：', '、'.join(update()) or '无')
