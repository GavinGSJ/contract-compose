# -*- coding: utf-8 -*-
"""页面：条款维护。

条款 / 附件：按章浏览或查找 → 修改文字（保存前对比与检查）、预览、调整结构（新增 / 移除 / 移动）、把文字改成变量、历史版本。
变量：查看变量用在哪里，修改默认值与说明。
所有保存都会自动备份、记入修订记录，并用示例合同试生成，出错自动还原。
"""
import streamlit as st

from contract_compose import maintenance as mt, structure as sc, variable_admin as va
from contract_compose.library import load_library, load_type, list_types

ss = st.session_state
TYPES = list_types()
TYPE_NAMES = {t: load_type(t)['名称'] for t in TYPES}
MODES = ['条款', '附件', '变量']


def flash(kind, text):
    ss['ed::msg'] = (kind, text)


def k(*parts):
    return 'ed::' + '::'.join(parts)


def reset(ctype, kind, aid):
    for x in ('body', 'name', 'reason'):
        ss.pop(k(x, ctype, kind, aid), None)


def finish(res, ctype, kind, goto=None, success=None):
    """操作结果：成功则提示并跳到 goto（条款 / 附件 ID）"""
    if res['ok']:
        snap = f"（回归快照已更新 {len(res['snapshots'])} 个）" if res.get('snapshots') else ''
        flash('success', (success or res['message']) + f'；已记入 library/{ctype}/修订记录.md' + snap)
        if goto:
            ss['ed::goto'] = (ctype, kind, goto)
    else:
        flash('error', res['message'])


def reason(ctype, kind, aid):
    return ss.get(k('sreason', ctype, kind, aid), '')


# ---------------- 回调 ----------------
def do_save(ctype, kind, aid):
    res = mt.save(load_library(ctype), kind, aid, ss.get(k('body', ctype, kind, aid), ''),
                  name=ss.get(k('name', ctype, kind, aid), '').strip() or None, reason=ss.get(k('reason', ctype, kind, aid), ''))
    if res['ok']: reset(ctype, kind, aid)
    finish(res, ctype, kind, success='已保存，旧版本已备份')


def do_restore(ctype, kind, aid, path):
    res = mt.restore(load_library(ctype), kind, aid, path)
    if res['ok']: reset(ctype, kind, aid)
    finish(res, ctype, kind, success='已恢复到所选版本（恢复前的版本也已备份）')


def do_move(ctype, kind, aid, direction):
    lib = load_library(ctype)
    fn = sc.move_annex if kind == '附件' else sc.move_atom
    finish(fn(lib, aid, direction, reason(ctype, kind, aid)), ctype, kind, aid)


def do_move_after(ctype, aid):
    target = ss.get(k('target', ctype, aid))
    finish(sc.move_atom_after(load_library(ctype), aid, target, reason(ctype, '条款', aid)), ctype, '条款', aid)


def do_insert(ctype, aid):
    lv = ss.get(k('newlv', ctype, aid), '条款')
    res = sc.insert_atom(load_library(ctype), aid, lv, ss.get(k('newname', ctype, aid), ''), ss.get(k('newbody', ctype, aid), ''),
                         code=ss.get(k('newcode', ctype, aid), ''), reason=reason(ctype, '条款', aid))
    if res['ok']:
        for x in ('newname', 'newbody', 'newcode'): ss.pop(k(x, ctype, aid), None)
    finish(res, ctype, '条款', res.get('id'))


def do_remove(ctype, kind, aid):
    if not ss.get(k('confirm', ctype, kind, aid)):
        return flash('warning', '请先勾选“确认移除”。')
    fn = sc.remove_annex if kind == '附件' else sc.remove_atom
    finish(fn(load_library(ctype), aid, reason(ctype, kind, aid)), ctype, kind)


def do_readd(ctype, kind, aid):
    after = ss.get(k('readd', ctype, kind, aid))
    lib = load_library(ctype)
    res = sc.readd_annex(lib, aid, after, reason(ctype, kind, aid)) if kind == '附件' else sc.readd_atom(lib, aid, after, reason(ctype, kind, aid))
    finish(res, ctype, kind, aid if kind == '条款' else None, success='已放回合同')


def do_default(ctype, aid):
    on = ss.get(k('default', ctype, aid)) == '有'
    finish(sc.set_annex_default(load_library(ctype), aid, on, reason(ctype, '附件', aid)), ctype, '附件', aid)


def do_add_annex(ctype, aid):
    res = sc.add_annex(load_library(ctype), aid, ss.get(k('axname', ctype), ''), ss.get(k('axname_en', ctype), ''),
                       typ=ss.get(k('axtype', ctype), '正文'), default=ss.get(k('axdefault', ctype), '有'),
                       body=ss.get(k('axbody', ctype), ''), reason=reason(ctype, '附件', aid))
    if res['ok']:
        for x in ('axname', 'axname_en', 'axbody'): ss.pop(k(x, ctype), None)
    finish(res, ctype, '附件', res.get('id'))


def do_make_var(ctype, kind, aid):
    g = lambda x: ss.get(k(x, ctype, kind, aid), '')
    res = va.make_variable(load_library(ctype), kind, aid, g('mvtext'), g('mvname'), default=g('mvdefault'),
                           desc=g('mvdesc'), scope='common' if g('mvscope') == '共用（各合同类型都可用）' else 'type',
                           replace_all=bool(ss.get(k('mvall', ctype, kind, aid), True)), reason=g('mvreason'))
    if res['ok']:
        reset(ctype, kind, aid)
        for x in ('mvtext', 'mvname', 'mvdefault', 'mvdesc', 'mvreason'): ss.pop(k(x, ctype, kind, aid), None)
    finish(res, ctype, kind)


def do_set_default(ctype, var):
    g = lambda x: ss.get(k(x, ctype, var), '')
    scope = 'type' if g('vscope').startswith('只改') else 'auto'
    res = va.set_default(load_library(ctype), var, g('vdefault'), desc=g('vdesc'), scope=scope, reason=g('vreason'))
    if res['ok']:
        for x in ('vdefault', 'vdesc', 'vreason'): ss.pop(k(x, ctype, var), None)
    finish(res, ctype, '变量')


# ---------------- 页面 ----------------
st.header('条款维护')
st.caption('修改条款和附件的文字、调整顺序、新增或移除条款、管理变量。每次保存都会自动备份旧版本、记入修订记录，'
           '并用示例合同试生成一遍，出错会自动还原。')
if 'ed::msg' in ss:
    t, m = ss.pop('ed::msg'); getattr(st, t)(m)

goto = ss.pop('ed::goto', None)                       # 操作后跳到相关条款（须在控件创建前设置）
if goto:
    gct, gkind, gid = goto
    grows = mt.items(load_library(gct), gkind)
    if gid in [x['id'] for x in grows]:
        ss['ed::ctype'], ss['ed::kind'], ss['ed::kw'] = gct, gkind, ''
        if gkind == '条款':
            ss[k('ch', gct)] = next(i for i, c in enumerate(mt.chapters(grows)) if gid in [x['id'] for x in c[2]])
        ss[k('sel', gct, gkind)] = gid

c1, c2, c3 = st.columns([1.2, 1.3, 3])
ctype = c1.selectbox('合同类型', TYPES, key='ed::ctype', format_func=lambda t: TYPE_NAMES.get(t, t))
kind = c2.radio('内容', MODES, horizontal=True, key='ed::kind')
kw = c3.text_input('查找', key='ed::kw', placeholder='编号、名称或正文中的文字，如：质保期、3.4、HSE' if kind != '变量' else '变量名、说明或用到它的条款')
lib = load_library(ctype)

# ======================= 变量 =======================
if kind == '变量':
    vrows = va.rows(lib)
    q = kw.strip().lower()
    shown = [r for r in vrows if not q or q in r['name'].lower() or q in str(r['说明']).lower() or any(q in u.lower() for u in r['用在'])]
    left, right = st.columns([1, 2.3], gap='large')
    with left:
        st.caption(f'共 {len(shown)} 个变量')
        if not shown:
            st.stop()
        names = [r['name'] for r in shown]
        sk = k('vsel', ctype)
        if ss.get(sk) not in names: ss[sk] = names[0]
        var = st.radio('变量', names, key=sk, label_visibility='collapsed',
                       format_func=lambda n: n + ('　（未使用）' if not next(r for r in vrows if r['name'] == n)['用在'] else ''))
    with right:
        r = next(x for x in vrows if x['name'] == var)
        st.subheader(var)
        st.caption(f"类别：{r['类别'] or '—'}　·　类型：{r['类型'] or '—'}　·　定义在：{r['定义在'] or '—'}"
                   + ('　·　有英文变量 ' + var + '_en' if r['英文'] else ''))
        st.markdown('**用在**：' + ('、'.join(r['用在']) if r['用在'] else '没有条款用到这个变量'))
        if r['类型'] == '选项':
            st.info('这是选项变量（多种写法），写法在选项库中维护；这里只能改默认选用的写法 ID。')
        dk, ck = k('vdefault', ctype, var), k('vdesc', ctype, var)
        if dk not in ss: ss[dk] = '' if r['默认值'] is None else str(r['默认值'])
        if ck not in ss: ss[ck] = str(r['说明'] or '')
        st.text_input('默认值（合同中没有填写时使用）', key=dk)
        st.text_input('说明（表单中的提示）', key=ck)
        if r['定义在'] == '共用':
            st.radio('修改范围', ['只改本类型（' + TYPE_NAMES[ctype] + '）', '修改共用定义（所有合同类型都变）'], key=k('vscope', ctype, var))
        changed = ss[dk] != ('' if r['默认值'] is None else str(r['默认值'])) or ss[ck] != str(r['说明'] or '')
        if changed:
            st.text_input('修改原因（写入修订记录）', key=k('vreason', ctype, var))
            st.button('保存', type='primary', on_click=do_set_default, args=(ctype, var))
        else:
            st.caption('尚未修改。新增变量：在“条款”的“改成变量”中把条款里的文字直接改成变量。')
    st.stop()

# ======================= 条款 / 附件 =======================
rows = mt.items(lib, kind)
by_id = {r['id']: r for r in rows}
unused_ax = sc.unused_annexes(lib) if kind == '附件' else []

left, right = st.columns([1, 2.3], gap='large')
with left:
    if kw.strip():
        shown = mt.search(rows, kw)
        st.caption(f'找到 {len(shown)} 处')
    elif kind == '条款':
        chs = mt.chapters(rows)
        labels = [f'{no}　{name}' if no != mt.UNUSED else name for no, name, _ in chs]
        if ss.get(k('ch', ctype), 0) >= len(chs): ss[k('ch', ctype)] = 0
        ci = st.selectbox('章', range(len(chs)), format_func=lambda i: labels[i], key=k('ch', ctype))
        shown = chs[ci][2]
    else:
        shown = rows
    if not shown:
        st.info('没有找到。'); st.stop()
    ids = [r['id'] for r in shown]
    sk = k('sel', ctype, kind)
    if ss.get(sk) not in ids: ss[sk] = ids[0]
    lab = lambda i: f"{by_id[i]['no']}　{by_id[i]['name']}" + ('　（PDF）' if kind == '附件' and by_id[i]['level'] == '文件' else '')
    aid = st.radio('条款', ids, key=sk, format_func=lab, label_visibility='collapsed')
    if unused_ax:
        st.caption('未使用的附件：' + '、'.join(unused_ax) + '（在“结构”中放回）')

with right:
    r = by_id[aid]
    unused = r['no'] == mt.UNUSED
    is_pdf = kind == '附件' and r['level'] == '文件'
    st.subheader(f"{r['no']}　{r['name']}")
    st.caption(f"ID：{aid}　·　文件：library/{ctype}/{mt.KINDS[kind]}/{r['file']}")
    bk, nk, rk = k('body', ctype, kind, aid), k('name', ctype, kind, aid), k('reason', ctype, kind, aid)
    if bk not in ss: ss[bk] = r['body']
    if nk not in ss: ss[nk] = r['name']
    t_edit, t_view, t_struct, t_var, t_hist = st.tabs(['修改', '预览', '结构', '改成变量', '历史版本'])

    with t_edit:
        if is_pdf:
            st.info('这是 PDF 类附件：合同中只在附件清单表里打钩，没有正文。可以修改名称。')
        if unused:
            st.warning('这条条款目前不在合同中（已移除）。可在“结构”中放回。')
        st.text_input('名称（列表、修订记录中显示；附件名称会出现在目录和清单表中）', key=nk)
        if not is_pdf:
            st.text_area('正文', key=bk, height=380, help='行首标记决定 Word 样式，{{…}} 为变量 / 引用，见下方“写法说明”')
        with st.expander('写法说明'):
            st.markdown(
                '- 行首：`# ` 章标题，`## ` 条款，`### ` 子条款，`- ` 列项 a)，`  - ` 二级列项 1)，`+ ` 数字列项，'
                '两个空格开头为续行（如中文译文），`<居中> ` 居中，`<分页>` 单独一行分页\n'
                '- `{{变量}}` 值变量（须已在变量字典中，新变量用“改成变量”），`{{选项:名称}}` 选项写法，`{{ref:条款ID}}` 引用条款编号，'
                '`{{附件:附件ID}}` 引用附件编号（附件五），`{{附件_en:附件ID}}`（Annex 5）\n'
                '- `**加粗**`、`<u>下划线</u>`；空行只用于分段，不会在合同中留空行')
        new_body, new_name = ss.get(bk, r['body']), ss.get(nk, r['name']).strip()
        changed = new_body.replace('\r\n', '\n').strip('\n') != r['body'].strip('\n') or new_name != r['name']
        if not changed:
            st.caption('尚未修改。')
        else:
            errors, warns = mt.check(lib, kind, aid, new_body)
            st.markdown('**修改对比**（红色删除线为删除，绿色为新增）')
            with st.container(border=True):
                d = mt.diff_html(r['body'], new_body)
                if new_name != r['name']:
                    d = f'<p>名称：<del style="background:#fde2e2">{r["name"]}</del> → <ins style="background:#dcfce7;text-decoration:none">{new_name}</ins></p>' + d
                st.markdown(d or '（只有空行变化）', unsafe_allow_html=True)
            for e in errors: st.error(e)
            for w in warns: st.warning(w)
            st.text_input('修改原因（写入修订记录）', key=rk, placeholder='如：按 2026 年新版模板，质保期改为 24 个月')
            b1, b2, _ = st.columns([1, 1, 3])
            b1.button('保存', type='primary', disabled=bool(errors), on_click=do_save, args=(ctype, kind, aid))
            b2.button('放弃修改', on_click=reset, args=(ctype, kind, aid))

    with t_view:
        st.caption('按变量默认值预览（版式近似 Word）：蓝底为变量的值，黄底为需要填写的变量。显示的是“修改”页中当前的文字。')
        with st.container(border=True):
            try:
                st.markdown(mt.preview_html(lib, kind, aid, ss.get(bk, r['body'])) or '（无正文）', unsafe_allow_html=True)
            except SystemExit as e:
                st.error(f'无法预览：{e}')

    with t_struct:
        st.text_input('操作原因（写入修订记录）', key=k('sreason', ctype, kind, aid))
        if kind == '条款':
            order = sc.current_order(lib)
            olab = lambda a: f"{by_id[a]['no']}　{by_id[a]['name']}"
            if unused:
                st.markdown('**放回合同**')
                st.selectbox('放在哪一条之后', order, format_func=olab, key=k('readd', ctype, kind, aid))
                st.button('放回合同', type='primary', on_click=do_readd, args=(ctype, kind, aid))
            else:
                st.markdown('**移动**（连同下面的子条款；编号和引用自动更新）')
                m1, m2, _ = st.columns([1, 1, 3])
                m1.button('⬆ 上移', on_click=do_move, args=(ctype, kind, aid, 'up'))
                m2.button('⬇ 下移', on_click=do_move, args=(ctype, kind, aid, 'down'))
                t1, t2 = st.columns([3, 1])
                t1.selectbox('移到某一条之后（可跨章）', [a for a in order if a != aid], format_func=olab, key=k('target', ctype, aid))
                t2.write(''); t2.button('移动', on_click=do_move_after, args=(ctype, aid))
                st.divider()
                st.markdown(f'**在 {r["no"]} 之后新增**')
                lvs = ['条款', '子条款', '章'] if r['level'] != '章' else ['条款', '章']
                n1, n2 = st.columns([1, 2])
                lv = n1.radio('层级', lvs, key=k('newlv', ctype, aid), horizontal=True)
                n2.text_input('名称', key=k('newname', ctype, aid), placeholder='如：质保延期')
                if lv == '章':
                    st.text_input('章代码（2–4 个大写字母，用于条款 ID，如 WAR）', key=k('newcode', ctype, aid))
                st.text_area('正文（可留空，新增后再在“修改”中写）', key=k('newbody', ctype, aid), height=140,
                             placeholder=f"{sc.MARK[lv]}名称 English Title\n\n正文……")
                st.button('新增', type='primary', on_click=do_insert, args=(ctype, aid))
                st.divider()
                st.markdown('**从合同中移除**（文件保留，可随时放回；被其他条款引用时不能移除）')
                st.checkbox('确认移除', key=k('confirm', ctype, kind, aid))
                st.button('移除', on_click=do_remove, args=(ctype, kind, aid))
        else:
            meta = lib.annexes[aid]['meta']
            st.markdown('**附件顺序**（编号、目录、清单表和引用自动更新）')
            m1, m2, _ = st.columns([1, 1, 3])
            m1.button('⬆ 上移', on_click=do_move, args=(ctype, kind, aid, 'up'))
            m2.button('⬇ 下移', on_click=do_move, args=(ctype, kind, aid, 'down'))
            st.divider()
            if meta.get('跟随变量'):
                st.caption(f"默认有无：随“{meta['跟随变量']}”自动决定")
            else:
                dk = k('default', ctype, aid)
                cur = '无' if str(meta.get('默认', '有')) == '无' else '有'
                d1, d2 = st.columns([2, 1])
                d1.radio('默认有无（新合同中是否默认勾选）', ['有', '无'], index=['有', '无'].index(cur), key=dk, horizontal=True)
                d2.write(''); d2.button('保存默认', on_click=do_default, args=(ctype, aid), disabled=ss.get(dk, cur) == cur)
            st.divider()
            st.markdown(f'**在 {r["no"]} 之后新增附件**')
            a1, a2 = st.columns(2)
            a1.text_input('中文名称', key=k('axname', ctype))
            a2.text_input('英文名称', key=k('axname_en', ctype))
            a3, a4 = st.columns(2)
            a3.radio('类型', ['正文', '文件'], key=k('axtype', ctype), horizontal=True, help='文件：PDF 等单独的文件，只在清单表打钩')
            a4.radio('默认', ['有', '无'], key=k('axdefault', ctype), horizontal=True)
            if ss.get(k('axtype', ctype), '正文') == '正文':
                st.text_area('正文（可留空，新增后再写）', key=k('axbody', ctype), height=120)
            st.button('新增附件', type='primary', on_click=do_add_annex, args=(ctype, aid))
            st.divider()
            st.markdown('**从合同中移除**（文件保留；后面的附件编号自动前移；被条款引用时不能移除）')
            st.checkbox('确认移除', key=k('confirm', ctype, kind, aid))
            st.button('移除', on_click=do_remove, args=(ctype, kind, aid))
            for ua in unused_ax:
                st.divider()
                st.markdown(f'**放回未使用的附件 {ua}**')
                st.selectbox('放在哪个附件之后', list(lib.annexes), format_func=lambda a: f"{by_id[a]['no']} {by_id[a]['name']}",
                             key=k('readd', ctype, kind, ua))
                st.button('放回', key=k('readdbtn', ctype, ua), on_click=do_readd, args=(ctype, kind, ua))

    with t_var:
        if is_pdf:
            st.info('PDF 类附件没有正文。')
        else:
            st.caption('把正文中的一段文字（如“12个月”中的“12”）改成变量：新变量的默认值就是原文字，合同内容不变；'
                       '以后在表单中按合同填写，或在“变量”中改默认值。')
            g = lambda x: k(x, ctype, kind, aid)
            st.text_input('要改成变量的文字（从“修改”页复制，须与正文完全一致）', key=g('mvtext'))
            txt = ss.get(g('mvtext'), '')
            if txt:
                cnt = r['body'].count(txt)
                (st.caption if cnt else st.error)(f'正文中出现 {cnt} 处' if cnt else '正文中找不到这段文字')
            v1, v2 = st.columns(2)
            v1.text_input('变量名', key=g('mvname'), placeholder='如：质保月数')
            name = ss.get(g('mvname'), '').strip()
            exists = name in lib.V
            if name:
                v1.caption('将使用已有变量（默认值：' + str(lib.V[name].get('默认值', '')) + '）' if exists else '将新建变量')
            if not exists:
                if g('mvdefault') not in ss or ss.get(g('_mvlast')) != txt:
                    ss[g('mvdefault')] = txt; ss[g('_mvlast')] = txt
                v2.text_input('默认值（默认为原文字）', key=g('mvdefault'))
                st.text_input('说明（表单中的提示）', key=g('mvdesc'))
                st.radio('新变量放在', ['本类型专属', '共用（各合同类型都可用）'], key=g('mvscope'), horizontal=True)
            st.checkbox('替换全部出现的位置', value=True, key=g('mvall'))
            st.text_input('修改原因（写入修订记录）', key=g('mvreason'))
            st.button('改成变量', type='primary', on_click=do_make_var, args=(ctype, kind, aid), disabled=not (txt and name))

    with t_hist:
        hist = mt.history(lib, kind, aid)
        if not hist:
            st.info('还没有历史版本。每次在本页保存时，修改前的版本会自动备份到这里。')
        else:
            hi = st.selectbox('选择版本（保存前的备份）', range(len(hist)), format_func=lambda i: hist[i][0], key=k('hist', ctype, kind, aid))
            old_name, old_body = mt.read_backup(hist[hi][1])
            st.markdown('**与当前版本的差异**（红色为当前版本中已删除的，绿色为当前版本新增的）')
            with st.container(border=True):
                d = mt.diff_html(old_body, r['body'])
                if old_name and old_name != r['name']:
                    d = f'<p>名称：{old_name} → {r["name"]}</p>' + d
                st.markdown(d or '（与当前版本相同）', unsafe_allow_html=True)
            st.button('恢复此版本', on_click=do_restore, args=(ctype, kind, aid, hist[hi][1]))
