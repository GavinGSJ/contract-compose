# -*- coding: utf-8 -*-
"""PO 模板 2026-10-23 调整（一次性脚本，留作追溯；不要重复运行）。

用法（项目根目录）：python -I new_types/PO/2026-10-23_LOA与附件改造.py <用户上传的新模板.docx>

做了什么：
1. 前言：加入 LOA（中标通知书）段落（文字取自上传的新模板），清单中加入“附件B 技术协议”，“附件B至L”改为“附件C至末位附件”。
2. 附件改为附件库（library/PO/annexes/，A–L 共 12 个，B 技术协议、C 价格明细），编号用字母（类型设置 附件编号格式: 字母）；
   目录中的附件行、前言中的附件清单、条款 / 表格 / 付款条款里写死的“ATTACHMENT B”“附件C”等全部改成自动引用。
3. 项目预设：新增变量 项目中文名、业主中文名、LOA编号、LOA日期；预存库“项目信息”增加项目名称、业主、设施、附加附件。
"""
import os, re, sys, copy, glob
import yaml
from lxml import etree

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
from contract_compose.master_parser import parse

PO = os.path.join(ROOT, 'library', 'PO')
W = 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'
q = lambda t: '{%s}%s' % (W, t)
dump = lambda d: yaml.safe_dump(d, allow_unicode=True, sort_keys=False, width=10000)

# ---------------------------------------------------------------- 附件 A–L（母本 rev04 的写法，B / C 按新模板对调）
ANNEXES = [  # (ID, 文件名, 中文名, 英文名, 跟随变量)
    ('ANX-PSR', '项目特殊要求', '项目特殊要求', 'PROJECT SPECIAL REQUIREMENT', None),
    ('ANX-TA', '技术协议', '技术协议', 'TECHNICAL AGREEMENT', '有技术协议'),
    ('ANX-PRICE', '价格明细', '价格明细及可选项价格', 'DETAILED PRICE LIST AND PROVISIONAL RATES', None),
    ('ANX-SVC-SELLER', '卖方技术人员待遇', '卖方技术人员的服务范围和待遇',
     'EXTENT OF SERVICES AND TREATMENT CONDITIONS OF SELLER’S TECHNICAL PERSONNEL', None),
    ('ANX-SVC-BUYER', '买方技术人员待遇', '买方技术人员的待遇条件', 'TREATMENT CONDITION OF BUYER’S TECHNICAL PERSONNEL', None),
    ('ANX-SHIP', '运输单据要求', '运输单据要求', 'SHIPPING DOCUMENTATION REQUIREMENT', None),
    ('ANX-COMPLIANCE', '合规', '合规：行政和反腐败责任、企业社会责任和人权',
     'COMPLIANCE: Administrative and anti-corruption liability, Corporate Social Responsibility and Human Rights', None),
    ('ANX-PRIVACY', '隐私政策', '隐私政策', 'PRIVACY', None),
    ('ANX-NDA', '保密协议', '签订的保密协议', 'SIGNED NDA', None),
    ('ANX-TEMPLATES', '模板', '模板', 'TEMPLATES', None),
    ('ANX-INTEGRITY', '廉洁承诺书', '廉洁从业承诺书', 'Undertaking of Honest Conduct', None),
    ('ANX-RETURN', '退货和回购条款', '退货和回购条款', 'Return and Buy-back Term', None),
]
OLD_LETTER = dict(zip('ABCDEFGHIJKL', ['ANX-PSR', 'ANX-PRICE', 'ANX-TA', 'ANX-SVC-SELLER', 'ANX-SVC-BUYER', 'ANX-SHIP',
                                       'ANX-COMPLIANCE', 'ANX-PRIVACY', 'ANX-NDA', 'ANX-TEMPLATES', 'ANX-INTEGRITY', 'ANX-RETURN']))


def para_text(p):
    return ''.join(t.text or '' for t in p.iter(q('t')))


def set_text(p, text):
    """段落文字换成 text：保留第一个有文字的 run 的格式，其余 run 清空"""
    runs = [r for r in p.findall(q('r')) if r.find(q('t')) is not None]
    for r in runs[1:]:
        p.remove(r)
    t = runs[0].find(q('t')); t.text = text
    t.set('{http://www.w3.org/XML/1998/namespace}space', 'preserve')


def refs(text):
    """写死的“ATTACHMENT B”“附件C”→ 自动引用（字母按母本 rev04）"""
    text = re.sub(r'ATTACHMENT ([A-L])\b', lambda m: '{{附件_en:%s}}' % OLD_LETTER[m.group(1)], text)
    return re.sub(r'附件([A-L])(?![A-Za-z])', lambda m: '{{附件:%s}}' % OLD_LETTER[m.group(1)], text)


def save_block(path, root):
    open(path, 'wb').write(etree.tostring(root, encoding='utf-8', xml_declaration=True))


def main(new_docx):
    # ---------- 1. 附件库 ----------
    os.makedirs(os.path.join(PO, 'annexes'), exist_ok=True)
    for aid, fn, zh, en, follow in ANNEXES:
        meta = {'id': aid, '名称': zh, '名称_en': en, '类型': '文件', '默认': '有'}
        if follow: meta['跟随变量'] = follow
        open(os.path.join(PO, 'annexes', f'{aid}_{fn}.md'), 'w', encoding='utf-8').write('---\n' + dump(meta) + '---\n')

    # ---------- 2. recipe / type.yaml ----------
    p = os.path.join(PO, 'recipe.yaml'); s = open(p, encoding='utf-8').read()
    assert '\n附件:' not in s
    order = ''.join(f'  - {aid}              # {zh}\n' for aid, _, zh, _, _ in ANNEXES)
    s = s.replace('\n顺序:\n', '\n附件:                          # 附件 A–L；L 之后的附加附件按项目预设（预存库“项目信息”的“附加附件”）\n  顺序:\n' + order + '顺序:\n', 1)
    open(p, 'w', encoding='utf-8').write(s)
    p = os.path.join(PO, 'type.yaml'); s = open(p, encoding='utf-8').read()
    s = s.rstrip('\n') + '\n附件编号格式: 字母                    # 附件A / ATTACHMENT A…\n项目附件字段: 附加附件                  # 预存库“项目信息”中提供各项目附加附件的字段（每行“中文名 | 英文名”）\n'
    open(p, 'w', encoding='utf-8').write(s)

    # ---------- 3. 目录中的附件块：标题 + 一对英文 / 中文行模板 ----------
    p = os.path.join(PO, 'blocks', 'PO-TOC-ANNEX.xml'); root = etree.parse(p).getroot()
    kids = list(root); assert para_text(kids[2]).startswith('ATTACHMENT A') and para_text(kids[27]).startswith('附件M')
    for e in kids[4:]:
        root.remove(e)
    set_text(kids[2], '{{行.英文}}'); set_text(kids[3], '{{行.中文}}')
    save_block(p, root)

    # ---------- 4. 前言 ----------
    M = parse(new_docx)
    texts = [x['text'] for x in M['paras']]
    en = next(t for t in texts if t.startswith('This Procurement Package is evidenced'))
    zh = next(t for t in texts if t.startswith('本采购包已于'))
    for a, b in (('Wison New Energies Co., Ltd.', '{{买方.英文名}}'), ('XXXXXXXXXXX', '{{卖方.英文名}}'),
                 ('(No. XXXX)', '(No. {{LOA编号}})'), ('[DD Month YYYY]', '{{LOA日期_en}}')):
        assert a in en, a; en = en.replace(a, b)
    for a, b in (('惠生清洁能源科技集团股份有限公司', '{{买方.名称}}'), ('XXXXXXXXXXX', '{{卖方.名称}}'),
                 ('编号为XXXX', '编号为{{LOA编号}}'), ('xx年xx月xx日', '{{LOA日期}}')):
        assert a in zh, a; zh = zh.replace(a, b)
    p = os.path.join(PO, 'blocks', 'PO-PREFACE.xml'); root = etree.parse(p).getroot()
    kids = list(root); assert para_text(kids[1]).startswith('This PURCHASE CONTRACT') and para_text(kids[4]).startswith('ATTACHMENT')
    e_en, e_zh = copy.deepcopy(kids[1]), copy.deepcopy(kids[2])
    set_text(e_en, en); set_text(e_zh, zh)
    kids[2].addnext(e_zh); kids[2].addnext(e_en)                      # LOA 段落放在原有两段之后
    set_text(kids[4], '{{附件_en:ANX-PSR}} PROJECT SPECIAL REQUIREMENTS{{附件:ANX-PSR}}项目特殊条款')
    line_b = copy.deepcopy(kids[4]); set_text(line_b, '{{附件_en:ANX-TA}} TECHNICAL AGREEMENT{{附件:ANX-TA}}技术协议')
    kids[4].addnext(line_b)                                            # 附件B 技术协议在合同条款之前
    assert para_text(kids[6]).startswith('ATTACHMENT B to L')
    set_text(kids[6], '{{附件_en:ANX-PRICE}} to {{附件号:末位}} (unless otherwise mentioned) {{附件:ANX-PRICE}}至{{附件号:末位}}（除非另有说明）')
    save_block(p, root)

    # ---------- 5. 条款、表格、付款条款中写死的附件字母 → 自动引用 ----------
    changed = []
    for p in sorted(glob.glob(os.path.join(PO, 'atoms', '*.md'))):
        s = open(p, encoding='utf-8').read(); n = refs(s)
        if n != s:
            open(p, 'w', encoding='utf-8').write(n); changed.append(os.path.basename(p))
    for p in sorted(glob.glob(os.path.join(PO, 'tables', '*.xml'))):
        root = etree.parse(p).getroot(); hit = False
        for para in root.iter(q('p')):
            t = para_text(para); n = refs(t)
            if n != t:
                set_text(para, n); hit = True
        if hit:
            save_block(p, root); changed.append(os.path.basename(p))
    p = os.path.join(ROOT, 'library', 'common', 'payment_terms.yaml')
    lines = open(p, encoding='utf-8').read().split('\n')
    for i, l in enumerate(lines):
        if re.match(r'\s+PO_', l) and refs(l) != l:                     # 只改 PO 的付款单据（FA 另有自己的附件引用）
            lines[i] = refs(l); changed.append(f'payment_terms.yaml:{i + 1}')
    open(p, 'w', encoding='utf-8').write('\n'.join(lines))
    print('已改引用：', '、'.join(changed))

    # ---------- 6. 中文条款中的项目名称、业主 ----------
    p = glob.glob(os.path.join(PO, 'atoms', 'DEF-00_*.md'))[0]; s = open(p, encoding='utf-8').read()
    for a, b in (('业主是指{{业主名称}}或其许可', '业主是指{{业主中文名}}或其许可'), ('项目：{{项目名称}}', '项目：{{项目中文名}}'),
                 ('- 业主名称\n', '- 业主名称\n- 业主中文名\n'), ('- 项目名称\n', '- 项目名称\n- 项目中文名\n')):
        assert s.count(a) == 1, a; s = s.replace(a, b)
    open(p, 'w', encoding='utf-8').write(s)

    # ---------- 7. 变量 ----------
    from contract_compose.library import load_library
    V0 = load_library('PO').V
    p = os.path.join(PO, 'variables.yaml'); head = open(p, encoding='utf-8').readline()
    V = yaml.safe_load(open(p, encoding='utf-8')) or {}
    def zh_var(src, desc, atom):
        return {'默认值': '', '说明': desc, '原子': [atom], '类别': '有默认值', '类型': '值', '缺省取自': src,
                **({'母本值': V0[src]['母本值']} if V0.get(src, {}).get('母本值') else {})}
    V['项目中文名'] = zh_var('项目名称', '项目名称（中文，用于中文条款）；不填时用英文项目名称', 'DEF-00')
    V['业主中文名'] = zh_var('业主名称', '业主名称（中文，用于中文条款）；不填时用英文业主名称', 'DEF-00')
    V['LOA编号'] = {'默认值': '', '说明': '中标通知书（LOA）编号', '原子': ['PO-PREFACE'], '类别': '必填', '类型': '值', '母本值': 'XXXX'}
    V['LOA日期'] = {'默认值': '', '说明': '中标通知书签署日期（中文），如 2026年8月1日', '原子': ['PO-PREFACE'], '类别': '必填', '类型': '值',
                  '母本值': 'xx年xx月xx日'}
    V['LOA日期_en'] = {'默认值': '', '说明': '中标通知书签署日期（英文），如 1 August 2026', '原子': ['PO-PREFACE'], '类别': '必填', '类型': '值',
                     '母本值': '[DD Month YYYY]'}
    open(p, 'w', encoding='utf-8').write(head + dump(V))

    # ---------- 8. 预存库“项目信息” ----------
    p = os.path.join(ROOT, 'library', 'common', 'presets', '项目信息.yaml'); d = yaml.safe_load(open(p, encoding='utf-8'))
    d['说明'] = '按项目代号预设的项目信息；合同表单填写“项目编号”后自动带出（项目名称、业主、设施、3.4 b) 质量保证期条款、PO 的附加附件）'
    d['带入变量'] = ['项目名称', '项目中文名', '业主名称', '业主中文名', '设施简称', '设施全称', '设施全称_en']
    d['多行字段'] = ['质保期', '质保期_en', '附加附件']
    d['字段'] = {'项目名称': '项目名称（英文）', '项目中文名': '项目名称（中文，不填用英文）', '业主名称': '业主（英文）', '业主中文名': '业主（中文，不填用英文）',
               '设施简称': '设施简称（如 FPSO）', '设施全称': '设施全称（中文）', '设施全称_en': '设施全称（英文）',
               '附加附件': 'PO 附件 L 之后的附加附件（每行一个：中文名 | 英文名）', **d['字段']}
    info = {
        'F484': {'项目名称': 'BALEINE III FPSO PROJECT', '项目中文名': 'BALEINE 三期 FPSO 项目', '业主名称': 'Eni', '业主中文名': '埃尼',
                 '设施简称': 'FPSO', '设施全称': '浮式生产储卸油装置', '设施全称_en': 'Floating Production, Storage and Offloading unit',
                 '附加附件': '职业健康，安全和环境保护要求 | HEALTH, SAFETY AND ENVIRONMENT REQUIREMENTS\n网络安全要求 | CYBER SECURITY REQUIREMENTS'},
        'F520': {'项目名称': 'ARGENTINA LNG (ArLNG) Project', '项目中文名': 'ARGENTINA LNG (ArLNG) Project',
                 '业主名称': 'YPF S.A. and ENI and/or jointly with other possible partner(s)', '业主中文名': 'YPF S.A. 和ENI和/或联合其他潜在合作伙伴',
                 '设施简称': 'FLNG', '设施全称': '浮式液化生产设施', '设施全称_en': 'floating liquefaction production facility', '附加附件': ''},
        'F502': {'附加附件': '物资运输、包装和标识管理规程 | Instruction on Management of Material Transport, Package and Marking'},
    }
    for code, e in d['条目'].items():
        new = {k: '' for k in d['带入变量'] + ['附加附件']}
        new.update(info.get(code, {}))
        d['条目'][code] = {**new, **e}
    open(p, 'w', encoding='utf-8').write('# 预存信息库（可在表单“预存信息管理”页面中编辑）\n' + dump(d))


if __name__ == '__main__':
    main(sys.argv[1])
