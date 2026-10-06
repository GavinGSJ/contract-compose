# -*- coding: utf-8 -*-
"""页面：合同生成（FA 框架合同 / PO 实采合同，由 app.py 调用）"""
import os, re, io, glob, datetime
import yaml
import streamlit as st

from contract_compose import assembler as asm, paths

# ---------------- 读取原子库（按所选合同类型） ----------------
TYPE_NAMES = {'FA': 'FA 框架合同', 'PO': 'PO 实采合同'}
TYPES = [t for t in asm.TYPES if os.path.exists(os.path.join(paths.type_dir(t), paths.RECIPE))]
if st.session_state.get('ctype') not in TYPES: st.session_state['ctype'] = TYPES[0]
CT = st.session_state['ctype']
atoms, opts, V, recipe, entities = asm.load_library(CT)
conditions = sorted({it['条件'] for it in recipe['顺序'] if it.get('条件')})

GROUPS = {
    '合同信息': ['合同编号', '项目编号', '项目名称', '业主名称', '设施简称', '设施全称', '标的物名称', '签订日期'],
    '卖方信息': [k for k in ('卖方.名称', '卖方.英文名', '卖方.地址', '卖方.电话', '卖方.传真', '卖方.邮编', '卖方.开户行', '卖方.账号', '卖方.信用代码', '卖方.SWIFT') if k in V]
             + sorted(k for k in V if k.startswith('卖方.') and k not in ('卖方.名称', '卖方.英文名', '卖方.地址', '卖方.电话', '卖方.传真', '卖方.邮编', '卖方.开户行', '卖方.账号', '卖方.信用代码', '卖方.SWIFT') and not k.endswith('_en')),
    '交货': ['交货期天数', '交货日期'],
}
LABEL = {'预付款_文件数': '预付款前需收到的文件数', '预付款_天数': '收到文件后支付预付款的天数（日历日）',
         '交货期天数': '每批订单生效后交货天数', '签订日期': '签订日期'}
PCT = {'履约保函比例'}
PAY_VARS = [k for k, v in V.items() if v.get('类别') == '付款' and v.get('类型') == '值']
PAY = asm.PAY
_auto_node = asm.for_type(PAY.get('质保金模式追加'), CT)
PAY_NODE_NAMES = {n: asm.pay_node(n)['名称'] for n in asm.pay_nodes_available() if n != _auto_node}
PAY_NAME_TO_ID = {v: k for k, v in PAY_NODE_NAMES.items()}

BOND = '履约保函比例'; BOND_ATOM = recipe.get('履约保函条款')     # 该类型合同没有履约保函条款时为 None
required = [k for k, v in V.items() if v.get('类型') == '值' and v.get('类别') == '必填' and not k.endswith('_en') and k != BOND]
GROUPS = {g: [k for k in names if k in V] for g, names in GROUPS.items()}
grouped = {k for g in GROUPS.values() for k in g}
GROUPS['其他必填'] = [k for k in required if k not in grouped]
defaults = [k for k, v in V.items() if v.get('类型') == '值' and v.get('类别') == '有默认值' and not k.endswith('_en')]
_pos = {it['原子']: i for i, it in enumerate(recipe['顺序']) if '原子' in it}
option_vars = sorted([k for k, v in V.items() if v.get('类型') == '选项' and v.get('类别') != '付款'],
                     key=lambda k: _pos.get(str(V[k].get('原子', [''])[0]), 999))

# 可标注“不适用”的条款（付款条款与履约保函单独处理）
ALL_ORDER = [it['原子'] for it in recipe['顺序'] if '原子' in it]
REFS = asm.numbering(atoms, ALL_ORDER, recipe.get('编号起始', 1))
COND_ATOMS = {it['原子'] for it in recipe['顺序'] if it.get('条件') or it.get('仅当选项')}
NA_LABEL = {f"{REFS[a]}　{atoms[a]['meta']['名称']}": a for a in ALL_ORDER
            if a not in asm.NA_EXCLUDE and a != BOND_ATOM and a not in COND_ATOMS}
NA_ID_TO_LABEL = {v: k for k, v in NA_LABEL.items()}

CFG_DIR = paths.CONFIGS; OUT_DIR = paths.OUTPUT
os.makedirs(CFG_DIR, exist_ok=True); os.makedirs(OUT_DIR, exist_ok=True)


def key(name): return 'v::' + name


AUTO = '（自动）'
def label_of(name, i):
    o = opts[name]; x = o['选项'][i]
    if o['类型'] == '字母选择':
        return f"{i}) {x.get('中文') or x.get('列表文字', '')}"
    s = x.get('名称') or x.get('中文') or i
    return f'{i}：{s}' + ('（待补）' if x.get('状态') == '待补' else '')
OPT_LABELS, LABEL_TO_ID = {}, {}
for _n in option_vars + ['付款方式', '质保方式']:
    _o = opts[_n]; _auto = bool(_o.get('跟随变量') or _o.get('项目预设'))
    LABEL_TO_ID[_n] = {label_of(_n, i): i for i in _o['选项']}
    OPT_LABELS[_n] = ([AUTO] if _auto else []) + list(LABEL_TO_ID[_n])


# ---------------- 载入已保存的配置 ----------------
def load_cfg():
    """选择已保存的合同：先切换合同类型，下一次运行时（已载入该类型的原子库）再填入表单"""
    f = st.session_state.get('cfg_file')
    if not f or f == '（新合同）':
        return
    cfg = yaml.safe_load(open(os.path.join(CFG_DIR, f), encoding='utf-8')) or {}
    st.session_state['ctype'] = cfg.get('合同类型') or 'FA'
    st.session_state['_pending_cfg'] = cfg


def apply_cfg(cfg):
    for k in list(st.session_state):
        if k.startswith(('v::', 'o::')): del st.session_state[k]
    for k, v in (cfg.get('变量') or {}).items():
        st.session_state[key(k)] = '' if v is None else str(v)
    for k, v in (cfg.get('选项') or {}).items():
        if k in opts and str(v) in opts[k]['选项']:
            st.session_state['o::' + k] = label_of(k, str(v))
    st.session_state['pay_nodes'] = [PAY_NODE_NAMES[n] for n in (cfg.get('选项') or {}).get('付款节点', []) if n in PAY_NODE_NAMES]
    st.session_state['_pending_docs'] = list((cfg.get('选项') or {}).get('付款可选单据') or [])
    if cfg.get('买方主体') in entities: st.session_state['entity'] = cfg['买方主体']
    st.session_state['ta'] = str((cfg.get('变量') or {}).get('有技术协议', '是')) != '否'
    for c in conditions: st.session_state['c::' + c] = c in (cfg.get('条件') or [])
    na = cfg.get('不适用') or []
    if BOND_ATOM: st.session_state['bond'] = BOND_ATOM not in na
    st.session_state['na'] = [NA_ID_TO_LABEL[a] for a in na if a in NA_ID_TO_LABEL]


if '_pending_cfg' in st.session_state:
    apply_cfg(st.session_state.pop('_pending_cfg'))


def change_type():
    for k in list(st.session_state):           # 换合同类型时清空条款写法与付款设置，以及未改动过的默认值
        if k.startswith('o::') or k in ('pay_nodes', 'pay_docs', 'na'): del st.session_state[k]
        elif k.startswith('v::') and str(st.session_state[k]) == str(V.get(k[3:], {}).get('默认值', '')):
            del st.session_state[k]


# ---------------- 页面 ----------------
st.header(f'{TYPE_NAMES.get(CT, CT)}生成')
st.caption('只需填写本份合同的信息；条款、顺序、编号按模板自动生成。未填写的必填项会在 Word 中以黄色【待填】标出。')

top = st.columns([1.3, 2, 2, 3])
top[0].selectbox('合同类型', TYPES, key='ctype', format_func=lambda t: TYPE_NAMES.get(t, t), on_change=change_type)
saved = ['（新合同）'] + sorted(os.path.basename(p) for p in glob.glob(os.path.join(CFG_DIR, '*.yaml')))
top[1].selectbox('打开已保存的合同', saved, key='cfg_file', on_change=load_cfg)
if st.session_state.get('entity') not in entities and entities: st.session_state['entity'] = next(iter(entities))
top[2].selectbox('买方主体', list(entities) or ['（预存库为空）'], key='entity', help='在左侧“预存信息管理”中新增或修改')
with top[3]:
    if conditions: st.write('合同范围')
    for c in conditions:
        st.checkbox(f'{c}（不勾选时相关章节保留并标注不适用）', key='c::' + c)


def field(col, name, en=False):
    k = name + ('_en' if en else '')
    v = V.get(k, {})
    label = ('英文' if en else LABEL.get(name, name.replace('卖方.', '')))
    if not en and name in PCT: label += '（%）'
    ph = v.get('说明') or ''
    col.text_input(label, key=key(k), placeholder=ph)


tabs = st.tabs(['① 必填信息', '② 条款写法', '③ 默认条款参数'])

with tabs[0]:
    for g, names in GROUPS.items():
        if not names: continue
        st.subheader(g)
        if g == '卖方信息':
            cols = st.columns(2)
            for i, name in enumerate(n for n in names if n in V):
                field(cols[i % 2], name)
            continue
        for name in names:
            if name not in V: continue
            if name + '_en' in V:
                c1, c2 = st.columns(2); field(c1, name); field(c2, name, en=True)
            else:
                c1, _ = st.columns(2); field(c1, name)

    # ---------------- 付款方式 ----------------
    # ---------------- 合同价款 ----------------
    st.subheader('合同价款')
    ss = st.session_state
    CUR = list(asm.CURRENCIES); RATES = [AUTO] + asm.TAX_RATES
    if ss.get(key('币种')) not in CUR: ss[key('币种')] = 'RMB'
    if ss.get(key('增值税率')) not in RATES: ss[key('增值税率')] = AUTO
    c1, c2, c3 = st.columns(3)
    c1.selectbox('币种', CUR, key=key('币种'), help='RMB 人民币 / USD 美元 / EUR 欧元 / GBP 英镑')
    c2.selectbox('增值税率', RATES, key=key('增值税率'), help='（自动）= 人民币 13%，外币不涉及增值税')
    c3.text_input('含税总价', key=key('含税总价'), placeholder='如 1130000 或 1,130,000.00')
    _pc = asm.price_calc(ss.get(key('含税总价')), ss[key('币种')], ss[key('增值税率')])
    if str(ss.get(key('含税总价'), '')).strip():
        if '含税' in _pc:
            _sym = asm.CURRENCIES[_pc['币种']][0]
            st.info(f"不含税：{asm.fmt_money(_pc['不含税'], _sym)}　｜　"
                    f"增值税（{_pc['税率'] if _pc['计税'] else 'N/A'}）：{asm.fmt_money(_pc['税额'], _sym) if _pc['计税'] else 'N/A'}　｜　"
                    f"含税：{asm.fmt_money(_pc['含税'], _sym)}\n\n"
                    f"{asm.CURRENCIES[_pc['币种']][1]}大写：{asm.cn_upper(_pc['含税'])}\n\n"
                    f"{_pc['币种']} {asm.en_words(_pc['含税'])}")
        else:
            st.error('含税总价只能填数字（可带千分位逗号）。')

    # ---------------- 技术协议 ----------------
    st.subheader('技术协议')
    if 'ta' not in ss: ss['ta'] = True
    st.checkbox('本合同有技术协议', key='ta', help='不勾选时，1.1 合同组成及目录中的“附件五 技术协议”标注不适用，其余条款原样保留')
    if ss['ta']:
        c1, c2, c3 = st.columns(3)
        c1.text_input('技术协议号', key=key('技术协议号'))
        c2.text_input('版本号', key=key('技术协议版本'), placeholder='如 Rev.0')
        c3.text_input('日期', key=key('技术协议日期'), placeholder='如 2026-10-06')
    TA_FIELDS = ['技术协议号', '技术协议版本', '技术协议日期'] if ss['ta'] else []
    st.session_state['_extra'] = ['币种', '含税总价'] + TA_FIELDS

    st.subheader('付款方式')
    def pay_select(name, label, horizontal=False):
        labels = OPT_LABELS[name]
        if st.session_state.get('o::' + name) not in labels:
            st.session_state['o::' + name] = label_of(name, str(opts[name]['默认']))
        if horizontal:
            st.radio(label, labels, key='o::' + name, horizontal=True)
        else:
            st.selectbox(label, labels, key='o::' + name)
        return LABEL_TO_ID[name][st.session_state['o::' + name]]
    c1, c2 = st.columns(2)
    with c1: plan = pay_select('付款方式', '付款方案')
    with c2: mode = pay_select('质保方式', '质保担保方式', horizontal=True)
    if plan == '自定义':
        st.multiselect('选择付款节点（按合同顺序自动排列）', list(PAY_NODE_NAMES.values()), key='pay_nodes')
    pay_choice = {'付款方式': plan, '质保方式': mode,
                  '付款节点': [PAY_NAME_TO_ID[x] for x in st.session_state.get('pay_nodes', [])]}
    nodes, _ = asm.payment_nodes(opts['付款方式'], plan, opts, {}, pay_choice)
    st.caption('付款顺序：' + ' → '.join(asm.pay_node(n)['名称'] for n in nodes) if nodes else '请选择付款节点')
    _opt_docs = asm.pay_optional_docs(nodes)
    if _opt_docs:
        _dl = {t[:70]: d for d, t in _opt_docs}
        if '_pending_docs' in st.session_state:
            _ids = st.session_state.pop('_pending_docs'); st.session_state['pay_docs'] = [l for l, d in _dl.items() if d in _ids]
        st.session_state['pay_docs'] = [x for x in st.session_state.get('pay_docs', []) if x in _dl]
        st.multiselect('加入的可选单据（母本中标为“可选/Optional”的单据）', list(_dl), key='pay_docs')
        pay_choice['付款可选单据'] = [_dl[x] for x in st.session_state['pay_docs']]
    pay_fields = [f for f in asm.pay_fields(opts['付款方式'], plan, opts, pay_choice) if f in V] if nodes else []
    PAY_LABEL = {'预付款比例': '预付款（%）', '进度款比例': '进度款（%）', '发货款比例': '发货款（%）', '到货款比例': '到货款（%）',
                 '调试款比例': '调试款（%）', '质保比例': '质保款（%）' if CT == 'PO' else '质保函 / 质保金（%）',
                 '付款天数': '收到单据后付款天数', '完工文件_原件份数': '完工文件原件份数', '完工文件_电子份数': '完工文件电子版份数',
                 '预付款_文件数': '预付款前需收到的文件数', '预付款_天数': '收到文件后支付预付款的天数',
                 '进度款_主材名称': '进度款：主要材料或构件名称', '信用证_开证提前天数': '信用证：装运前开证天数',
                 '质保金_释放天数': '质保金：申请后释放天数'}
    cols = st.columns(3)
    for i, f in enumerate(pay_fields):
        if key(f) not in st.session_state and V[f].get('默认值') not in (None, ''):
            st.session_state[key(f)] = str(V[f]['默认值'])
        cols[i % 3].text_input(PAY_LABEL.get(f, f), key=key(f), placeholder=V[f].get('说明') or '')
    if BOND_ATOM:
        if 'bond' not in st.session_state: st.session_state['bond'] = True
        b1, b2 = st.columns([1, 2])
        b1.checkbox('本合同需要履约保函', key='bond', help='不勾选时，履约保函条款仍保留在合同中并标注不适用')
        if st.session_state['bond']:
            field(b2, BOND); pay_fields.append(BOND)
        else:
            b2.caption('履约保函条款保留，标注“不适用”，比例写 N/A。')
    st.session_state['_pay'] = (pay_choice, pay_fields, nodes)
    nums, bad_num = [], False
    for n in nodes:
        sv = st.session_state.get(key(asm.pay_node(n)['比例变量']), '').strip()
        if sv:
            try: nums.append(float(sv))
            except ValueError: bad_num = True
    if nums and not bad_num:
        tot = sum(nums)
        parts = ' + '.join(asm.pay_node(n)['名称'].split('（')[0] for n in nodes)
        (st.success if abs(tot - 100) < 1e-6 else st.warning)(
            f'{parts} = {tot:g}%' + ('' if abs(tot - 100) < 1e-6 else '，不等于 100%'))

with tabs[1]:
    st.caption('不改动则使用模板默认写法。')
    for name in option_vars:
        o = opts[name]
        hint = ''
        if o.get('跟随变量'): hint = f"自动：跟随“{o['跟随变量']}”"
        elif o.get('项目预设'): hint = '自动：按项目编号预设，没有预设时用默认'
        labels = OPT_LABELS[name]
        cur = st.session_state.get('o::' + name)
        if cur not in labels:
            st.session_state['o::' + name] = labels[0] if hint else label_of(name, str(o['默认']))
        st.selectbox(f"{o.get('名称', name)}　·　{o.get('位置', '')}", labels, key='o::' + name,
                     help=hint or o.get('说明') or None)
        sid = LABEL_TO_ID[name].get(st.session_state['o::' + name])
        if sid and o['选项'][sid].get('状态') == '待补':
            st.warning('该写法还没有条款文字，请先在选项库中补充，或选择其他写法。')
        if name == '质保期':
            pid = str(st.session_state.get(key('项目编号'), '')).strip()
            eff = sid or asm.choose(name, o, {'项目编号': pid}, {})
            if eff == '自定义':
                c1, c2 = st.columns(2)
                c1.text_area('自定义质保期条款（中文）', key=key('质保期_自定义'), height=120,
                             placeholder='如：供货、合同货物的……质保期应为……，以先到者为准。')
                c2.text_area('自定义质保期条款（英文）', key=key('质保期_自定义_en'), height=120,
                             placeholder='e.g. The warranty period of the SUPPLY ... whichever comes first.')
            else:
                if not sid:
                    src = (f'项目编号 {pid} 的预设' if pid.upper() in o.get('项目预设', {})
                           else (f'项目编号“{pid}”没有预设，使用模板原文（可在“预存信息管理 → 项目信息”中新增）' if pid
                                 else '尚未填写项目编号，使用模板原文'))
                    st.caption('自动选用：' + src)
                st.markdown(f"> {o['选项'][eff]['中文']}\n>\n> {o['选项'][eff]['英文']}")

    st.divider()
    st.multiselect('标注为不适用的条款（条款保留在合同中，标题后注明“不适用”）', list(NA_LABEL), key='na',
                   help='付款条款不在此列：未选用的付款节点不会出现在合同中。')

with tabs[2]:
    st.caption('一般保持默认；谈判有变化时再修改。')
    cols = st.columns(3)
    for i, name in enumerate(defaults):
        k = key(name)
        if k not in st.session_state: st.session_state[k] = str(V[name].get('默认值', ''))
        cols[i % 3].text_input(name, key=k, help=V[name].get('说明') or None)
        if name + '_en' in V:
            ke = key(name + '_en')
            if ke not in st.session_state: st.session_state[ke] = str(V[name + '_en'].get('默认值', ''))
            cols[i % 3].text_input(name + '（英文）', key=ke)


# ---------------- 生成 ----------------
def collect():
    pay_choice, pay_fields, nodes = st.session_state['_pay']
    order = [n for g in GROUPS.values() for n in g] + st.session_state.get('_extra', []) + pay_fields + defaults
    order = [x for n in order for x in (n, n + '_en')]
    vals = {}
    for n in order:
        v = str(st.session_state.get(key(n), '')).strip()
        if v: vals[n] = v
    sel = {'付款方式': pay_choice['付款方式'], '质保方式': pay_choice['质保方式']}
    if pay_choice.get('付款可选单据'): sel['付款可选单据'] = pay_choice['付款可选单据']
    if pay_choice['付款方式'] == '自定义': sel['付款节点'] = pay_choice['付款节点']
    for name in option_vars:
        sid = LABEL_TO_ID[name].get(st.session_state.get('o::' + name))
        if sid: sel[name] = sid
    if sel.get('质保期') == '自定义':
        for k in ('质保期_自定义', '质保期_自定义_en'):
            v = str(st.session_state.get(key(k), '')).strip()
            if v: vals[k] = v
    if st.session_state.get(key('增值税率')) not in (None, AUTO):
        vals['增值税率'] = st.session_state[key('增值税率')]
    vals['有技术协议'] = '是' if st.session_state.get('ta', True) else '否'
    cfg = {'合同类型': CT, '买方主体': st.session_state.get('entity'),
           '条件': [c for c in conditions if st.session_state.get('c::' + c)],
           '选项': sel, '变量': vals}
    na = [NA_LABEL[x] for x in st.session_state.get('na', []) if x in NA_LABEL]
    if BOND_ATOM and not st.session_state.get('bond', True): na.append(BOND_ATOM)
    if na: cfg['不适用'] = sorted(na, key=ALL_ORDER.index)
    return cfg


st.divider()
cfg = collect()
pay_req = [asm.pay_node(n)['比例变量'] for n in st.session_state['_pay'][2]] + ([BOND] if BOND_ATOM and st.session_state.get('bond', True) else [])
_custom = ['质保期_自定义', '质保期_自定义_en'] if cfg['选项'].get('质保期') == '自定义' else []
miss = [k for k in required + pay_req + _custom + [x for x in st.session_state.get('_extra', []) if x != '币种'] if k not in cfg['变量']] + \
       [k + '_en' for k in required if k + '_en' in V and k + '_en' not in cfg['变量']]
bad = [n for n, s in cfg['选项'].items() if n in option_vars and opts[n]['选项'][s].get('状态') == '待补']
if not st.session_state['_pay'][2]: bad.append('付款节点')
c1, c2 = st.columns([1, 3])
go = c1.button('生成合同', type='primary', disabled=bool(bad))
c2.write(f'必填项还有 **{len(miss)}** 项未填' + ('，生成后会在 Word 中标黄。' if miss else '。'))
if miss:
    with c2.expander('查看未填项'):
        st.write('、'.join(miss))

if go:
    v = cfg['变量']
    stem = re.sub(r'[\\/:*?"<>|]', '_', f"{v.get('合同编号', '未编号')}_{v.get('标的物名称', '')}".strip('_'))
    stamp = datetime.datetime.now().strftime('%Y%m%d-%H%M')
    cfg['输出文件名'] = f'{stem}.docx'
    with open(os.path.join(CFG_DIR, f'{stem}.yaml'), 'w', encoding='utf-8') as f:
        f.write(f'# 由表单保存于 {stamp}\n' + yaml.safe_dump(cfg, allow_unicode=True, sort_keys=False, width=1000))
    try:
        doc, used, missing, order, na = asm.build(cfg)
    except SystemExit as e:
        st.error(str(e)); st.stop()
    out = os.path.join(OUT_DIR, cfg['输出文件名'])
    try:
        doc.save(out)
    except PermissionError:
        out = os.path.join(OUT_DIR, f'{stem}_{stamp}.docx'); doc.save(out)
    buf = io.BytesIO(); doc.save(buf)
    st.success(f'已生成：output\\{os.path.basename(out)}（{len(order)} 个条款原子）；配置已保存到 configs\\{stem}.yaml')
    if na:
        st.info('标注不适用：' + '、'.join(f'{REFS[a]} {atoms[a]["meta"]["名称"]}' for a in na))
    if missing:
        st.warning(f'Word 中有 {len(missing)} 处黄色【待填】：' + '、'.join(sorted(missing)))
    st.download_button('下载 Word', buf.getvalue(), file_name=os.path.basename(out),
                       mime='application/vnd.openxmlformats-officedocument.wordprocessingml.document')
