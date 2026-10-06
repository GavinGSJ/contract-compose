# -*- coding: utf-8 -*-
"""页面：预存信息管理（买方主体等）。每个预存库是 library/common/presets/ 下的一个 yaml 文件。"""
import os, re
import streamlit as st

from contract_compose import assembler as asm

NEW = '＋ 新增条目'
ss = st.session_state


def flash(kind, text):
    ss['pm::msg'] = (kind, text)


def label(d, f):
    return d['字段'].get(f) or f.split('.', 1)[-1]


def fields_of(d):
    """字段顺序：字段设置中列出的在前，条目中出现但未列出的在后"""
    out = list(d['字段'])
    for e in d['条目'].values():
        out += [k for k in e if k not in out]
    return out


def fkey(lib, entry, f):
    return f'pm::{lib}::{entry}::{f}'


# ---------------- 回调：保存 / 删除 / 设为默认 / 复制 ----------------
def save_entry(lib, old):
    d = asm.load_presets()[lib]
    name = str(ss.get(fkey(lib, old, '__name__'), '')).strip()
    if not name:
        return flash('error', '条目名称不能为空。')
    if name != old and name in d['条目']:
        return flash('error', f'已有名为“{name}”的条目，请换一个名称。')
    vals = {f: str(ss.get(fkey(lib, old, f), '')).strip() for f in fields_of(d)}
    items = list(d['条目'].items())
    if old == NEW:
        items.append((name, vals))
    else:
        items = [(name, vals) if n == old else (n, e) for n, e in items]
    d['条目'] = dict(items)
    asm.save_preset(d)
    if old == NEW:                                  # 清空“新增条目”表单
        for k in [k for k in ss.keys() if k.startswith(fkey(lib, NEW, ''))]:
            del ss[k]
    ss['pm::sel::' + lib] = name
    flash('success', f'已保存“{name}”。')


def delete_entry(lib, name):
    if not ss.get(f'pm::confirm::{lib}::{name}'):
        return flash('warning', '请先勾选“确认删除”。')
    d = asm.load_presets()[lib]
    d['条目'].pop(name, None)
    asm.save_preset(d)
    ss['pm::sel::' + lib] = next(iter(d['条目']), NEW)
    flash('success', f'已删除“{name}”（旧版本已存入 presets/backups）。')


def make_default(lib, name):
    d = asm.load_presets()[lib]
    d['条目'] = {name: d['条目'][name], **{n: e for n, e in d['条目'].items() if n != name}}
    asm.save_preset(d)
    flash('success', f'“{name}”已设为默认（排在第一位）。')


def copy_entry(lib, name):
    d = asm.load_presets()[lib]
    for f, v in d['条目'][name].items():
        ss[fkey(lib, NEW, f)] = '' if v is None else str(v)
    ss[fkey(lib, NEW, '__name__')] = name + '（副本）'
    ss['pm::sel::' + lib] = NEW
    flash('info', '已复制到“新增条目”，修改名称和内容后点“保存”。')


def add_field(lib):
    k = str(ss.get('pm::newfield::' + lib, '')).strip()
    lab = str(ss.get('pm::newlabel::' + lib, '')).strip()
    d = asm.load_presets()[lib]
    if not k:
        return flash('error', '请填写变量名。')
    if k in fields_of(d):
        return flash('error', f'字段“{k}”已存在。')
    d['字段'][k] = lab or k.split('.', 1)[-1]
    for e in d['条目'].values():
        e.setdefault(k, '')
    asm.save_preset(d)
    ss['pm::newfield::' + lib] = ''; ss['pm::newlabel::' + lib] = ''
    flash('success', f'已新增字段“{d["字段"][k]}”（{k}）。')


def save_labels(lib):
    d = asm.load_presets()[lib]
    for f in fields_of(d):
        v = str(ss.get(f'pm::label::{lib}::{f}', '')).strip()
        if v: d['字段'][f] = v
    asm.save_preset(d)
    flash('success', '字段显示名已保存。')


# ---------------- 页面 ----------------
st.header('预存信息管理')
st.caption('维护合同中反复使用的固定信息。修改保存后立即生效，生成合同时自动带出；每次保存前的旧版本自动存入 library/common/presets/backups。')

presets = asm.load_presets()
if not presets:
    st.info('library/common/presets/ 中还没有预存信息文件。'); st.stop()

if 'pm::msg' in ss:
    kind, text = ss.pop('pm::msg')
    getattr(st, kind)(text)

libs = list(presets)
lib = st.radio('预存库', libs, horizontal=True, key='pm::lib',
               format_func=lambda n: f"{n}（{len(presets[n]['条目'])}）")
d = presets[lib]
fields = fields_of(d)
if d.get('说明'):
    st.caption('用途：' + d['说明'])

# 总览
rows = [{(d.get('条目名称标签') or '条目名称').split('（')[0]: n, **{label(d, f): e.get(f, '') for f in fields}} for n, e in d['条目'].items()]
if rows:
    st.dataframe(rows, hide_index=True)
else:
    st.info('还没有条目，请在下方新增。')

st.subheader('编辑')
options = list(d['条目']) + [NEW]
sk = 'pm::sel::' + lib
if ss.get(sk) not in options:
    ss[sk] = options[0]
left, right = st.columns([1, 3])
with left:
    sel = st.radio('选择条目', options, key=sk,
                   format_func=lambda n: n + ('　（默认）' if options and n == options[0] and n != NEW else ''))

with right:
    entry = d['条目'].get(sel, {})
    nk = fkey(lib, sel, '__name__')
    if nk not in ss:
        ss[nk] = '' if sel == NEW else sel
    for f in fields:
        k = fkey(lib, sel, f)
        if k not in ss:
            ss[k] = '' if entry.get(f) is None else str(entry.get(f, ''))
    with st.form(f'pm::form::{lib}::{sel}', border=True):
        st.text_input(d.get('条目名称标签') or '条目名称（下拉选择时显示的名字）', key=nk)
        multi = set(d.get('多行字段') or [])
        cols = st.columns(2)
        short = [f for f in fields if f not in multi]
        for i, f in enumerate(short):
            cols[i % 2].text_input(label(d, f), key=fkey(lib, sel, f), help=f'对应合同变量 {{{{{f}}}}}')
        for f in fields:
            if f in multi:
                st.text_area(label(d, f), key=fkey(lib, sel, f), height=130)
        st.form_submit_button('保存', type='primary', on_click=save_entry, args=(lib, sel))

    if sel != NEW:
        b1, b2, b3 = st.columns(3)
        b1.button('设为默认', on_click=make_default, args=(lib, sel), disabled=(sel == options[0]))
        b2.button('复制为新条目', on_click=copy_entry, args=(lib, sel))
        with b3:
            st.checkbox('确认删除', key=f'pm::confirm::{lib}::{sel}')
            st.button('删除此条目', on_click=delete_entry, args=(lib, sel))

with st.expander('字段设置（新增字段、修改显示名）'):
    st.caption('字段的“变量名”就是合同原子中的 {{变量}}。新增字段后，需在条款原子中使用该变量才会出现在合同里。')
    cols = st.columns(3)
    for i, f in enumerate(fields):
        lk = f'pm::label::{lib}::{f}'
        if lk not in ss: ss[lk] = label(d, f)
        cols[i % 3].text_input(f, key=lk)
    st.button('保存显示名', on_click=save_labels, args=(lib,))
    st.divider()
    c1, c2, c3 = st.columns([2, 2, 1])
    c1.text_input('新字段变量名', key='pm::newfield::' + lib, placeholder='如 买方.联系人')
    c2.text_input('显示名', key='pm::newlabel::' + lib, placeholder='如 联系人')
    c3.write(''); c3.button('新增字段', on_click=add_field, args=(lib,))
