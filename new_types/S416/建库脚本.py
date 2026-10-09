# -*- coding: utf-8 -*-
"""S416 VLCC 采购订单（中文版）建库脚本（一次性，留作追溯）。

用法（项目根目录）：python -I new_types/S416/建库脚本.py <母本.docx> library/S416
生成：type.yaml、recipe.yaml、variables.yaml、options/物资类别.yaml、atoms/、annexes/、
      blocks/S416-COVER.xml、blocks/S416-SIGN.xml、tables/S416-PRICE.xml、templates/S416样式模板.docx、reference/
母本中的明显错误按评审意见第二节修正（见 library/S416/修订记录.md），存疑项保持原文。
"""
import os, re, sys, copy, shutil, zipfile
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
import yaml
from lxml import etree
from contract_compose.master_parser import parse

SRC, OUT = sys.argv[1], sys.argv[2]
W = 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'
q = lambda t: '{%s}%s' % (W, t)
XS = '{http://www.w3.org/XML/1998/namespace}space'

M = parse(SRC)
P = {p['i']: p['text'] for p in M['paras'] if p['kind'] == 'p'}


def strip_label(t):
    t = re.sub(r'^\s*[一二三四五六七八九十]+、', '', t)
    t = re.sub(r'^\s*\d+\.\d+\s*', '', t)
    t = re.sub(r'^\s*(\(\d+\)|\d+）|[a-m][\.\)）])\s*', '', t)
    return t.strip()


def T(i):
    return strip_label(P[i])


# ======================= 条款结构 =======================
# (ID, 层级, 名称, 正文行)；正文行：标记 + 文字（文字为段落号时取母本原文）
EQUIP = '<仅当 物资类别=设备> '
A = []


def chap(aid, i, *body, name=None):
    A.append((aid, '章', name or T(i), ['# ' + (name or T(i))] + list(body)))


def cl(aid, i, *body):
    A.append((aid, '条款', None, ['## ' + T(i)] + list(body)))


chap('SCO-00', 9, '{{table:S416-PRICE}}')
cl('SCO-01', 12)
cl('SCO-02', 13, T(14), T(15), EQUIP + T(16))
cl('SCO-03', 17, T(18))
cl('SCO-04', 19)
chap('PLC-00', 20, T(21))
chap('DEL-00', 22, '{{交货日期}}（如有调整，买方通知，买方不构成违约）。')
chap('PAY-00', 24)
A.append(('PAY-01', '条款', '付款节点', ['## ', '- ' + T(26), '- ' + T(27), '  ' + T(28), EQUIP + '- ' + T(29), '  ' + T(30)]))
cl('PAY-02', 31); cl('PAY-03', 32)
chap('ORI-00', 33, '{{原产地和制造商}}。' + T(34).split('。', 1)[1])
chap('SPE-00', 35, T(36))
chap('IPC-00', 37); cl('IPC-01', 38); cl('IPC-02', 39); cl('IPC-03', 40); cl('IPC-04', 41)
chap('PAC-00', 42, T(43))
chap('MRK-00', 44, T(45), EQUIP + T(46))
chap('SHP-00', 47); cl('SHP-01', 48)
cl('SHP-02', 49, *['  - ' + T(i) for i in (50, 51)], EQUIP + '  - ' + T(52), *['  - ' + T(i) for i in (53, 54, 55, 56)])
chap('TRA-00', 57, T(58))
chap('QTY-00', 59); cl('QTY-01', 60); cl('QTY-02', 61); cl('QTY-03', 62)
chap('QUA-00', 63); cl('QUA-01', 64); cl('QUA-02', 65); cl('QUA-03', 66); cl('QUA-04', 67)
chap('PLI-00', 68, T(69))
chap('SAF-00', 70); cl('SAF-01', 71); cl('SAF-02', 72)
chap('INS-00', 73)
for n, i in enumerate(range(74, 80), 1):
    cl(f'INS-0{n}', i)
# 修正 1：第十七章标题与正文粘连，拆开
t81 = T(81); head17 = '合同货物的安装、试运行和性能测试'
assert t81.startswith(head17 + '合同货物的安装'), t81[:40]
chap('ERE-00', 81, t81[len(head17):], T(82), name=head17)
chap('LIA-00', 83)
for n, i in enumerate(range(84, 96), 1):
    cl(f'LIA-{n:02d}', i)
chap('FM-00', 96)
cl('FM-01', 97)
cl('FM-02', 98, *['+ ' + T(i) for i in (99, 100, 101, 102)], T(103))
cl('FM-03', 104, *['  + ' + T(i) for i in range(105, 118)])
cl('FM-04', 118); cl('FM-05', 119, T(120)); cl('FM-06', 121)
cl('FM-07', 122, '  + ' + T(123), '  + ' + T(124), T(125))
chap('TER-00', 126)
cl('TER-01', 127, T(128))
cl('TER-02', 129, T(130), *['  + ' + T(i) for i in (131, 132, 133)], T(134), *['  + ' + T(i) for i in (135, 136, 137, 138)])
cl('TER-03', 139); cl('TER-04', 140); cl('TER-05', 141); cl('TER-06', 142)
chap('TAX-00', 143, T(144))
chap('LAW-00', 145, T(146))
chap('DIS-00', 147, T(148))
chap('EFF-00', 149)
for n, i in enumerate(range(150, 155), 1):
    cl(f'EFF-0{n}', i)
chap('INT-00', 155, T(156))
chap('DEC-00', 157, T(158), T(159), T(160))
chap('SPC-00', 161); cl('SPC-01', 162)
cl('SPC-02', 163, '- ' + T(164), '- ' + T(165))
cl('SPC-03', 166); cl('SPC-04', 167); cl('SPC-05', 168)

ONLY_EQUIP = {'SCO-03', 'INS-06', 'ERE-00', 'LIA-05', 'SPC-02'}      # 整条 / 整章仅设备类适用

# ======================= 修正与变量替换（每处须在原文中出现） =======================
FIX = [  # 评审意见第二节的修正（编号见修订记录）
    ('SCO-03', '卖方应以优惠价格向卖方供应', '卖方应以优惠价格向买方供应'),                       # 4
    ('PAY-01', '与买方实际需求交货期前三个月内支付', '于买方实际需求交货期前{{预付款_提前月数}}个月内支付'),  # 5
    ('PAY-01', '出场检验', '出厂检验'),                                                       # 6
    ('IPC-01', '程序文件等等不受第三方', '程序文件等）不受第三方'),                             # 7
    ('IPC-02', '货款及及其他', '货款及其他'),                                                 # 8
    ('QTY-03', '验收合同之日起算', '验收合格之日起算'),                                        # 9
    ('FM-03', '不构成不不可抗力', '不构成不可抗力'),                                           # 11
    ('FM-03', '除上述19.1 a）以外', '除上述{{ref:FM-02}} a）以外'),                            # 12
    ('TER-01', '卖方就此恢复供货的协商和协商可获得的唯一救济', '卖方就恢复供货进行协商可获得的唯一救济'),  # 14
]
VAR = [
    ('SCO-01', '含13%增值税', '含{{增值税率}}增值税'),
    ('PAY-01', '- 10%预付款', '- {{预付款比例}}%预付款'),
    ('PAY-01', '“10%预付款保函”', '“{{预付款比例}}%预付款保函”'),
    ('PAY-01', '- 50%到货款', '- {{到货款比例}}%到货款'),
    ('PAY-01', '- 40%调试款', '- {{调试款比例}}%调试款'),
    ('PAY-01', '买方认可的5%银行质量保函后三个月支付', '买方认可的{{质保比例}}%银行质量保函后{{调试款_支付月数}}个月支付'),
    ('IPC-02', '保密协议（附件【】）', '保密协议（{{附件:ANX-NDA}}）'),
    ('IPC-02', '违约金金额为合同总价的10%', '违约金金额为合同总价的{{保密违约金比例}}%'),
    ('IPC-02', '违约金为合同总价的5%', '违约金为合同总价的{{宣传违约金比例}}%'),
    ('SHP-01', '交货前2个工作日内', '交货前{{装运通知工作日}}个工作日内'),
    ('SHP-02', '正本3份，副本4份', '正本{{单据正本份数}}份，副本{{单据副本份数}}份'),
    ('SHP-02', '满足XXX船级社', '满足{{船级社}}'),
    ('QTY-01', '收货后15日内', '收货后{{数量异议天数}}日内'),
    ('QTY-02', '交船之日向后12个月', '交船之日向后{{质保期月数}}个月'),
    ('QTY-02', '保证期应另外延长12个月', '保证期应另外延长{{质保延长月数}}个月'),
    ('QTY-03', '七（7）天内', '{{中文数字:质保函_提交天数}}（{{质保函_提交天数}}）天内'),
    ('QTY-03', '合同价款 5% 质量保函', '合同价款 {{质保比例}}% 质量保函'),
    ('QTY-03', '有效期为18个月', '有效期为{{质保函_有效月数}}个月'),
    ('QTY-03', '十四（14）日内', '{{中文数字:质保函_退还天数}}（{{质保函_退还天数}}）日内'),
    ('QUA-04', '24小时内', '{{维修到场小时}}小时内'),
    ('LIA-03', '延迟交货在10日以内(含)的,按合同总金额的0.5%/天支付违约金,但违约金总额不超过合同总金额的5%;若逾期达10日以上的',
     '延迟交货在{{延迟天数阈值}}日以内(含)的,按合同总金额的{{延迟违约金比例}}%/天支付违约金,但违约金总额不超过合同总金额的{{延迟违约金上限}}%;若逾期达{{延迟天数阈值}}日以上的'),
    ('LIA-03', '未履行部分金额20%的违约金', '未履行部分金额{{延迟逾期违约金比例}}%的违约金'),
    ('LIA-06', '第1.2、1.3条', '第{{ref:SCO-02}}、{{ref:SCO-03}}条'),
    ('LIA-06', '合同价款30%的违约金', '合同价款{{供货义务违约金比例}}%的违约金'),
    ('LIA-10', '第10.2之约定', '第{{ref:SHP-02}}之约定'),
    ('LIA-10', '货款总额1%的违约金', '货款总额{{发票逾期违约金比例}}%的违约金'),
    ('LIA-10', '超过10日仍然不能交付', '超过{{发票逾期天数}}日仍然不能交付'),
    ('LIA-10', '货款5%的违约金', '货款{{发票逾期加重比例}}%的违约金'),
    ('LIA-10', '30天的宽展期', '{{船级社证书宽展天数}}天的宽展期'),
    ('FM-02', '根据第19.4条约定', '根据第{{ref:FM-04}}条约定'),
    ('INT-00', '附件【】《廉洁从业承诺书》', '{{附件:ANX-INTEGRITY}}《廉洁从业承诺书》'),
    ('SPC-01', '合同签订日后5天内', '合同签订日后{{资料提交天数}}天内'),
    ('SPC-02', '提前3天预报', '提前{{调试_预报天数}}天预报'),
    ('SPC-02', '提前1天予以正式确认', '提前{{调试_确认天数}}天予以正式确认'),
    ('SPC-02', '2天内卖方未能作出', '{{调试_反馈天数}}天内卖方未能作出'),
    ('SPC-02', '设备合同总金额的1%', '设备合同总金额的{{调试_罚款比例}}%'),
    ('SPC-03', '卖方联系人：____________（______________）。', '卖方联系人：{{卖方.联系人}}（{{卖方.电话}}）。'),
    ('SPC-04', '两年内', '{{价格保持年数}}年内'),
]
for n in (4, 5):                                       # 18.4、18.5 的技术文件 / 技术服务延误违约金
    VAR += [(f'LIA-0{n}', '百分之零点五（0.5%）', '百分之{{中文数字:技术延误违约金_前四周}}（{{技术延误违约金_前四周}}%）'),
            (f'LIA-0{n}', '百分之一点五（1.5%）', '百分之{{中文数字:技术延误违约金_此后}}（{{技术延误违约金_此后}}%）'),
            (f'LIA-0{n}', '百分之五（5%）', '百分之{{中文数字:技术延误违约金_上限}}（{{技术延误违约金_上限}}%）')]

atoms = {aid: [lv, name, body] for aid, lv, name, body in A}
for aid, old, new in FIX + VAR:
    text = '\n\n'.join(atoms[aid][2])
    c = text.count(old)
    assert c >= 1, (aid, old)
    atoms[aid][2] = text.replace(old, new).split('\n\n')
# 修正 10：13.3 句末补句号
atoms['QUA-03'][2][0] = atoms['QUA-03'][2][0].rstrip() + '。'
assert not any('【】' in l or '____' in l or 'XXX' in l for v in atoms.values() for l in v[2]), '仍有待填位'

# ======================= 写原子 =======================
CODE_NAME = {}
os.makedirs(os.path.join(OUT, 'atoms'), exist_ok=True)
cur_ch = ''
for aid, lv, name, _ in A:
    lv_, nm, body = atoms[aid]
    if lv == '章':
        cur_ch = nm
    if nm is None:
        nm = re.sub(r'^#+ ', '', body[0]).strip()
        nm = re.split(r'[，。；：,:（(]', nm)[0][:24] or aid
    meta = {'id': aid, '名称': nm, '层级': lv, '章': cur_ch, '适用': ['S416'], '版本': 'S416中文版'}
    safe = re.sub(r'[\\/:*?"<>|\s，。、；：（）()“”‘’《》【】,]', '', nm)[:16]
    with open(os.path.join(OUT, 'atoms', f'{aid}_{safe}.md'), 'w', encoding='utf-8') as f:
        f.write('---\n' + yaml.safe_dump(meta, allow_unicode=True, sort_keys=False, width=10000) + '---\n\n' + '\n\n'.join(body) + '\n')

# ======================= 配方、类型、选项、附件 =======================
recipe = ['# S416 VLCC 采购订单配方：条款顺序（类型设置见 type.yaml）。',
          '# 带“仅当选项”的条款在选项不符时保留并标注“（不适用）”；条款内的段落用行首 <仅当 物资类别=设备> 标记。',
          '附件:', '  顺序:', '  - ANX-INTEGRITY              # 廉洁承诺书（PDF）', '  - ANX-NDA                    # 保密协议（PDF）',
          '顺序:', '- 块: S416-COVER']
for aid, *_ in A:
    recipe.append(f'- 原子: {aid}')
    if aid in ONLY_EQUIP:
        recipe.append('  仅当选项: {物资类别: 设备}')
recipe += ['- 块: S416-SIGN', '- 附件列表: 自动']
open(os.path.join(OUT, 'recipe.yaml'), 'w', encoding='utf-8').write('\n'.join(recipe) + '\n')

open(os.path.join(OUT, 'type.yaml'), 'w', encoding='utf-8').write('''# 合同类型设置。library/ 下有 type.yaml 的目录即为一种合同类型，程序与表单自动识别。
名称: S416 VLCC 采购订单                # 表单中显示的名称
说明: 中文；章号“一、”，条款 x.y；同一模板适用材料类与设备类物资（“物资类别”切换）
样式模板: templates/S416样式模板.docx
编号起始: 1
付款条款: []
履约保函条款: null
不适用标注: （不适用）                   # 中文合同只标中文
货物明细: true                          # 价格表按多行货物生成，含税总价 = 各行总金额之和
表单标签: {}
表单隐藏: [项目编号, 项目名称, 业主名称, 设施简称, 设施全称, 标的物名称, 币种, 技术协议, 付款方式, 质保方式, 质保期]
''')

os.makedirs(os.path.join(OUT, 'options'), exist_ok=True)
open(os.path.join(OUT, 'options', '物资类别.yaml'), 'w', encoding='utf-8').write('''# 物资类别：设备类专有的条款 / 段落在材料类合同中保留并标注“（不适用）”
名称: 物资类别
类型: 文字
位置: 全文（1.2、1.3、4.1、9、10.2、16.6、第十七章、18.5、27.2 等）
说明: 设备类：安装调试、控制软件、调试款等条款适用；材料类：这些条款标注不适用
默认: 设备
选项:
  设备:
    名称: 设备类
    中文: 设备
  材料:
    名称: 材料类
    中文: 材料
''')

os.makedirs(os.path.join(OUT, 'annexes'), exist_ok=True)
for aid, nm in (('ANX-INTEGRITY', '廉洁承诺书'), ('ANX-NDA', '保密协议')):
    meta = {'id': aid, '名称': nm, '名称_en': {'ANX-INTEGRITY': 'Undertaking of Honest Conduct', 'ANX-NDA': 'Non-Disclosure Agreement'}[aid],
            '类型': '文件', '默认': '有'}
    open(os.path.join(OUT, 'annexes', f'{aid}_{nm}.md'), 'w', encoding='utf-8').write(
        '---\n' + yaml.safe_dump(meta, allow_unicode=True, sort_keys=False) + '---\n')

# ======================= 变量 =======================
def v(default, desc, cat='有默认值', 母本=None):
    d = {'默认值': str(default), '说明': desc, '类别': cat, '类型': '值'}
    if 母本 is not None: d['母本值'] = str(母本)
    return d


req = lambda desc, 母本='': v('', desc, '必填', 母本)
VARS = {
    '物资类别': {'默认值': '设备', '说明': '设备类 / 材料类', '原子': ['SCO-00'], '类别': '选项', '类型': '选项'},
    '交货日期': req('交货日期（中文），如 2027年3月31日', '____年__月__日'),
    '原产地和制造商': req('原产地和制造商，如 中国 / XX有限公司', '______________________________'),
    '船级社': req('船级社名称，如 中国船级社（CCS）', 'XXX船级社'),
    '卖方.联系人': req('卖方联系人姓名（第二十七条）', '____________'),
    '卖方.电话': req('卖方联系电话（封面、第二十七条）', '______________'),
    '货物明细': req('在表单“合同价款”中填写货物明细（多行）'),
    '计价单位': v('船套', '价格表单价的计价单位，如 船套、台、吨'),
    '价款_单价合计': {'默认值': '', '说明': '价格表合计行（单价列），由货物明细自动计算', '类别': '自动（计算）', '类型': '值'},
    '价款_合计': {'默认值': '', '说明': '价格表合计行（总金额列），由货物明细自动计算', '类别': '自动（计算）', '类型': '值'},
    '预付款比例': v(10, '4.1 预付款比例（%）'), '到货款比例': v(50, '4.1 到货款比例（%）'),
    '调试款比例': v(40, '4.1 调试款比例（%），材料类该款标注不适用'),
    '质保比例': v(5, '质量保函金额占合同价款的比例（%）'),
    '预付款_提前月数': v('三', '预付款于实际需求交货期前几个月内支付（中文数字）'),
    '调试款_支付月数': v('三', '调试款在收到质量保函后几个月支付（中文数字）'),
    '保密违约金比例': v(10, '7.2 违反保密义务的违约金（合同总价 %）'),
    '宣传违约金比例': v(5, '7.2 未经同意宣传 / 使用买方信息的违约金（合同总价 %）'),
    '装运通知工作日': v(2, '10.1 交货前几个工作日通知'),
    '单据正本份数': v(3, '10.2 码单 / 装箱单正本份数'), '单据副本份数': v(4, '10.2 码单 / 装箱单副本份数'),
    '数量异议天数': v(15, '12.1 收货后数量异议期（日）'),
    '质保期月数': v(12, '12.2 质保期：交船后（月）'), '质保延长月数': v(12, '12.2 修理或更替后保证期延长（月）'),
    '质保函_提交天数': v(7, '12.3 验收合格后提交质量保函（天）'), '质保函_有效月数': v(18, '12.3 质量保函有效期（月）'),
    '质保函_退还天数': v(14, '12.3 质保期满后退还质量保函（日）'),
    '维修到场小时': v(24, '13.4 接到通知后到场维修（小时）'),
    '延迟天数阈值': v(10, '18.3 延迟交货分段天数（日）'), '延迟违约金比例': v(0.5, '18.3 延迟交货违约金（%/天）'),
    '延迟违约金上限': v(5, '18.3 延迟交货违约金上限（%）'), '延迟逾期违约金比例': v(20, '18.3 逾期超过分段天数后的违约金（%）'),
    '技术延误违约金_前四周': v(0.5, '18.4、18.5 前四周每七天违约金（%）'), '技术延误违约金_此后': v(1.5, '18.4、18.5 此后每七天违约金（%）'),
    '技术延误违约金_上限': v(5, '18.4、18.5 违约金上限（%）'),
    '供货义务违约金比例': v(30, '18.6 违反 1.2、1.3 的违约金（%）'),
    '发票逾期违约金比例': v(1, '18.10 发票每逾期一日违约金（%）'), '发票逾期天数': v(10, '18.10 加重违约金的逾期天数（日）'),
    '发票逾期加重比例': v(5, '18.10 超过逾期天数后每日违约金（%）'), '船级社证书宽展天数': v(30, '18.10 船级社证书宽展期（天）'),
    '资料提交天数': v(5, '27.1 签订后提供买方认可资料（天）'),
    '调试_预报天数': v(3, '27.2 提前预报服务时间（天）'), '调试_确认天数': v(1, '27.2 提前正式确认（天）'),
    '调试_反馈天数': v(2, '27.2 卖方书面反馈期限（天）'), '调试_罚款比例': v(1, '27.2 每天罚款（设备合同总金额 %）'),
    '价格保持年数': v('两', '27.4 同等供货单价不高于本合同的期限（年，中文数字）'),
}
open(os.path.join(OUT, 'variables.yaml'), 'w', encoding='utf-8').write(
    '# S416 专用变量（与 library/common/variables.yaml 合并；同名时以此处为准）\n'
    + yaml.safe_dump(VARS, allow_unicode=True, sort_keys=False, width=10000))

# ======================= 块、表格、样式模板 =======================
z = zipfile.ZipFile(SRC)
body = etree.fromstring(z.read('word/document.xml')).find(q('body'))
els = list(body)


def clean(e):
    e = copy.deepcopy(e)
    for x in e.iter():
        for a in list(x.attrib):
            if 'rsid' in a or a.endswith(('}paraId', '}textId')): del x.attrib[a]
    for tag in ('bookmarkStart', 'bookmarkEnd', 'proofErr', 'lastRenderedPageBreak', 'commentRangeStart', 'commentRangeEnd'):
        for x in list(e.iter(q(tag))): x.getparent().remove(x)
    for r in list(e.iter(q('r'))):
        if r.find(q('commentReference')) is not None: r.getparent().remove(r)
    return e


def segments(p, segs, tab=None):
    """把段落的文字换成 segs=[(文字, 加粗)]；tab 为制表位位置（文字中的 \\t）"""
    ppr = p.find(q('pPr'))
    for r in list(p):
        if r is not ppr: p.remove(r)
    if tab:
        tabs = etree.SubElement(ppr, q('tabs')); ppr.insert(0, tabs)
        t = etree.SubElement(tabs, q('tab')); t.set(q('val'), 'left'); t.set(q('pos'), str(tab))
    for text, bold in segs:
        for k, part in enumerate(text.split('\t')):
            if k:
                etree.SubElement(etree.SubElement(p, q('r')), q('tab'))
            if part:
                r = etree.SubElement(p, q('r'))
                if bold:
                    rp = etree.SubElement(r, q('rPr')); etree.SubElement(rp, q('b')); etree.SubElement(rp, q('bCs'))
                t = etree.SubElement(r, q('t')); t.text = part; t.set(XS, 'preserve')


def save_block(name, elems, sub='blocks'):
    os.makedirs(os.path.join(OUT, sub), exist_ok=True)
    root = etree.Element('block', nsmap={'w': W})
    for e in elems: root.append(e)
    open(os.path.join(OUT, sub, name + '.xml'), 'wb').write(etree.tostring(root, encoding='utf-8', xml_declaration=True))


cover = [clean(els[i]) for i in range(0, 9)]
def cover_table(p_tpl, rows, widths=(5000, 4026)):
    """封面买方两行做成无框两栏表：左栏地址过长时在栏内折行，不会挤到右栏“签订时间”"""
    tbl = etree.Element(q('tbl'))
    pr = etree.SubElement(tbl, q('tblPr'))
    etree.SubElement(pr, q('tblW')).attrib.update({q('w'): str(sum(widths)), q('type'): 'dxa'})
    bd = etree.SubElement(pr, q('tblBorders'))
    for side in ('top', 'left', 'bottom', 'right', 'insideH', 'insideV'):
        etree.SubElement(bd, q(side)).set(q('val'), 'nil')
    etree.SubElement(pr, q('tblLayout')).set(q('type'), 'fixed')
    mar = etree.SubElement(pr, q('tblCellMar'))
    for side, wd in (('left', 0), ('right', 284)):              # 右侧留空，左栏文字不贴近右栏
        etree.SubElement(mar, q(side)).attrib.update({q('w'): str(wd), q('type'): 'dxa'})
    grid = etree.SubElement(tbl, q('tblGrid'))
    for wd in widths:
        etree.SubElement(grid, q('gridCol')).set(q('w'), str(wd))
    for row in rows:
        tr = etree.SubElement(tbl, q('tr'))
        for wd, segs in zip(widths, row):
            tc = etree.SubElement(tr, q('tc'))
            etree.SubElement(etree.SubElement(tc, q('tcPr')), q('tcW')).attrib.update({q('w'): str(wd), q('type'): 'dxa'})
            p = copy.deepcopy(p_tpl); tc.append(p); segments(p, segs)
    return tbl


segments(cover[4], [('卖方：', True), ('{{卖方.名称}}', True)])
segments(cover[5], [('地址：', False), ('{{卖方.地址}}', True)])
segments(cover[6], [('电话：', False), ('{{卖方.电话}}', True)])
cover[1:3] = [cover_table(cover[1], [
    [[('买方：', True), ('{{买方.名称}}', True)], [('合同号：', False), ('{{合同编号}}', True)]],
    [[('地址：', False), ('{{买方.地址}}', True)], [('签订时间：', False), ('{{签订日期}}', True)]]])]
save_block('S416-COVER', cover)

sign = [clean(els[i]) for i in (169, 170, 171, 172)]
ts = [t for t in sign[1].iter(q('t'))]
blanks = [t for t in ts if t.text and re.fullmatch(r'_+', t.text)]
assert len(blanks) == 2
blanks[0].text, blanks[1].text = '{{买方.名称}}', '{{卖方.名称}}'
save_block('S416-SIGN', sign)

tbl = clean(els[10])
rows = tbl.findall(q('tr'))
for r in rows[2:5]: tbl.remove(r)
for t in rows[0].iter(q('t')):
    if t.text and '船套' in t.text: t.text = t.text.replace('船套', '{{计价单位}}')
cells = rows[1].findall(q('tc'))
for tc, ph in zip(cells, ['序号', '产品名称', '规格型号', '单位', '单价', '总金额', '备注']):
    ts = list(tc.iter(q('t')))
    assert ts, ph
    ts[0].text = '{{行.%s}}' % ph
    for t in ts[1:]: t.text = ''
tot = rows[5].findall(q('tc'))
for tc, ph in ((tot[1], '{{价款_单价合计}}'), (tot[2], '{{价款_合计}}')):
    ts = list(tc.iter(q('t'))); ts[0].text = ph
    for t in ts[1:]: t.text = ''
up = [t for t in rows[6].iter(q('t')) if t.text and '人民币（大写）' in t.text]
assert up
up[-1].text = up[-1].text + '{{价款_大写}}'
# 列宽：单价、总金额加宽（金额不折行），单位、备注收窄；总宽不变
WID = {'830': '700', '1187': '1700', '2660': '1764', '3992': '3862'}
for x in list(tbl.iter(q('gridCol'))) + list(tbl.iter(q('tcW'))):
    x.set(q('w'), WID.get(x.get(q('w')), x.get(q('w'))))
save_block('S416-PRICE', [tbl], 'tables')

# 样式模板：以母本为底（保留页面设置、页眉页脚、原有样式），清空正文，加入“合同-*”样式与编号
os.makedirs(os.path.join(OUT, 'templates'), exist_ok=True)
os.makedirs(os.path.join(OUT, 'reference'), exist_ok=True)
shutil.copy(SRC, os.path.join(OUT, 'reference', 'S416VLCC采购订单_中文版.docx'))
STY = '''<w:styles xmlns:w="%s">
<w:style w:type="paragraph" w:customStyle="1" w:styleId="s416base"><w:name w:val="合同-基础"/><w:qFormat/><w:pPr><w:spacing w:after="120" w:line="360" w:lineRule="auto"/><w:jc w:val="both"/></w:pPr></w:style>
<w:style w:type="paragraph" w:customStyle="1" w:styleId="s416h1"><w:name w:val="合同-章标题"/><w:basedOn w:val="s416base"/><w:next w:val="s416c1"/><w:qFormat/><w:pPr><w:keepNext/><w:numPr><w:ilvl w:val="0"/><w:numId w:val="1"/></w:numPr><w:spacing w:before="200"/><w:outlineLvl w:val="0"/></w:pPr><w:rPr><w:b/><w:bCs/></w:rPr></w:style>
<w:style w:type="paragraph" w:customStyle="1" w:styleId="s416c1"><w:name w:val="合同-条款"/><w:basedOn w:val="s416base"/><w:qFormat/><w:pPr><w:numPr><w:ilvl w:val="1"/><w:numId w:val="1"/></w:numPr></w:pPr></w:style>
<w:style w:type="paragraph" w:customStyle="1" w:styleId="s416c2"><w:name w:val="合同-子条款"/><w:basedOn w:val="s416base"/><w:qFormat/><w:pPr><w:numPr><w:ilvl w:val="2"/><w:numId w:val="1"/></w:numPr></w:pPr></w:style>
<w:style w:type="paragraph" w:customStyle="1" w:styleId="s416l1"><w:name w:val="合同-列项"/><w:basedOn w:val="s416base"/><w:qFormat/><w:pPr><w:numPr><w:ilvl w:val="3"/><w:numId w:val="1"/></w:numPr></w:pPr></w:style>
<w:style w:type="paragraph" w:customStyle="1" w:styleId="s416l2"><w:name w:val="合同-列项二级"/><w:basedOn w:val="s416base"/><w:qFormat/><w:pPr><w:numPr><w:ilvl w:val="4"/><w:numId w:val="1"/></w:numPr></w:pPr></w:style>
<w:style w:type="paragraph" w:customStyle="1" w:styleId="s416p"><w:name w:val="合同-正文"/><w:basedOn w:val="s416base"/><w:qFormat/><w:pPr><w:ind w:firstLine="420"/></w:pPr></w:style>
<w:style w:type="paragraph" w:customStyle="1" w:styleId="s416p0"><w:name w:val="合同-正文（顶格）"/><w:basedOn w:val="s416base"/><w:qFormat/></w:style>
<w:style w:type="paragraph" w:customStyle="1" w:styleId="s416pc"><w:name w:val="合同-正文（居中）"/><w:basedOn w:val="s416base"/><w:qFormat/><w:pPr><w:jc w:val="center"/></w:pPr></w:style>
<w:style w:type="paragraph" w:customStyle="1" w:styleId="s416cont"><w:name w:val="合同-正文（列项续行）"/><w:basedOn w:val="s416base"/><w:qFormat/><w:pPr><w:ind w:firstLine="420"/></w:pPr></w:style>
<w:style w:type="paragraph" w:customStyle="1" w:styleId="s416cont2"><w:name w:val="合同-正文（二级续行）"/><w:basedOn w:val="s416base"/><w:qFormat/><w:pPr><w:ind w:left="840"/></w:pPr></w:style>
<w:style w:type="paragraph" w:customStyle="1" w:styleId="s416tbl"><w:name w:val="合同-表格文字"/><w:basedOn w:val="s416base"/><w:qFormat/><w:pPr><w:spacing w:after="0" w:line="240" w:lineRule="auto"/><w:jc w:val="left"/></w:pPr></w:style>
</w:styles>''' % W


def lvl(i, fmt, text, ind, suff='nothing', style=None, legal=False):
    s = f'<w:lvl w:ilvl="{i}"><w:start w:val="1"/><w:numFmt w:val="{fmt}"/>'
    if style: s += f'<w:pStyle w:val="{style}"/>'
    if legal: s += '<w:isLgl/>'
    return s + f'<w:suff w:val="{suff}"/><w:lvlText w:val="{text}"/><w:lvlJc w:val="left"/><w:pPr><w:ind {ind}/></w:pPr></w:lvl>'


NUM = f'''<w:numbering xmlns:w="{W}"><w:abstractNum w:abstractNumId="0"><w:multiLevelType w:val="multilevel"/>
{lvl(0, 'chineseCounting', '%1、', 'w:left="0" w:firstLine="0"', style='s416h1')}
{lvl(1, 'decimal', '%1.%2  ', 'w:left="0" w:firstLine="420"', style='s416c1', legal=True)}
{lvl(2, 'decimal', '%1.%2.%3  ', 'w:left="0" w:firstLine="420"', style='s416c2', legal=True)}
{lvl(3, 'decimal', '%4）', 'w:left="0" w:firstLine="420"', style='s416l1')}
{lvl(4, 'decimal', '(%5) ', 'w:left="840" w:firstLine="0"', style='s416l2')}
{lvl(5, 'lowerLetter', '%6) ', 'w:left="840" w:firstLine="0"')}
{lvl(6, 'lowerLetter', '%7.', 'w:left="840" w:firstLine="0"')}
{lvl(7, 'none', '', 'w:left="0" w:firstLine="0"')}
{lvl(8, 'none', '', 'w:left="0" w:firstLine="0"')}
</w:abstractNum><w:num w:numId="1"><w:abstractNumId w:val="0"/></w:num></w:numbering>'''

tpl = os.path.join(OUT, 'templates', 'S416样式模板.docx')
with zipfile.ZipFile(SRC) as zin, zipfile.ZipFile(tpl, 'w', zipfile.ZIP_DEFLATED) as zout:
    for item in zin.infolist():
        data = zin.read(item.filename)
        if item.filename == 'word/document.xml':
            d = etree.fromstring(data); b = d.find(q('body'))
            for e in list(b):
                if e.tag != q('sectPr'): b.remove(e)
            etree.SubElement(b, q('p')).addnext(b.find(q('sectPr')))   # 保留一个空段落
            data = etree.tostring(d, xml_declaration=True, encoding='UTF-8', standalone=True)
        elif item.filename == 'word/styles.xml':
            s = etree.fromstring(data)
            for st in etree.fromstring(STY): s.append(st)
            data = etree.tostring(s, xml_declaration=True, encoding='UTF-8', standalone=True)
        elif item.filename == 'word/numbering.xml':
            data = NUM.encode('utf-8')
        elif item.filename == 'word/header1.xml':
            data = data.replace(b'>XXXX<', '>{{合同编号}}<'.encode('utf-8'))
        elif item.filename in ('word/comments.xml', 'word/commentsExtended.xml', 'word/commentsIds.xml', 'word/people.xml'):
            pass
        zout.writestr(item, data)
print('原子', len(A), '变量', len(VARS), '→', OUT)
