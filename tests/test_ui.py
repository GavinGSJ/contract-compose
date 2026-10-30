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
    shutil.copy(os.path.join(ROOT, 'tests', 'cases', 'S416_材料.yaml'), cfg_dir / '测试_S416_材料.yaml')     # 材料类：含重量列、另加附件等
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
    cfgs = sorted((yaml.safe_load(open(p, encoding='utf-8')) for p in saved), key=lambda c: c['合同类型'])
    assert [c['合同类型'] for c in cfgs] == ['FA', 'PO', 'S416', 'S416']
    mat, eq = sorted(cfgs[2:], key=lambda c: c['选项']['物资类别'])    # 材料、设备（按字符顺序）
    assert [g['产品名称'] for g in eq['货物']] == ['货油泵', '压载泵'] and [g['数量'] for g in eq['货物']] == ['2', '3']
    assert '付款方式' not in eq['选项'] and '有技术协议' not in eq['变量'] and eq['选项']['付款方案'] == '预付款+到货款+调试款'
    assert eq['选项']['交货期方式'] == '天数+最晚日期' and eq['变量']['交货期数量'] == '180' and eq['变量']['交货日期'] == '2027年3月31日'
    assert mat['货物'][0]['重量'] == '84000' and mat['货物'][0]['总金额'] == '672003.50'       # 重量列、手填总金额保留
    assert mat['选项']['付款方案'] == '到货款一次付清' and mat['选项']['交货期单位'] == '周' and mat['变量']['交货期数量'] == '6'
    assert mat['变量']['到货款比例'] == '100' and '预付款比例' not in mat['变量']           # 到货款一次付清：只有到货款比例
    assert mat['自定义附件'] == [{'名称': '技术协议（签字盖章版）', '名称_en': 'Technical Agreement (Signed and Sealed)'}]
    assert mat['附件']['ANX-NDA'] == '无' and mat['附件']['ANX-MINUTES'] == '有'


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
    base = at.text_area(key=bk).value
    at.text_area(key=bk).input(base + '\n\n{{没有这个变量}}'); _run(at)           # 合法的新变量：提示登记，可以保存
    assert any('正文里用到了新变量' in m.value for m in at.markdown)
    assert not next(b for b in at.button if b.label == '保存').disabled
    at.text_area(key=bk).input(base + '\n\n{{a b}}'); _run(at)                  # 名称不合法：不能保存
    assert any('不合法' in e.value for e in at.error)
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


def test_s416_form_blocks(tmp_path, monkeypatch):
    """S416 表单：付款方案、交货期随选项显示变量；切换写法时未改动的比例换成新写法的初始值；生成后配置正确"""
    import glob, yaml
    from contract_compose import paths
    monkeypatch.setattr(paths, 'CONFIGS', str(tmp_path / 'configs'))
    monkeypatch.setattr(paths, 'OUTPUT', str(tmp_path / 'output'))
    (tmp_path / 'configs').mkdir()
    at = _run(AppTest.from_file(APP))
    at.selectbox(key='ctype').set_value('S416'); _run(at)
    keys = lambda: {t.key for t in at.text_input}
    pay = lambda n: next(o for o in at.radio(key='o::付款方案').options if o.replace(' ', '') == n)
    assert at.radio(key='o::物资类别').value == '设备类'
    assert at.radio(key='o::付款方案').value == '到货款 + 质保金'                    # 默认方案：到货款 95% + 质保金 5%
    assert at.text_input(key='v::到货款比例').value == '95' and at.text_input(key='v::质保比例').value == '5'
    assert at.text_input(key='v::付款天数').value == '60' and at.text_input(key='v::质保金_释放天数').value == '30'
    assert 'v::预付款比例' not in keys() and 'v::调试款比例' not in keys()
    at.radio(key='o::付款方案').set_value(pay('预付款+到货款+调试款')); _run(at)
    assert at.text_input(key='v::到货款比例').value == '50' and at.text_input(key='v::调试款比例').value == '40'
    at.radio(key='o::付款方案').set_value(pay('到货款一次付清')); _run(at)
    assert at.text_input(key='v::到货款比例').value == '100'
    assert 'v::预付款比例' not in keys() and 'v::调试款比例' not in keys()
    at.radio(key='o::付款方案').set_value(pay('预付款+到货款')); _run(at)
    assert at.text_input(key='v::到货款比例').value == '90' and at.text_input(key='v::预付款比例').value == '10'
    assert 'v::交货期数量' not in keys()                                   # 默认“最晚日期”：不显示天数
    at.radio(key='o::交货期方式').set_value('起算后 N 天（周、月）内，且最晚日期'); _run(at)
    assert {'v::交货期数量', 'v::交货期起算', 'v::交货日期'} <= keys()
    assert at.selectbox(key='o::交货期单位').options == ['天', '周', '月', '工作日']
    at.selectbox(key='o::交货期单位').set_value('周'); at.text_input(key='v::交货期数量').input('6'); _run(at)
    at.text_input(key='v::交货日期').input('2026年11月25日'); _run(at)
    # 按批次交货：填批数、首批日期、间隔后自动生成每批交货日期，可以再手工修改
    at.radio(key='o::交货期方式').set_value('按批次（船套）逐条列出交货日期'); _run(at)
    assert at.text_area(key='v::交货计划').value == ''
    at.text_input(key='v::交货批数').input('3'); at.text_input(key='v::首批交货日期').input('2027年1月26日'); _run(at)
    plan = at.text_area(key='v::交货计划').value
    assert plan.split('\n') == ['首船套交期：2027年1月26日', '第二条船交期：2027年4月26日', '第三条船交期：2027年7月26日']
    at.text_input(key='v::交货间隔月数').input('2'); _run(at)                       # 没手工改过：随输入更新
    assert '第二条船交期：2027年3月26日' in at.text_area(key='v::交货计划').value
    at.text_area(key='v::交货计划').input('首船套交期：2027年1月26日\n第二条船交期：2027年6月1日'); _run(at)
    at.text_input(key='v::交货间隔月数').input('3'); _run(at)                       # 手工改过：不再覆盖
    assert at.text_area(key='v::交货计划').value.endswith('第二条船交期：2027年6月1日')
    at.button[0].click(); _run(at)
    cfg = yaml.safe_load(open(glob.glob(str(tmp_path / 'configs' / '*.yaml'))[0], encoding='utf-8'))
    assert cfg['选项']['付款方案'] == '预付款+到货款' and cfg['选项']['交货期方式'] == '按批次交货'
    assert cfg['变量']['到货款比例'] == '90' and '调试款比例' not in cfg['变量']
    assert cfg['变量']['交货批数'] == '3' and cfg['变量']['首批交货日期'] == '2027年1月26日'
    assert cfg['变量']['交货计划'] == '首船套交期：2027年1月26日\n第二条船交期：2027年6月1日'


def test_po_project_preset_autofill(tmp_path, monkeypatch):
    """PO 表单：填项目编号自动带入预存的项目信息；没改动的值随项目切换，改过的保留；附加附件显示在“④ 合同附件”"""
    import glob, yaml
    from contract_compose import paths
    monkeypatch.setattr(paths, 'CONFIGS', str(tmp_path / 'configs'))
    monkeypatch.setattr(paths, 'OUTPUT', str(tmp_path / 'output'))
    (tmp_path / 'configs').mkdir()
    at = _run(AppTest.from_file(APP))
    at.selectbox(key='ctype').set_value('PO'); _run(at)
    at.text_input(key='v::项目编号').input('f484'); _run(at)
    assert at.text_input(key='v::项目名称').value == 'BALEINE III FPSO PROJECT'
    assert at.text_input(key='v::业主中文名').value == '埃尼' and at.text_input(key='v::设施简称').value == 'FPSO'
    assert any('附件M' in c.value and '附件N' in c.value for c in at.caption)
    at.text_input(key='v::项目名称').input('My Project'); at.text_input(key='v::项目编号').input('F520'); _run(at)
    assert at.text_input(key='v::项目名称').value == 'My Project'                   # 改过的保留
    assert at.text_input(key='v::设施简称').value == 'FLNG'                          # 没改过的随项目切换
    assert not any('附件M' in c.value for c in at.caption)                           # F520 只到附件 L
    assert at.checkbox(key='ax::ANX-TA').disabled                                     # 附件B 技术协议随“有技术协议”
    for k, v in (('LOA编号', 'LOA-1'), ('LOA日期', '2026年8月1日'), ('LOA日期_en', '1 August 2026')):
        at.text_input(key='v::' + k).input(v)
    _run(at)
    at.button[0].click(); _run(at)
    cfg = yaml.safe_load(open(glob.glob(str(tmp_path / 'configs' / '*.yaml'))[0], encoding='utf-8'))
    assert cfg['变量']['项目名称'] == 'My Project' and cfg['变量']['设施全称_en'] == 'floating liquefaction production facility'
    assert cfg['变量']['LOA编号'] == 'LOA-1' and cfg['附件']['ANX-NDA'] == '有' and 'ANX-TA' not in cfg['附件']


def test_editor_new_clause_with_new_variable(lib_copy, tmp_path, monkeypatch):
    """“＋ 新增条款”：选位置、写内容（正文里直接写新变量）、预览检查、保存；新条款按位置编号，新变量一并登记"""
    from contract_compose import load_library, structure as sc
    at = _editor(lib_copy, tmp_path, monkeypatch)
    at.selectbox(key='ed::ctype').set_value('S416'); _run(at)
    at.radio(key='ed::kind').set_value('新增条款'); _run(at)
    assert at.radio(key='nw::lv').value == '条款'
    at.selectbox(key='nw::ch').set_value('SCO-00'); _run(at)
    at.selectbox(key='nw::pos').set_value('SCO-01'); _run(at)                            # 放在 1.1 之后
    assert any('1.2' in i.value for i in at.info)                                         # 预告编号
    at.text_input(key='nw::name').input('质保延长说明')
    at.text_area(key='nw::body').input('卖方应在合同货物质保期届满前{{质保延长天数}}天内书面通知买方是否需要延长质保。\n\n- 延长期限由双方另行协商。'); _run(at)
    assert any('新变量' in m.value for m in at.markdown)                                   # 提示登记新变量
    assert next(b for b in at.button if b.label == '保存新增条款').disabled is False
    at.text_input(key='nw::vd::质保延长天数').input('30')
    at.text_input(key='nw::vs::质保延长天数').input('质保届满前几天通知买方')
    at.text_input(key='nw::reason').input('页面测试新增'); _run(at)
    _click(at, '保存新增条款')
    assert any('已新增条款' in s.value for s in at.success), [e.value for e in at.error]
    lib = load_library('S416')
    new = [a for a in lib.atoms if lib.atoms[a]['meta']['名称'] == '质保延长说明']
    assert len(new) == 1 and sc.current_order(lib).index(new[0]) == sc.current_order(lib).index('SCO-01') + 1
    assert lib.atoms[new[0]]['body'].startswith('## 卖方应在合同货物质保期届满前{{质保延长天数}}天内书面通知买方') and '\n\n- 延长期限由双方另行协商。' in lib.atoms[new[0]]['body']
    v = lib.V['质保延长天数']
    assert v['默认值'] == '30' and v['类别'] == '有默认值' and v['说明'] == '质保届满前几天通知买方' and v['原子'] == new
    assert '新建变量 质保延长天数' in open(lib_copy / 'S416' / '修订记录.md', encoding='utf-8').read()
    assert at.radio(key='ed::kind').value == '条款' and at.radio(key='ed::sel::S416::条款').value == new[0]     # 保存后跳到新条款


def test_editor_new_chapter_and_subclause(lib_copy, tmp_path, monkeypatch):
    from contract_compose import load_library, structure as sc
    at = _editor(lib_copy, tmp_path, monkeypatch)
    at.selectbox(key='ed::ctype').set_value('S416'); _run(at)
    at.radio(key='ed::kind').set_value('新增条款'); _run(at)
    at.radio(key='nw::lv').set_value('章'); _run(at)
    at.text_input(key='nw::name').input('售后服务'); _run(at)                              # 章代码留空自动分配，放在最后一章之后
    _click(at, '保存新增条款')
    assert any('已新增章' in s.value for s in at.success), [e.value for e in at.error]
    lib = load_library('S416')
    assert lib.atoms['CHA-00']['meta']['名称'] == '售后服务' and sc.current_order(lib)[-1] == 'CHA-00'
    at.radio(key='ed::kind').set_value('新增条款'); _run(at)
    at.radio(key='nw::lv').set_value('条款'); _run(at)
    at.selectbox(key='nw::ch').set_value('CHA-00'); _run(at)
    at.text_input(key='nw::name').input('响应时间'); at.text_area(key='nw::body').input('卖方应在收到通知后24小时内响应。'); _run(at)
    _click(at, '保存新增条款')
    assert any('已新增条款' in s.value for s in at.success), [e.value for e in at.error]
    at.radio(key='ed::kind').set_value('新增条款'); _run(at)
    at.radio(key='nw::lv').set_value('子条款'); _run(at)
    at.selectbox(key='nw::ch').set_value('CHA-00'); _run(at)
    at.text_input(key='nw::name').input('紧急情况'); at.text_area(key='nw::body').input('紧急情况下应在4小时内响应。'); _run(at)
    _click(at, '保存新增条款')
    assert any('已新增子条款' in s.value for s in at.success), [e.value for e in at.error]
    lib = load_library('S416'); order = sc.current_order(lib)
    assert order[-3:] == ['CHA-00', 'CHA-01', 'CHA-01-1']


def test_editor_new_clause_blocked_until_valid(lib_copy, tmp_path, monkeypatch):
    at = _editor(lib_copy, tmp_path, monkeypatch)
    at.selectbox(key='ed::ctype').set_value('S416'); _run(at)
    at.radio(key='ed::kind').set_value('新增条款'); _run(at)
    save = lambda: next(b for b in at.button if b.label == '保存新增条款')
    assert save().disabled                                                                  # 没有内容不能保存
    at.text_area(key='nw::body').input('引用不存在的条款 {{ref:XXX-99}}'); _run(at)
    assert save().disabled and any('XXX-99' in e.value for e in at.error)
    at.text_area(key='nw::body').input('只有文字的新条款。'); _run(at)
    assert not save().disabled and at.text_input(key='nw::name').value == ''              # 名称留空时取内容开头
