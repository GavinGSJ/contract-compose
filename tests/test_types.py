# -*- coding: utf-8 -*-
"""合同类型由 library/<类型>/type.yaml 识别：新增类型只需加内容，不改代码。"""
import os, shutil
import yaml
import pytest

from contract_compose import paths, build, list_types, load_type
from contract_compose.snapshots import dump

CFG = os.path.join(paths.CONFIGS, '示例_FA_防腐油漆.yaml')


def _add_type(x, src, new):
    """内容库数据中，凡按类型区分的写法（{FA: …} 键、适用: [FA]）都给新类型复制一份"""
    if isinstance(x, dict):
        x = {k: _add_type(v, src, new) for k, v in x.items()}
        if src in x: x[new] = x[src]
        if isinstance(x.get('适用'), list) and src in x['适用']: x['适用'] = x['适用'] + [new]
    elif isinstance(x, list):
        x = [_add_type(v, src, new) for v in x]
    return x


def test_types_discovered():
    assert list_types() == ['FA', 'PO']
    assert load_type('PO')['编号起始'] == 0 and load_type('FA')['履约保函条款'] == 'PRI-06'


def test_new_type_without_code_change(lib_copy):
    """复制 FA 为新类型 XX（只改内容库），生成结果应与 FA 完全相同"""
    shutil.copytree(lib_copy / 'FA', lib_copy / 'XX')
    for p in [lib_copy / 'common' / paths.PAYMENT_TERMS] + list((lib_copy / 'common' / paths.OPTIONS).glob('*.yaml')):
        d = yaml.safe_load(open(p, encoding='utf-8'))
        yaml.safe_dump(_add_type(d, 'FA', 'XX'), open(p, 'w', encoding='utf-8'), allow_unicode=True, sort_keys=False)
    assert list_types() == ['FA', 'PO', 'XX']
    cfg = yaml.safe_load(open(CFG, encoding='utf-8'))
    fa = dump(build({**cfg, '合同类型': 'FA'}))
    xx = dump(build({**cfg, '合同类型': 'XX'}))
    assert xx == fa


def test_missing_type_is_clear_error(lib_copy):
    with pytest.raises(SystemExit, match='没有合同类型'):
        build({'合同类型': 'NOPE'})
    os.remove(lib_copy / 'PO' / paths.TYPE_FILE)              # 去掉 type.yaml 即不再是合同类型
    assert list_types() == ['FA']
