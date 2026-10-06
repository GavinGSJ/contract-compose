# -*- coding: utf-8 -*-
"""
命令行（在项目根目录运行）：
    python -m contract_compose configs/示例_FA_防腐油漆.yaml   # 按配置生成合同 + 生成报告
    python -m contract_compose --母本 FA                       # 用全部默认值生成，用于和母本比对
    python -m contract_compose --标注 PO                       # 生成变量标注版母本
"""
import os, argparse
import yaml

from . import paths
from .assembler import build
from .library import list_types


def main(argv=None):
    ap = argparse.ArgumentParser(prog='python -m contract_compose')
    ap.add_argument('配置', nargs='?', help='合同配置文件（configs/*.yaml）')
    ap.add_argument('--标注', '--annotate', dest='标注', metavar='合同类型',
                    help='生成“变量标注版”母本：所有变量黄色高亮并写明变量名')
    ap.add_argument('--母本', '--regress', dest='母本', metavar='合同类型',
                    help='用全部默认值生成，用于与母本比对')
    a = ap.parse_args(argv)
    if a.标注:
        out = os.path.join(paths.type_dir(a.标注), f'{a.标注}母本_变量标注版.docx')
        os.makedirs(os.path.dirname(out), exist_ok=True)
        doc, used, missing, order, na = build({'合同类型': a.标注}, regress=True, mark_vars=True)
        doc.save(out); print('已生成：', out, f'（{len(order)} 个原子）'); return
    if a.母本:
        cfg = {'合同类型': a.母本}; out = os.path.join(paths.OUTPUT, f'母本比对_{a.母本}_组装结果.docx')
    else:
        if not a.配置: ap.error('请指定合同配置文件')
        cfg = yaml.safe_load(open(a.配置, encoding='utf-8'))
        name = cfg.get('输出文件名') or f"{cfg.get('变量', {}).get('合同编号', '合同')}.docx"
        out = os.path.join(paths.OUTPUT, name)
    os.makedirs(os.path.dirname(out), exist_ok=True)
    doc, used, missing, order, na = build(cfg, regress=bool(a.母本))
    doc.save(out)
    rep = [f'已生成：{os.path.relpath(out, paths.ROOT)}（{cfg.get("合同类型") or list_types()[0]}）', f'条款原子：{len(order)} 个',
           '选用的写法：' + '、'.join(f'{k}={v}' for k, v in used.items()),
           '标注不适用：' + ('、'.join(na) or '无')]
    if not a.母本:
        rep += [f'未填变量（{len(missing)} 个，Word 中黄色标出）：' + ('、'.join(sorted(missing)) or '无')]
    print('\n'.join(rep))
    if not a.母本:
        open(os.path.splitext(out)[0] + '_生成报告.txt', 'w', encoding='utf-8').write('\n'.join(rep) + '\n')


if __name__ == '__main__':
    main()
