# -*- coding: utf-8 -*-
"""全局常量（不随合同类型变化；类型相关的设置在 library/<类型>/type.yaml）。"""

MISS_L, MISS_R = '\u0001', '\u0002'            # 未填变量标记（内部使用，写入 Word 时换成黄色【待填：…】）
LABEL_MISSING = '待填'                          # 未填变量的标签
LABEL_ANNOTATE = '变量'                         # 变量标注版中的标签
NA_MARK = '（不适用 Not Applicable）'           # 不适用条款标题后缀
YES = ('是', '有', 'true', 'True', True, '1', 1)
