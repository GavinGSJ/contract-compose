# -*- coding: utf-8 -*-
"""条款维护第二步：条款新增 / 移除 / 恢复 / 移动，附件排序 / 默认 / 新增 / 移除，变量管理。全部在内容库副本上进行。"""
import os
import yaml

from contract_compose import paths, load_library, build
from contract_compose import structure as sc, variable_admin as va, maintenance as mt
from contract_compose.snapshots import dump

CFG = os.path.join(paths.CONFIGS, '示例_FA_防腐油漆.yaml')
NOSNAP = {}


def fa():
    return load_library('FA')


def out():
    return dump(build(yaml.safe_load(open(CFG, encoding='utf-8'))))


def no(aid):
    return {r['id']: r['no'] for r in mt.items(fa(), '条款')}[aid]


def test_insert_clause_and_subclause(lib_copy, monkeypatch):
    monkeypatch.setattr('contract_compose.snapshots.SNAP', str(lib_copy.parent / 'snap'))
    assert no('QUA-04') == '3.4'
    r = sc.insert_atom(fa(), 'QUA-02', '条款', '新增测试条款', '## 新增测试条款\n\n测试正文。', reason='测试')
    assert r['ok'], r
    assert r['id'] == 'QUA-05' and no('QUA-05') == '3.3' and no('QUA-04') == '3.5'   # 后面的条款号自动顺延
    assert '新增测试条款' in out()
    r = sc.insert_atom(fa(), 'QUA-05', '子条款', '子条款测试')
    assert r['ok'] and r['id'] == 'QUA-05-1' and no('QUA-05-1') == '3.3.1'
    log = open(lib_copy / 'FA' / '修订记录.md', encoding='utf-8').read()
    assert '新增条款 3.3 新增测试条款（QUA-05）：测试' in log
    assert not sc.insert_atom(fa(), 'QUA-00', '子条款', 'x')['ok']           # 子条款不能直接放在章标题后


def test_insert_chapter(lib_copy, monkeypatch):
    monkeypatch.setattr('contract_compose.snapshots.SNAP', str(lib_copy.parent / 'snap'))
    assert not sc.insert_atom(fa(), 'QUA-04', '章', '新章', code='QUA')['ok']   # 章代码已被使用
    r = sc.insert_atom(fa(), 'QUA-04', '章', '测试章', code='TST')
    assert r['ok'], r
    assert no('TST-00') == '4' and no('PRI-00') == '5'


def test_remove_and_readd(lib_copy, monkeypatch):
    monkeypatch.setattr('contract_compose.snapshots.SNAP', str(lib_copy.parent / 'snap'))
    r = sc.remove_atom(fa(), 'QUA-03')                                       # 被 3.4 引用，不能移除
    assert not r['ok'] and '引用' in r['message']
    assert not sc.remove_atom(fa(), 'QUA-00')['ok']                          # 章下面还有条款
    assert not sc.remove_atom(fa(), 'PRI-02')['ok']                          # 付款条款
    r = sc.remove_atom(fa(), 'QUA-01', reason='测试移除')
    assert r['ok'], r
    assert no('QUA-01') == mt.UNUSED and no('QUA-02') == '3.1'
    assert os.path.exists(mt.path_of(fa(), '条款', 'QUA-01'))               # 文件保留
    r = sc.readd_atom(fa(), 'QUA-01', 'QUA-00')
    assert r['ok'], r
    assert no('QUA-01') == '3.1'


def test_move(lib_copy, monkeypatch):
    monkeypatch.setattr('contract_compose.snapshots.SNAP', str(lib_copy.parent / 'snap'))
    assert not sc.move_atom(fa(), 'QUA-01', 'up')['ok']                      # 本章第一个
    r = sc.move_atom(fa(), 'QUA-02', 'up')
    assert r['ok'] and no('QUA-02') == '3.1' and no('QUA-01') == '3.2'
    r = sc.move_atom(fa(), 'QUA-02', 'down')
    assert r['ok'] and no('QUA-02') == '3.2'
    r = sc.move_atom_after(fa(), 'QUA-02', 'PRI-07')                         # 跨章移动：所属章自动更新
    assert r['ok'], r
    assert no('QUA-02').startswith('4.') and fa().atoms['QUA-02']['meta']['章'] == fa().atoms['PRI-00']['meta']['章']
    r = sc.move_atom(fa(), 'QUA-00', 'down')                                 # 整章移动
    assert r['ok'] and no('QUA-00') == '4' and no('PRI-00') == '3'


def test_recipe_keeps_comments_and_conditions(lib_copy, monkeypatch):
    monkeypatch.setattr('contract_compose.snapshots.SNAP', str(lib_copy.parent / 'snap'))
    before = open(lib_copy / 'FA' / 'recipe.yaml', encoding='utf-8').read()
    assert sc.move_atom(fa(), 'QUA-02', 'up')['ok'] and sc.move_atom(fa(), 'QUA-02', 'down')['ok']
    assert open(lib_copy / 'FA' / 'recipe.yaml', encoding='utf-8').read() == before   # 移回原位，配方逐字相同


def test_annexes(lib_copy, monkeypatch):
    monkeypatch.setattr('contract_compose.snapshots.SNAP', str(lib_copy.parent / 'snap'))
    r = sc.move_annex(fa(), 'ANX-RETURN', 'down')
    assert r['ok'], r
    assert list(fa().annexes)[9] == 'ANX-RETURN' and '附件十 主合同相关要求' in out()
    assert not sc.set_annex_default(fa(), 'ANX-TA', False)['ok']             # 技术协议随变量
    assert sc.set_annex_default(fa(), 'ANX-HSE', False)['ok'] and fa().annexes['ANX-HSE']['meta']['默认'] == '无'
    r = sc.add_annex(fa(), 'ANX-INTEGRITY', '保密协议', 'Non-Disclosure Agreement', typ='文件')
    assert r['ok'], r
    assert list(fa().annexes)[8] == r['id']
    assert not sc.remove_annex(fa(), 'ANX-TA')['ok']                         # 被条款引用
    assert sc.remove_annex(fa(), r['id'])['ok'] and r['id'] in sc.unused_annexes(fa())


def test_variables(lib_copy, monkeypatch):
    monkeypatch.setattr('contract_compose.snapshots.SNAP', str(lib_copy.parent / 'snap'))
    rows = {r['name']: r for r in va.rows(fa())}
    assert any(u.startswith('3.4') for u in rows['涂层质保月数']['用在'])
    r = va.set_default(fa(), '涂层质保月数', '36', reason='测试')
    assert r['ok'], r
    assert fa().V['涂层质保月数']['默认值'] == '36'
    r = va.set_default(fa(), '付款天数', '45', scope='type')                 # 共用变量只改本类型
    assert r['ok'] and fa().V['付款天数']['默认值'] == '45' and load_library('PO').V['付款天数']['默认值'] != '45'
    text = '若法律规定的质保期'
    before = out()
    r = va.make_variable(fa(), '条款', 'QUA-04', text, '质保依据说明')
    assert r['ok'], r
    assert '{{质保依据说明}}' in fa().atoms['QUA-04']['body'] and fa().V['质保依据说明']['默认值'] == text
    assert out().split('---- 正文 ----')[1] == before.split('---- 正文 ----')[1]   # 默认值为原文，合同文字不变
    assert not va.make_variable(fa(), '条款', 'QUA-04', '找不到的文字', 'x')['ok']
    assert not va.make_variable(fa(), '条款', 'QUA-04', '质量保证期', 'a b')['ok']
