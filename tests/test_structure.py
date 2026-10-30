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


def test_heading_style_and_compose_body():
    """三种合同类型的条款都是：条款号后面直接是条款正文（## 后面就是第一段），再接其余段落；每段长度多为几十到几百字"""
    assert sc.heading_style(fa()) == sc.heading_style(load_library('PO')) == '正文'
    s416 = load_library('S416')
    assert sc.heading_style(s416) == '正文'
    assert sc.compose_body(fa(), '条款', '质保延期', '第一段。\n\n第二段。', style='标题') == '## 质保延期\n\n第一段。\n\n第二段。'     # 另一种写法：标题 + 正文
    assert sc.compose_body(fa(), '条款', '质保延期', '第一段。\n\n第二段。') == '## 第一段。\n\n第二段。'
    assert sc.compose_body(s416, '条款', '质保延期', '第一段。\n\n第二段。\n\n- 列项') == '## 第一段。\n\n第二段。\n\n- 列项'
    assert sc.compose_body(s416, '子条款', '名称', '只有一段。') == '### 只有一段。'
    assert sc.compose_body(s416, '章', '售后服务', '') == '# 售后服务'
    assert sc.compose_body(s416, '条款', '名称', '## 已经带标记\n\n原样使用') == '## 已经带标记\n\n原样使用'


def test_new_clause_registers_new_variables(lib_copy, monkeypatch):
    """新增条款时正文里的新变量一并登记（本类型专属 / 共用）；没有默认值的为必填"""
    monkeypatch.setattr('contract_compose.snapshots.SNAP', str(lib_copy.parent / 'snap'))
    body = '## 质保延期\n\n质保期届满前{{延期通知天数}}天内，由{{延期联系人}}书面通知买方。'
    r = sc.insert_atom(fa(), 'QUA-02', '条款', '质保延期', body, reason='测试',
                       variables=[{'name': '延期通知天数', 'default': '30', 'desc': '提前几天通知', 'scope': 'type'},
                                  {'name': '延期联系人', 'default': '', 'desc': '', 'scope': 'common'}])
    assert r['ok'], r
    V = fa().V
    assert V['延期通知天数']['默认值'] == '30' and V['延期通知天数']['类别'] == '有默认值' and V['延期通知天数']['原子'] == [r['id']]
    assert V['延期联系人']['类别'] == '必填' and va.defined_in(fa(), '延期联系人') == '共用' and va.defined_in(fa(), '延期通知天数') == '本类型'
    assert '新建变量 延期通知天数、延期联系人' in open(lib_copy / 'FA' / '修订记录.md', encoding='utf-8').read()
    out_text = out()
    assert '质保期届满前30天内' in out_text                                       # 有默认值：直接出现在合同中
    # 没有登记的变量、不合法的变量名都不能保存
    assert not sc.insert_atom(fa(), 'QUA-02', '条款', 'x', '## x\n\n{{没登记的变量}}')['ok']
    bad = sc.insert_atom(fa(), 'QUA-02', '条款', 'x', '## x\n\n{{a/b}}', variables=[{'name': 'a/b'}])
    assert not bad['ok'] and '不合法' in bad['message']


def test_free_chapter_code_and_auto_code(lib_copy, monkeypatch):
    monkeypatch.setattr('contract_compose.snapshots.SNAP', str(lib_copy.parent / 'snap'))
    assert sc.free_chapter_code(fa()) == 'CHA'
    r = sc.insert_atom(fa(), 'QUA-04', '章', '自动代码章')                           # 不填章代码：自动 CHA
    assert r['ok'] and r['id'] == 'CHA-00' and sc.free_chapter_code(fa()) == 'CHB'


def test_unknown_variables_and_save_with_variables(lib_copy, monkeypatch):
    monkeypatch.setattr('contract_compose.snapshots.SNAP', str(lib_copy.parent / 'snap'))
    lib = fa()
    body = lib.atoms['QUA-04']['body'] + '\n\n补充：{{新增质保说明}}，{{ref:QUA-01}}，{{中文数字:另一个新变量}}。'
    assert mt.unknown_variables(lib, body) == ['新增质保说明', '另一个新变量']
    errors, _ = mt.check(lib, '条款', 'QUA-04', body)
    assert errors and not mt.check(lib, '条款', 'QUA-04', body, known=['新增质保说明', '另一个新变量'])[0]
    r = mt.save(lib, '条款', 'QUA-04', body, reason='测试', variables=[{'name': '新增质保说明', 'default': '见技术协议'},
                                                                   {'name': '另一个新变量', 'default': '5'}])
    assert r['ok'], r
    assert '新增质保说明' in fa().V and '新建变量 新增质保说明、另一个新变量' in open(lib_copy / 'FA' / '修订记录.md', encoding='utf-8').read()
    assert not mt.save(fa(), '条款', 'QUA-04', body + '{{又一个新变量}}', reason='x')['ok']          # 没登记不能保存
