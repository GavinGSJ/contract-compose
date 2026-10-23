# -*- coding: utf-8 -*-
"""PO：LOA 前言、附件库（字母编号、B 技术协议 / C 价格明细）、项目预设（项目信息、附加附件）。"""
import os, re
import yaml
import pytest

from contract_compose import paths, build, load_library
from contract_compose.snapshots import dump
from contract_compose import annexes

CASE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'cases', 'F520-PO-EXAMPLE-001_离心泵.yaml')


def cfg_with(drop=(), **over):
    cfg = yaml.safe_load(open(CASE, encoding='utf-8'))
    for k in drop:
        cfg['变量'].pop(k, None)
    for k, v in over.items():
        cfg[k] = {**cfg.get(k, {}), **v} if isinstance(v, dict) and isinstance(cfg.get(k), dict) else v
    return cfg


def lines(cfg):
    return dump(build(cfg)).split('\n')


def find(ls, text):
    return [l for l in ls if text in l]


PROJECT_VARS = ('项目名称', '项目中文名', '业主名称', '业主中文名', '设施简称', '设施全称', '设施全称_en')


def test_annex_letters_and_order():
    lib = load_library('PO')
    ids = list(lib.annexes)
    assert ids[:3] == ['ANX-PSR', 'ANX-TA', 'ANX-PRICE'] and len(ids) == 12
    assert [annexes.label(lib, a, True) for a in ids[:3]] == ['ATTACHMENT A', 'ATTACHMENT B', 'ATTACHMENT C']
    assert annexes.label(lib, 'ANX-RETURN') == '附件L' and annexes.no_text(lib, 13) == 'M'


def test_toc_and_preface_follow_annex_order():
    ls = lines(cfg_with(drop=PROJECT_VARS))
    assert find(ls, 'ATTACHMENT B: TECHNICAL AGREEMENT') and find(ls, '附件B：技术协议')
    assert find(ls, 'ATTACHMENT C: DETAILED PRICE LIST AND PROVISIONAL RATES') and find(ls, '附件C：价格明细及可选项价格')
    assert not find(ls, 'ATTACHMENT M')                                          # F520 只到附件 L，没有“M NOT USED”
    assert find(ls, 'ATTACHMENT B TECHNICAL AGREEMENT附件B技术协议') and find(ls, 'ATTACHMENT C to L (unless otherwise mentioned) 附件C至L（除非另有说明）')
    # 条款中的附件引用：价格明细 = C，技术协议 = B
    assert find(ls, 'Refer to ATTACHMENT C for detailed price breakdown') and find(ls, '详细价格请见附件C，')
    assert find(ls, 'under ATTACHMENT B.') and find(ls, 'the signed ATTACHMENT B: TECHNICAL AGREEMENT')
    assert find(ls, 'signed NDA (ATTACHMENT I)') and find(ls, 'ATTACHMENT G (COMPLIANCE')
    assert find(ls, 'The specimen is as per ATTACHMENT J') or find(ls, 'as per ATTACHMENT J')       # 付款条款中的引用也已替换
    assert not find(ls, '{{附件')


def test_loa_paragraphs():
    ls = lines(cfg_with(变量={'LOA编号': 'LOA-9', 'LOA日期': '2026年8月1日', 'LOA日期_en': '1 August 2026'}))
    assert find(ls, 'Procurement Package is evidenced by the written Letter of Award (No. LOA-9) executed by')
    assert find(ls, 'on 1 August 2026. Following further negotiations between the Parties')
    assert find(ls, '本采购包已于2026年8月1日由') and find(ls, '中标通知书（编号为LOA-9）')


@pytest.mark.parametrize('pid,extra', [
    ('F484', ['职业健康，安全和环境保护要求', '网络安全要求']),
    ('f502', ['物资运输、包装和标识管理规程']),                                   # 不区分大小写
    ('F520', []),
    ('F999', []),                                                               # 预存库中没有的项目：只有 A–L
])
def test_project_extra_annexes(pid, extra):
    ls = lines(cfg_with(drop=PROJECT_VARS, 变量={'项目编号': pid}))
    toc = [(m.group(1), m.group(2)) for l in ls for m in [re.search(r'^(?:\[[^\]]*\] )?附件([A-Z])：(.+)$', l)] if m]
    assert [n for letter, n in toc if letter > 'L'] == extra
    last = chr(ord('L') + len(extra))
    assert find(ls, f'ATTACHMENT C to {last} (unless otherwise mentioned) 附件C至{last}（除非另有说明）')


def test_f484_annex_texts():
    ls = lines(cfg_with(drop=PROJECT_VARS, 变量={'项目编号': 'F484'}))
    assert find(ls, 'ATTACHMENT M: HEALTH, SAFETY AND ENVIRONMENT REQUIREMENTS') and find(ls, '附件N：网络安全要求')
    f502 = lines(cfg_with(drop=PROJECT_VARS, 变量={'项目编号': 'F502'}))
    assert find(f502, 'ATTACHMENT M: Instruction on Management of Material Transport, Package and Marking')


def test_custom_annex_after_project_annexes_and_na_mark():
    ls = lines(cfg_with(drop=PROJECT_VARS, 变量={'项目编号': 'F502', '有技术协议': '否'}, 自定义附件=[{'名称': '补充说明', '名称_en': 'Notes'}]))
    assert find(ls, '附件M：物资运输、包装和标识管理规程') and find(ls, '附件N：补充说明') and find(ls, 'ATTACHMENT N: Notes')
    assert find(ls, '附件B：技术协议（不适用 Not Applicable）')                      # 没有技术协议：目录中标注不适用，编号不变


def test_project_info_filled_from_preset_and_explicit_wins():
    ls = lines(cfg_with(drop=PROJECT_VARS, 变量={'项目编号': 'F484'}))
    assert find(ls, 'OWNER means Eni or its permitted successor') and find(ls, '业主是指埃尼或其许可')
    assert find(ls, 'PROJECT means BALEINE III FPSO PROJECT.') and find(ls, '项目：BALEINE 三期 FPSO 项目')
    assert find(ls, 'FPSO是指买方为本项目向业主提供的浮式生产储卸油装置') or find(ls, 'FPSO 是指买方为本项目向业主提供的浮式生产储卸油装置')
    ls = lines(cfg_with(drop=PROJECT_VARS, 变量={'项目编号': 'F484', '业主名称': 'Other Owner', '业主中文名': '另一业主'}))
    assert find(ls, 'OWNER means Other Owner or') and find(ls, '业主是指另一业主或其许可')


def test_chinese_name_falls_back_to_english():
    """项目中文名、业主中文名没填时，中文条款用英文名"""
    cfg = cfg_with(drop=PROJECT_VARS, 变量={'项目编号': 'F999', '项目名称': 'Alpha Project', '业主名称': 'Alpha Owner'})
    ls = lines(cfg)
    assert find(ls, '项目：Alpha Project') and find(ls, '业主是指Alpha Owner或其许可')
