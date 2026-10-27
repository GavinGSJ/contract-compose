# -*- coding: utf-8 -*-
"""S416 的内容库功能：付款方案、交货期写法、价格表（数量 / 可选重量列）、附件编号与自定义附件。"""
import os, re, copy
import yaml
import pytest

from contract_compose import paths, build, load_library
from contract_compose.assembler import matches, split_conditions
from contract_compose.snapshots import dump
from contract_compose import structure as sc, maintenance as mt

CFG = os.path.join(paths.CONFIGS, '示例_S416_设备.yaml')


def cfg_with(**over):
    cfg = yaml.safe_load(open(CFG, encoding='utf-8'))
    for k, v in over.items():
        if isinstance(v, dict) and isinstance(cfg.get(k), dict):
            cfg[k] = {**cfg[k], **v}
        else:
            cfg[k] = v
    return cfg


def lines(cfg):
    return dump(build(cfg)).split('\n')


def find(ls, text):
    return [l for l in ls if text in l]


def test_option_match_alternatives():
    assert matches('甲', '甲|乙') and matches('乙', '甲|乙') and not matches('丙', '甲|乙')
    assert matches('甲', ['甲', '乙']) and matches('甲', '甲')


def test_payment_scheme_keeps_clauses_and_marks_na():
    """未选用的付款节点保留并标注不适用（比例写 N/A）；12.3 质量保函只在含调试款的方案中适用"""
    a = lines(cfg_with())                                                    # 预付款+到货款+调试款
    assert find(a, '] 10%预付款：') and find(a, '] 50%到货款：') and find(a, '] 40%调试款：')
    assert find(a, '在（60）日历日内，向卖方支付该批订单合同标的物价格的（50%）：')       # 到货款新写法
    assert find(a, '] （不适用）5%质保金：') and find(a, '（不适用）质保金为每批订单总价的（5）%')   # 质保金只在“到货款+质保金”方案中适用
    assert find(a, '] 设备（或货物）内在质量验收') and not find(a, 'N/A')
    b = lines(cfg_with(选项={'付款方案': '到货款一次付清'}))
    assert find(b, '（不适用）N/A预付款：') and find(b, '] 100%到货款：') and find(b, '（不适用）N/A调试款：')
    assert find(b, '（不适用）N/A质保金：') and find(b, '（不适用）设备（或货物）内在质量验收')       # 续行一同标注
    assert find(b, '（不适用）卖方应在货物安装调试验收合格后') and find(b, '合同价款 N/A 质量保函')
    c = lines(cfg_with(选项={'付款方案': '预付款+到货款'}))
    assert find(c, '] 10%预付款：') and find(c, '] 90%到货款：') and find(c, '（不适用）N/A调试款：')
    assert find(c, '（不适用）卖方应在货物安装调试验收合格后')
    # 明确给出的比例优先于方案预设
    d = lines(cfg_with(选项={'付款方案': '预付款+到货款'}, 变量={'预付款比例': '30', '到货款比例': '70'}))
    assert find(d, '] 30%预付款：') and find(d, '] 70%到货款：')


def test_payment_scheme_receipt_and_retention():
    """到货款+质保金（默认方案）：只有到货款和质保金，预付款、调试款不出现；质量保函（12.3）标注不适用"""
    e = lines(cfg_with(选项={'付款方案': '到货款+质保金'}))
    assert find(e, '] 95%到货款：卖方应根据买方下发的订单提供货物') and find(e, '价格的（95%）：')
    assert find(e, '] 5%质保金：') and find(e, '标的物质保期满且无质量或遗留问题') and find(e, '（30）个日历日内向卖方无息付清质量保证金')
    assert not find(e, '预付款：') and not find(e, '调试款：')
    assert find(e, '] 设备（或货物）内在质量验收') and not find(e, '（不适用）设备（或货物）')   # 验收报告也是支付质保金的依据
    assert find(e, '（不适用）卖方应在货物安装调试验收合格后')
    assert not find(e, 'N/A预付款') and not find(e, 'N/A调试款')
    f = lines(cfg_with(选项={'付款方案': '到货款+质保金'}, 变量={'到货款比例': '90', '质保比例': '10', '付款天数': '45', '质保金_释放天数': '15'}))
    assert find(f, '在（45）日历日内') and find(f, '价格的（90%）：') and find(f, '每批订单总价的（10）%') and find(f, '（15）个日历日内')


def test_default_payment_scheme_is_receipt_and_retention():
    cfg = cfg_with(); cfg['选项'].pop('付款方案')
    assert find(lines(cfg), '] 95%到货款：') and find(lines(cfg), '付款方案=到货款+质保金')


def test_payment_method_clause():
    ls = lines(cfg_with())
    assert find(ls, '支付方式：按（a）执行。') and find(ls, 'a) 银行转账；b) 承兑汇票；c) 银行转账或 6 个月银行承兑汇票；d) 银行支票；e) 银行本票；f) 托收承付；g) 现金。')
    assert find(lines(cfg_with(选项={'支付方式': 'c'})), '支付方式：按（c）执行。')


@pytest.mark.parametrize('opts,vals,expect', [
    ({'交货期方式': '最晚日期'}, {}, '2027年3月31日（如有调整，买方通知，买方不构成违约）。'),
    ({'交货期方式': '天数'}, {'交货期数量': '15'}, '收到中标通知书后15天内货到买方指定地点（如有调整'),
    ({'交货期方式': '天数', '交货期单位': '周'}, {'交货期数量': '6'}, '收到中标通知书后6周内货到买方指定地点（如有调整'),
    ({'交货期方式': '天数', '交货期单位': '月', '交货期节假日': '不计入'}, {'交货期数量': '2'},
     '收到中标通知书后2个月内货到买方指定地点（法定节假日不计入期限）（如有调整'),
    ({'交货期方式': '天数', '交货期单位': '工作日'}, {'交货期数量': '10'}, '收到中标通知书后10个工作日内货到买方指定地点'),
    ({'交货期方式': '天数+最晚日期', '交货期节假日': '不计入'}, {'交货期数量': '10'},
     '收到中标通知书后10天内货到现场（法定节假日不计入期限），最晚不迟于2027年3月31日货到买方指定地点（如有调整'),
    ({'交货期方式': '安排发货+最晚日期'}, {'交货期起算': '合同签订后'}, '合同签订后安排发货，最晚不迟于2027年3月31日货到买方指定地点'),
])
def test_delivery_forms(opts, vals, expect):
    ls = lines(cfg_with(选项=opts, 变量=vals))
    assert find(ls, expect), [l for l in ls if '交货' in l][:3]


def test_delivery_missing_count_only_when_used():
    """按天数写交货期而没填数量时，Word 中标黄；最晚日期方式不需要数量"""
    cfg = cfg_with(选项={'交货期方式': '天数'})
    del cfg['变量']['交货期数量']
    _, _, missing, _, _ = build(cfg)
    assert missing == {'交货期数量'}
    _, _, missing, _, _ = build(cfg_with())
    assert not missing


def table_rows(ls):
    """价格表各行（从表头“序号”起）"""
    rows = [l[4:].split(' | ') for l in ls if l.startswith('[表] ')]
    return rows[[r[0] for r in rows].index('序号'):]


def test_price_table_columns_and_total():
    std = table_rows(lines(cfg_with()))
    assert std[0] == ['序号', '产品名称', '规格/型号', '数量', '单位', '单价（元/船套）', '总金额（元）', '备注']
    assert std[1][3:5] == ['2', '船套'] and std[2][3:5] == ['3', '船套']        # 数量、单位
    assert std[3][:2] == ['合 计（元）', '1,650,000.00']                       # 合计行只留总金额
    cfg = cfg_with(货物=[{'产品名称': '钢板', '数量': '10', '单位': '块', '重量': '5000', '单价': '100', '总金额': '1003.50', '备注': '含运费'},
                       {'产品名称': '角钢', '数量': '4', '单位': '支', '单价': '50'}])
    w = table_rows(lines(cfg))
    assert w[0] == ['序号', '产品名称', '规格/型号', '数量', '单位', '重量（KG）', '单价（元/船套）', '总金额（元）', '备注']
    assert w[1][5] == '5000' and w[1][7] == '1,003.50' and w[2][5] == ''       # 总金额可手填；只填了一行重量
    assert w[3][:2] == ['合 计（元）', '1,203.50']
    assert any('壹仟贰佰零叁元伍角整' in l for l in lines(cfg))


def test_price_table_without_remark_column():
    """没有任何一行填备注时去掉备注列（有无重量列各一种）"""
    rows = [{'产品名称': '格栅', '数量': '6', '单位': '船套', '单价': '1320'}]
    t = table_rows(lines(cfg_with(货物=rows)))
    assert t[0] == ['序号', '产品名称', '规格/型号', '数量', '单位', '单价（元/船套）', '总金额（元）'] and t[1][5:] == ['1,320.00', '7,920.00']
    assert t[2] == ['合 计（元）', '7,920.00']                                  # 合计行：总金额是最后一列
    t = table_rows(lines(cfg_with(货物=[{**rows[0], '重量': '800'}])))
    assert t[0] == ['序号', '产品名称', '规格/型号', '数量', '单位', '重量（KG）', '单价（元/船套）', '总金额（元）']
    t = table_rows(lines(cfg_with(货物=[{**rows[0], '备注': '含锁'}])))
    assert t[0][-1] == '备注' and t[1][-1] == '含锁'


def test_price_unit_follows_goods_unit():
    """计价单位未填：各行单位相同时取货物明细的单位，否则用默认值；明确填写的优先"""
    row = {'产品名称': 'x', '单价': '1'}
    one = table_rows(lines(cfg_with(货物=[{**row, '单位': '吨'}, {**row, '单位': '吨'}])))
    assert '单价（元/吨）' in one[0]
    mixed = table_rows(lines(cfg_with(货物=[{**row, '单位': '吨'}, {**row, '单位': '块'}])))
    assert '单价（元/船套）' in mixed[0]
    given = table_rows(lines(cfg_with(货物=[{**row, '单位': '吨'}], 变量={'计价单位': '千克'})))
    assert '单价（元/千克）' in given[0]
    typed = table_rows(lines(cfg_with(货物=[{**row, '单位': '吨'}], 变量={'计价单位': '元/船套'})))        # 填成“元/船套”也不会写成“元/元/船套”
    assert '单价（元/船套）' in typed[0]


def annex_list(ls):
    return [l.split('] ', 1)[1] for l in ls if l.startswith('[s416p0] 附件')]


def test_annex_numbering_only_provided():
    """附件编号只给“有”的附件；没有编号的附件在引用处写 N/A；另加的附件接在最后"""
    ls = lines(cfg_with(附件={'ANX-PRICELIST': '有', 'ANX-NDA': '无', 'ANX-MINUTES': '有', 'ANX-AWARD': '无', 'ANX-TA': '无'},
                        自定义附件=[{'名称': '补充说明（签字盖章版）'}, {'名称': '补充说明', '名称_en': 'Supplement'}]))
    assert annex_list(ls) == ['附件一 供货明细表', '附件二 廉洁承诺书', '附件三 合同谈判纪要（签字盖章版）',
                              '附件四 补充说明（签字盖章版）', '附件五 补充说明']
    assert find(ls, '保密协议（附件/）') and find(ls, '本合同附件二《廉洁从业承诺书》')            # 7.2 的引用（没有提供：附件/）、第二十五章的引用
    default = lines(cfg_with(附件={}))                                   # 默认：供货明细表、廉洁承诺书、合同谈判纪要、中标通知书、技术协议，没有保密协议
    assert annex_list(default) == ['附件一 供货明细表', '附件二 廉洁承诺书', '附件三 合同谈判纪要（签字盖章版）',
                                   '附件四 中标通知书（签字盖章版）', '附件五 技术协议']
    nda = lines(cfg_with(附件={'ANX-NDA': '有'}))
    assert find(nda, '附件三 保密协议') and find(nda, '保密协议（附件三）')


def test_fa_annex_numbering_unchanged():
    """FA 仍按全部附件编号，没有英文名称的附件只写中文"""
    fa = yaml.safe_load(open(os.path.join(paths.CONFIGS, '示例_FA_防腐油漆.yaml'), encoding='utf-8'))
    fa['附件'] = {**(fa.get('附件') or {}), 'ANX-HSE': '无'}
    text = dump(build(fa))
    assert '附件十 项目特殊条款 Annex 10' in text and '附件十一' in text


def test_add_annex_english_name_optional(lib_copy):
    lib = load_library('S416')
    r = sc.add_annex(lib, 'ANX-NDA', '补充协议', '', typ='文件', default='无')
    assert r['ok'], r
    lib = load_library('S416')
    assert list(lib.annexes)[3] == r['id'] and lib.annexes[r['id']]['meta']['名称_en'] in ('', None)
    assert not sc.add_annex(lib, 'ANX-NDA', '', 'x')['ok']                      # 中文名称必填


def test_rename_annex_in_both_languages(lib_copy, tmp_path, monkeypatch):
    monkeypatch.setattr('contract_compose.snapshots.SNAP', str(tmp_path / 'snap'))
    lib = load_library('S416')
    body = lib.annexes['ANX-MINUTES']['body']
    r = mt.save(lib, '附件', 'ANX-MINUTES', body, name='合同谈判纪要', name_en='Negotiation Minutes', reason='测试', update_snapshots=False)
    assert r['ok'], r
    m = load_library('S416').annexes['ANX-MINUTES']['meta']
    assert m['名称'] == '合同谈判纪要' and m['名称_en'] == 'Negotiation Minutes'
    assert '英文名称“Contract Negotiation Minutes (Signed and Sealed)”改为“Negotiation Minutes”' in open(lib_copy / 'S416' / '修订记录.md', encoding='utf-8').read()


def test_clause_check_knows_conditions(lib_copy):
    lib = load_library('S416')
    body = lib.atoms['PAY-01']['body']
    assert mt.check(lib, '条款', 'PAY-01', body) == ([], [])
    errors, _ = mt.check(lib, '条款', 'PAY-01', body.replace('付款方案=预付款+到货款+调试款>', '付款方案=没有这种>', 1))
    assert any('没有取值' in e for e in errors)


def test_delivery_by_batches():
    """按批次交货：每隔几个月交付一批（如每三个月一船套），逐条列出每批的交货日期"""
    ls = lines(cfg_with(选项={'交货期方式': '按批次交货'}, 变量={'交货批数': '6', '首批交货日期': '2027年1月26日'}))
    assert [l.split('] ', 1)[1] for l in ls if '交期：' in l] == [
        '首船套交期：2027年1月26日', '第二条船交期：2027年4月26日', '第三条船交期：2027年7月26日',
        '第四条船交期：2027年10月26日', '第五条船交期：2028年1月26日', '第六条船交期：2028年4月26日']
    assert find(ls, '买方有权书面通知调整交货时间，包括提前或延后交付；卖方不得因买方调整交货期主张买方违约') and not find(ls, '（如有调整，买方通知')
    # 间隔、日期写法可改；也可以直接给交货计划（逐行修改过的）
    ls = lines(cfg_with(选项={'交货期方式': '按批次交货'}, 变量={'交货批数': '3', '首批交货日期': '2027-01-31', '交货间隔月数': '1'}))
    assert find(ls, '第二条船交期：2027年2月28日') and find(ls, '第三条船交期：2027年3月31日')
    ls = lines(cfg_with(选项={'交货期方式': '按批次交货'}, 变量={'交货计划': '首船套交期：2027年1月26日\n第二条船交期：2027年5月1日'}))
    assert find(ls, '第二条船交期：2027年5月1日') and not find(ls, '第三条船交期')
    _, _, missing, _, _ = build(cfg_with(选项={'交货期方式': '按批次交货'}))
    assert missing == {'交货计划'}                                          # 没填批数、首批日期：Word 中交货计划处标黄


def test_schedule_helpers():
    from contract_compose import schedule
    assert schedule.parse_date('2027/1/26') == (2027, 1, 26) and schedule.parse_date('2027.01.26') == (2027, 1, 26)
    assert schedule.parse_date('2027年2月30日') is None and schedule.parse_date('明年') is None
    assert schedule.add_months((2027, 11, 30), 3) == (2028, 2, 29)               # 日期超过当月天数取月末（2028 闰年）
    assert schedule.plan_lines('明年', 3, 3, 'a', 'b') is None and schedule.plan_lines('2027年1月1日', 0, 3, 'a', 'b') is None


def test_hide_paragraph_prefix():
    from contract_compose.assembler import split_conditions
    assert split_conditions('<不出现于 甲=乙><仅当 丙=丁> - 内容') == ([('不出现于', '甲', '乙'), ('仅当', '丙', '丁')], '- 内容')
    assert split_conditions('没有条件') == ([], '没有条件')


def test_template_defaults_from_e0095():
    """按 S416-02-0103-E-0095 调整的模板默认：LR 船级社、合同正本 3 份（买方持 2 份、卖方持 1 份）、联系人行可带邮箱"""
    cfg = cfg_with(); cfg['变量'].pop('船级社')
    ls = lines(cfg)
    assert find(ls, '提供满足LR船级社及买卖双方签订的技术协议要求证书正本一份')
    assert find(ls, '本合同正本3份，买方持2份，卖方持1份。')
    assert find(ls, '卖方联系人：张三（021-12345678）。')
    ls = lines(cfg_with(变量={'卖方.邮箱': 'a@b.com'}))
    assert find(ls, '卖方联系人：张三（021-12345678，a@b.com）。')


def test_stray_spaces_and_typos_removed():
    lib = load_library('S416')
    bad = [a for a, x in lib.atoms.items() if '（时间）' in x['body'] or
           re.search(r'[一-鿿，；。、：）（] [一-鿿（]', '\n'.join(split_conditions(l)[1] for l in x['body'].split('\n')))]
    assert bad == []
