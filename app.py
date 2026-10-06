# -*- coding: utf-8 -*-
"""合同生成工具入口。双击“启动表单.bat”，或运行：python -m streamlit run app.py"""
import os, sys
import streamlit as st

from ui.stale import stale, purge

# 表单运行期间更新了代码（如 git pull）时，进程里还留着旧的 contract_compose 模块，新旧混用会报错：
# 发现磁盘上的代码比已加载的新，就清掉旧模块，各页面重新导入
if stale(sys.modules.get('contract_compose'), os.path.join(os.path.dirname(os.path.abspath(__file__)), 'contract_compose')):
    purge()

st.set_page_config(page_title='合同生成', page_icon='📄', layout='wide')

# 切换页面时保留合同表单中已填写的内容（Streamlit 默认会清掉未显示页面的输入）
KEEP = ('v::', 'o::', 'c::', 'ax::', 'ed::')
for k in list(st.session_state.keys()):
    if k.startswith(KEEP) or k in ('ctype', 'entity', 'bond', 'na', 'ta', 'pay_nodes', 'pay_docs', 'cfg_file'):
        st.session_state[k] = st.session_state[k]

pg = st.navigation([
    st.Page('ui/contract_form.py', title='合同生成', icon='📄', url_path='contract', default=True),
    st.Page('ui/preset_manager.py', title='预存信息管理', icon='🗂️', url_path='presets'),
    st.Page('ui/clause_editor.py', title='条款维护', icon='✏️', url_path='clauses'),
])
pg.run()
