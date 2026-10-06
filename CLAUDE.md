# CLAUDE.md

合同生成工具：按 配方 × 原子 × 样式模板 × 变量/选项 组装 Word 合同（FA 框架合同、PO 实采合同）。用户主要通过 AI 维护本项目，用户本人只“说要什么”和“拍板”。

## 必读
- 架构、代码模块、维护约定：`docs/架构.md`
- 原子标记、变量、付款、不适用等规则：`docs/使用手册.md`
- 新增合同类型（`type.yaml`）：`docs/新增合同类型.md`
- 待办与进度：`docs/路线图.md`

## 常用命令（项目根目录）
```
pip install -r requirements-dev.txt
python -m pytest tests                          # 每次改动后必跑
python tests/test_regression.py --update        # 仅在有意改变生成结果时更新快照
python -m contract_compose configs/<配置>.yaml   # 生成合同 → output/
python -m contract_compose --母本 FA|PO          # 默认值组装，与母本比对
python -m contract_compose --标注 FA|PO          # 变量标注版
python -m contract_compose.atom_index           # 增删原子后更新 原子总览.md
```

## 规则
- 纯重构不得改变任何快照；内容改动导致快照变化时，先向用户说明差异，确认后再 `--update`，提交说明写清原因。
- 内容与代码分离：改条款改 `library/`，不在代码里写类型相关的判断（类型设置放 `library/<类型>/type.yaml`）。
- 路径只在 `contract_compose/paths.py` 定义。
- 目录与程序固定读取的文件用英文；原子文件名、选项库文件名、yaml 键名、给人看的文档用中文（它们是数据，改名会断引用）。
- 原子 ID 一经分配不改；块 / 表格 XML 不手改；改样式模板前先告知用户。
- 拿不准法律原意的改动写入对应类型的 `修订记录.md`“存疑”，不擅自改。
- `output/`（除两份示例）、`library/common/presets/backups/`、`__pycache__/` 不进 git。
