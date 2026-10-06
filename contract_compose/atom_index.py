# -*- coding: utf-8 -*-
"""重新生成 library/<类型>/原子总览.md。用法（在项目根目录运行）：python -m contract_compose.atom_index FA"""
import os, re, sys, glob
from . import paths
from .library import load_atoms, load_yaml
from .assembler import numbering


def main(ct):
    td = paths.type_dir(ct)
    atoms = load_atoms(td)
    recipe = load_yaml(os.path.join(td, paths.RECIPE), {})
    items = [it for it in recipe['顺序'] if '原子' in it]
    nos = numbering(atoms, [it['原子'] for it in items], recipe.get('编号起始', 1))
    rows = []
    for it in items:
        aid = it['原子']; a = atoms[aid]; m, body, fn = a['meta'], a['body'], a['file']
        text = body
        for t in re.findall(r'\{\{table:([^}]+)\}\}', body):
            for f in glob.glob(os.path.join(td, paths.TABLES, re.sub(r'\$[\w一-鿿]+', '*', t) + '.xml')):
                text += open(f, encoding='utf-8').read()
        ph = [x.split(':', 1)[1] if x.startswith(('英文数字:', '中文数字:')) else x for x in re.findall(r'\{\{([^}]+)\}\}', text)]
        vals = sorted({x[:-3] if x.endswith('_en') else x for x in ph if not x.startswith(('ref:', 'table:', '选项'))})
        ops = sorted({x.split(':', 1)[1].removesuffix('_en') for x in ph if x.startswith('选项')})
        refs = sorted({x[4:] for x in ph if x.startswith('ref:')})
        note = []
        if it.get('条件'): note.append(f"条件：{it['条件']}（不成立时标注不适用）")
        if it.get('仅当选项'): note.append('仅当 ' + '、'.join(f'{k}={v}' for k, v in it['仅当选项'].items()) + '（否则标注不适用）')
        rows.append(f"| {nos[aid]} | {aid} | {m['名称']} | {m['层级']} | `{fn}` | {'、'.join(vals)} | {'、'.join(ops)} | {'、'.join(refs)} | {'；'.join(note)} |")
    out = [f'# {ct} 原子总览', '',
           '按合同顺序列出全部条款原子。“编号”为默认组装（全部条款）时的条款号；改条款文字时打开“文件”列对应的 `atoms/` 文件。',
           '本表由 `python -m contract_compose.atom_index` 根据原子文件生成，增删或修改条款后可重新运行。', '',
           '| 编号 | ID | 名称 | 层级 | 文件 | 值变量 | 选项变量 | 引用 | 备注 |', '|---|---|---|---|---|---|---|---|---|'] + rows
    open(os.path.join(td, paths.ATOM_INDEX), 'w', encoding='utf-8').write('\n'.join(out) + '\n')
    print(f'{ct}: {len(rows)} 个原子 → library/{ct}/{paths.ATOM_INDEX}')


if __name__ == '__main__':
    main(sys.argv[1] if len(sys.argv) > 1 else 'FA')
