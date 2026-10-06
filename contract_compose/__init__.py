# -*- coding: utf-8 -*-
"""合同生成引擎：按 配方 + 原子 + 变量 + 选项 组装 Word 合同。

常用入口：
    from contract_compose import build, load_library
    doc, used, missing, order, na = build(cfg)
命令行：python -m contract_compose（见 cli.py）
"""
from .library import Library, load_library, list_types, load_type
from .assembler import build, numbering

__all__ = ["Library", "load_library", "list_types", "load_type", "build", "numbering"]
