# -*- coding: utf-8 -*-
"""页面：条款维护。按章浏览或查找条款 / 附件，修改文字，保存前对比与检查，保存时自动备份、记修订记录、试生成。"""
import streamlit as st

from contract_compose import maintenance as mt
from contract_compose.library import load_library, load_type, list_types

ss = st.session_state
TYPES = list_types()
TYPE_NAMES = {t: load_type(t)['名称'] for t in TYPES}


def flash(kind, text):
    ss['ed::msg'] = (kind, text)


def bkey(ctype, kind, aid):
    return f'ed::body::{ctype}::{kind}::{aid}'


def nkey(ctype, kind, aid):
    return f'ed::name::{ctype}::{kind}::{aid}'


def reset(ctype, kind, aid):
    for k in (bkey(ctype, kind, aid), nkey(ctype, kind, aid), f'ed::reason::{ctype}::{kind}::{aid}'):
        ss.pop(k, None)


# ---------------- 回调：保存 / 撤销 / 恢复 ----------------
def do_save(ctype, kind, aid):
    lib = load_library(ctype)
    res = mt.save(lib, kind, aid, ss.get(bkey(ctype, kind, aid), ''), name=ss.get(nkey(ctype, kind, aid), '').strip() or None,
                  reason=ss.get(f'ed::reason::{ctype}::{kind}::{aid}', ''))
    if res['ok']:
        reset(ctype, kind, aid)
        snap = f"（回归快照已更新：{len(res['snapshots'])} 个）" if res.get('snapshots') else ''
        flash('success', f'已保存，旧版本已备份，修改已记入 library/{ctype}/修订记录.md{snap}')
    else:
        flash('error', res['message'])


def do_restore(ctype, kind, aid, path):
    res = mt.restore(load_library(ctype), kind, aid, path)
    if res['ok']:
        reset(ctype, kind, aid); flash('success', '已恢复到所选版本（恢复前的版本也已备份）')
    else:
        flash('error', res['message'])


# ---------------- 页面 ----------------
st.header('条款维护')
st.caption('选择条款或附件，直接修改文字。保存前会显示修改对比并检查变量、引用；保存时自动备份旧版本、记入修订记录，'
           '并用示例合同试生成一遍，出错会自动还原。')

if 'ed::msg' in ss:
    k, t = ss.pop('ed::msg'); getattr(st, k)(t)

c1, c2, c3 = st.columns([1.2, 1, 3])
ctype = c1.selectbox('合同类型', TYPES, key='ed::ctype', format_func=lambda t: TYPE_NAMES.get(t, t))
kind = c2.radio('内容', list(mt.KINDS), horizontal=True, key='ed::kind')
kw = c3.text_input('查找', key='ed::kw', placeholder='编号、名称或正文中的文字，如：质保期、3.4、HSE')

lib = load_library(ctype)
rows = mt.items(lib, kind)
by_id = {r['id']: r for r in rows}
left, right = st.columns([1, 2.3], gap='large')

with left:
    if kw.strip():
        shown = mt.search(rows, kw)
        st.caption(f'找到 {len(shown)} 处')
    elif kind == '条款':
        chs = mt.chapters(rows)
        labels = [f'{no}　{name}' if no != mt.UNUSED else name for no, name, _ in chs]
        ci = st.selectbox('章', range(len(chs)), format_func=lambda i: labels[i], key=f'ed::ch::{ctype}')
        shown = chs[ci][2]
    else:
        shown = rows
    if not shown:
        st.info('没有找到。'); st.stop()
    ids = [r['id'] for r in shown]
    sk = f'ed::sel::{ctype}::{kind}'
    if ss.get(sk) not in ids:
        ss[sk] = ids[0]
    lab = lambda i: f"{by_id[i]['no']}　{by_id[i]['name']}" + ('　（PDF）' if kind == '附件' and by_id[i]['level'] == '文件' else '')
    aid = st.radio('条款', ids, key=sk, format_func=lab, label_visibility='collapsed')

with right:
    r = by_id[aid]
    st.subheader(f"{r['no']}　{r['name']}")
    st.caption(f"ID：{aid}　·　文件：library/{ctype}/{mt.KINDS[kind]}/{r['file']}")
    bk, nk, rk = bkey(ctype, kind, aid), nkey(ctype, kind, aid), f'ed::reason::{ctype}::{kind}::{aid}'
    if bk not in ss: ss[bk] = r['body']
    if nk not in ss: ss[nk] = r['name']
    t_edit, t_view, t_hist = st.tabs(['修改', '预览', '历史版本'])

    with t_edit:
        if kind == '附件' and r['level'] == '文件':
            st.info('这是 PDF 类附件：合同中只在附件清单表里打钩，没有正文。可以修改名称。')
        st.text_input('名称（列表、修订记录中显示；附件名称会出现在目录和清单表中）', key=nk)
        if not (kind == '附件' and r['level'] == '文件'):
            st.text_area('正文', key=bk, height=380, help='行首标记决定 Word 样式，{{…}} 为变量 / 引用，见下方“写法说明”')
        with st.expander('写法说明'):
            st.markdown(
                '- 行首：`# ` 章标题，`## ` 条款，`### ` 子条款，`- ` 列项 a)，`  - ` 二级列项 1)，`+ ` 数字列项，'
                '两个空格开头为续行（如中文译文），`<居中> ` 居中，`<分页>` 单独一行分页\n'
                '- `{{变量}}` 值变量（须已在变量字典中），`{{选项:名称}}` 选项写法，`{{ref:条款ID}}` 引用条款编号，'
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

    with t_hist:
        hist = mt.history(lib, kind, aid)
        if not hist:
            st.info('还没有历史版本。每次在本页保存时，修改前的版本会自动备份到这里。')
        else:
            hi = st.selectbox('选择版本（保存前的备份）', range(len(hist)), format_func=lambda i: hist[i][0], key=f'ed::hist::{ctype}::{kind}::{aid}')
            old_name, old_body = mt.read_backup(hist[hi][1])
            st.markdown('**与当前版本的差异**（红色为当前版本中已删除的，绿色为当前版本新增的）')
            with st.container(border=True):
                d = mt.diff_html(old_body, r['body'])
                if old_name and old_name != r['name']:
                    d = f'<p>名称：{old_name} → {r["name"]}</p>' + d
                st.markdown(d or '（与当前版本相同）', unsafe_allow_html=True)
            st.button('恢复此版本', on_click=do_restore, args=(ctype, kind, aid, hist[hi][1]))
