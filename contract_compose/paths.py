# -*- coding: utf-8 -*-
"""项目内所有目录与固定文件名，统一在这里定义。"""
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))   # 项目根目录
LIBRARY = os.path.join(ROOT, 'library')                              # 内容库
COMMON = os.path.join(LIBRARY, 'common')                             # 各类型共用的变量、选项、付款条款、预存库
PRESETS = os.path.join(COMMON, 'presets')                            # 预存库（买方主体、项目信息）
PRESET_BACKUPS = os.path.join(PRESETS, 'backups')                    # 预存库修改前的自动备份（不进 git）
CONFIGS = os.path.join(ROOT, 'configs')                              # 每份合同的配置
OUTPUT = os.path.join(ROOT, 'output')                                # 生成的合同与报告
NEW_TYPES = os.path.join(ROOT, 'new_types')                          # 新增合同类型的中间产物（体检报告等）

# 内容库中的固定名称（公共目录与各类型目录通用）
ATOMS = 'atoms'
ANNEXES = 'annexes'                                                  # 合同附件（一个附件一个 .md）
OPTIONS = 'options'
BLOCKS = 'blocks'
TABLES = 'tables'
VARIABLES = 'variables.yaml'
RECIPE = 'recipe.yaml'
TYPE_FILE = 'type.yaml'                                              # 合同类型设置；有此文件的目录即为一种合同类型
PAYMENT_TERMS = 'payment_terms.yaml'
ATOM_INDEX = '原子总览.md'


def type_dir(ctype):
    """合同类型目录：library/<类型>/"""
    return os.path.join(LIBRARY, ctype)
