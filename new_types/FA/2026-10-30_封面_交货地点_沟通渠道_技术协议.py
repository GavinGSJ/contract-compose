# -*- coding: utf-8 -*-
"""FA 框架合同 2026-10-30 调整（一次性脚本，留作追溯；不要重复运行）。

依据：用户上传的 F484EC-02-0103-M-0039（Topside 无缝钢结构管）带修订的合同，以及用户的 7 条要求：
1. 封面合同名称加上采购包（标的物）的中英文名称：“{{标的物名称}}框架采购合同 / Frame Master Contract for {{标的物名称_en}}”。
2. 目录中每个附件的名称可按合同修改（程序 + 表单，本脚本不涉及）。
3. 1.2 中技术协议的编号、版本、日期写入正文（原来写死 N/A）；1.1 的括号改为中文标签。
4. 2.4 计算方法在表单“① 必填信息”中选择。
5. 5.4 交货地点：默认惠生场地（地址可改），或自定义；不再跟随贸易术语。
6. 第 18 章 买卖双方沟通渠道可选（不选时整章不出现）。
7. 4.1 价款表序号 1 的“预估总金额合计”取不含税价。
"""
import os, re, glob
import yaml

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
L = os.path.join(ROOT, 'library', 'FA')
dump = lambda d: yaml.safe_dump(d, allow_unicode=True, sort_keys=False, width=10000)


def rw(p, fn):
    s = open(p, encoding='utf-8').read(); n = fn(s)
    assert n != s, p
    open(p, 'w', encoding='utf-8').write(n)


def sub1(s, a, b):
    assert s.count(a) == 1, a[:40]
    return s.replace(a, b)


# ---- 1 封面
rw(os.path.join(L, 'blocks', 'FA-COVER.xml'), lambda s: sub1(sub1(
    s, '<w:t>框架采购合同</w:t>', '<w:t>{{标的物名称}}框架采购合同</w:t>'),
    '<w:t>Frame Master Contract</w:t>', '<w:t>Frame Master Contract for {{标的物名称_en}}</w:t>'))

# ---- 7 价款表序号 1 行：预估总金额合计取不含税价（该行是表中唯一的“{{价款_含税_表}}”前三次出现中的第一次）
def price(s):
    i = s.index('{{价款_含税_表}}')
    assert s.count('{{价款_含税_表}}') == 2
    return s[:i] + '{{价款_不含税_表}}' + s[i + len('{{价款_含税_表}}'):]
rw(os.path.join(L, 'tables', 'PRI-01-T1.xml'), price)

# ---- 6 沟通渠道：选项 + 配方
open(os.path.join(L, 'options', '沟通渠道.yaml'), 'w', encoding='utf-8').write(dump({
    '名称': '第 18 章 买卖双方沟通渠道',
    '类型': '文字',
    '位置': '第 18 章（COM-00 至 COM-02）',
    '说明': '选“不包含”时整章不出现（目录、章号随之调整），不标注不适用',
    '表单位置': '必填信息',
    '默认': '包含',
    '选项': {'包含': {'名称': '包含', '中文': '包含'}, '不包含': {'名称': '不包含', '中文': '不包含'}},
}))
rp = os.path.join(L, 'recipe.yaml')
r = open(rp, encoding='utf-8').read()
for a in ('COM-00', 'COM-01', 'COM-01-1', 'COM-01-2', 'COM-01-3', 'COM-01-4', 'COM-01-5', 'COM-02'):
    r = sub1(r, f'- 原子: {a}\n', f'- 原子: {a}\n  仅当选项: {{沟通渠道: 包含}}\n  不符时: 不出现\n')
open(rp, 'w', encoding='utf-8').write(r)

# ---- 5 交货地点：选项 + 变量
open(os.path.join(L, 'options', '交货地点.yaml'), 'w', encoding='utf-8').write(dump({
    '名称': '交货地点',
    '位置': 'DEL-04（5.4）',
    '类型': '句内',
    '默认': '惠生场地',
    '说明': '默认惠生场地（地址在下方可改）；也可选“自定义”填写中英文交货地点',
    '表单位置': '必填信息',
    '选项': {
        '惠生场地': {'名称': '惠生场地（或买方指定的施工现场、仓库）',
                  '中文': '{{交货场地}}或者买方指定的施工现场或仓库',
                  '英文': '{{交货场地_en}} or any construction site or warehouse designated by the BUYER.',
                  '变量': ['交货场地', '交货场地_en']},
        '买方现场': {'名称': '买方的施工现场或仓库（模板原文）',
                  '中文': '买方的施工现场或仓库',
                  '英文': "The BUYER's construction site or warehouse."},
        '自定义': {'名称': '自定义（填写中英文交货地点）',
                 '中文': '{{交货地点_自定义}}',
                 '英文': '{{交货地点_自定义_en}}',
                 '变量': ['交货地点_自定义', '交货地点_自定义_en']},
    },
}))
vp = os.path.join(L, 'variables.yaml')                     # 文本方式修改，保留文件中的注释和顺序
def vblock(name, default, desc, atom, cat, typ='值', extra=''):
    return (f"{name}:\n  默认值: {default}\n  说明: {desc}\n  原子:\n  - {atom}\n  类别: {cat}\n  类型: {typ}\n{extra}")
def var(s):
    old = re.search(r'交货地点:\n(?:  .*\n|  - .*\n)+', s)
    assert old
    s = s.replace(old.group(0), vblock('交货地点', '惠生场地', '5.4 交货地点的写法', 'DEL-04', '选项', '选项', '  选项库: options/交货地点.yaml\n'))
    s = s.replace('计算方法:\n  默认值: a\n  说明: 根据不同结算方式进行选择', '计算方法:\n  默认值: a\n  说明: 2.4 的结算方式（在表单“① 必填信息”中选择）')
    add = (vblock('交货场地', '惠生启东场地（江苏省南通市启东市吕四港经济开发区卫海大道18号）', '惠生场地的名称和地址（中文）', 'DEL-04', '有默认值')
           + vblock('交货场地_en', "'Wison Qidong Site (Address: No. 18 Weihai Avenue, Lvsi Port Economic Development Zone, Qidong, Nantong, Jiangsu, China)'", '惠生场地的名称和地址（英文）', 'DEL-04', '有默认值')
           + vblock('交货地点_自定义', "''", '交货地点选“自定义”时填写的中文', 'DEL-04', '必填')
           + vblock('交货地点_自定义_en', "''", '交货地点选“自定义”时填写的英文', 'DEL-04', '必填')
           + vblock('沟通渠道', '包含', '第 18 章是否出现', 'COM-00', '选项', '选项', '  选项库: options/沟通渠道.yaml\n'))
    return s.rstrip('\n') + '\n' + add
rw(vp, var)
# 公共变量：技术协议的编号、版本、日期现在也用在 1.2
def ta(s):
    for name in ('技术协议号', '技术协议版本', '技术协议日期'):
        s = re.sub(r'(%s:\n(?:  .*\n)*?  原子:\n  - GEN-01\n)' % name, r'\1  - GEN-02\n', s, count=1)
    return s
rw(os.path.join(ROOT, 'library', 'common', 'variables.yaml'), ta)

# ---- 4 计算方法放到必填信息
rw(os.path.join(L, 'options', '计算方法.yaml'), lambda s: sub1(s, '显示方式: 字母加列表\n', '显示方式: 字母加列表\n表单位置: 必填信息\n'))

# ---- 3 技术协议：1.2 写入编号 / 版本 / 日期
rw(glob.glob(os.path.join(L, 'atoms', 'GEN-02_*.md'))[0], lambda s: sub1(sub1(
    s, '编号：<u>N/A，版本：N/A，日期：N/A</u>）', '编号：{{技术协议号}}，版本：{{技术协议版本}}，日期：{{技术协议日期}}）'),
    'No. <u>N/A, Rev. N/A, Date: N/A</u>)', 'No. {{技术协议号}}, Rev. {{技术协议版本}}, Date: {{技术协议日期}})'))
print('完成')
