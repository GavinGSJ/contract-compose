# -*- coding: utf-8 -*-
"""读取内容库：library/common/ + library/<合同类型>/ → Library 对象。"""
import os, glob
from dataclasses import dataclass, field
import yaml

from . import paths
from .options import merge_preset_options
from .presets import load_presets
from .constants import NA_MARK


@dataclass
class Library:
    """一种合同类型的全部内容（读取后不再改动）"""
    ctype: str
    settings: dict                                 # 类型设置（type.yaml）
    atoms: dict                                    # {原子ID: {'meta': 头信息, 'body': 正文}}
    opts: dict                                     # 选项库（公共 + 类型专属，已按类型过滤）
    V: dict                                        # 变量字典（类型专属覆盖公共的同名项）
    recipe: dict                                   # 配方
    entities: dict                                 # 预存库“买方主体”的条目
    pay: dict = field(default_factory=dict)        # 付款条款库
    annexes: dict = field(default_factory=dict)    # 合同附件，按配方“附件/顺序”排列 {附件ID: {'meta', 'body', 'file'}}

    @property
    def dir(self):
        return paths.type_dir(self.ctype)


def load_yaml(p, default=None):
    return (yaml.safe_load(open(p, encoding='utf-8')) or default) if os.path.exists(p) else default


def load_atoms(td, sub=paths.ATOMS):
    """读取 <类型目录>/atoms/*.md（附件为 annexes/）→ {ID: {'meta', 'body', 'file'}}"""
    atoms = {}
    for p in glob.glob(os.path.join(td, sub, '*.md')):
        _, fm, body = open(p, encoding='utf-8').read().split('---', 2)
        m = yaml.safe_load(fm)
        atoms[m['id']] = {'meta': m, 'body': body.strip('\n'), 'file': os.path.basename(p)}
    return atoms


def list_types():
    """全部合同类型：library/ 下有 type.yaml 的目录，按名称排序（第一个为默认类型）"""
    if not os.path.isdir(paths.LIBRARY):
        return []
    return sorted(d for d in os.listdir(paths.LIBRARY) if os.path.exists(os.path.join(paths.LIBRARY, d, paths.TYPE_FILE)))


TYPE_DEFAULTS = {'说明': '', '编号起始': 1, '付款条款': [], '履约保函条款': None, '表单标签': {}, '表单隐藏': [],
                 '不适用标注': NA_MARK, '货物明细': False}


def load_type(ctype):
    """读取 library/<类型>/type.yaml，补全默认值"""
    p = os.path.join(paths.type_dir(ctype), paths.TYPE_FILE)
    if not os.path.exists(p):
        raise SystemExit(f'没有合同类型“{ctype}”（缺少 library/{ctype}/{paths.TYPE_FILE}），已有：{list_types()}')
    s = {**TYPE_DEFAULTS, **(load_yaml(p, {}) or {})}
    for k in ('名称', '样式模板'):
        if not s.get(k):
            raise SystemExit(f'library/{ctype}/{paths.TYPE_FILE} 缺少“{k}”')
    s['代码'] = ctype
    s['付款条款'] = list(s['付款条款'] or [])
    s['表单标签'] = dict(s['表单标签'] or {})
    s['表单隐藏'] = list(s['表单隐藏'] or [])
    return s


def for_type(x, ctype):
    """取按合同类型区分的值：{FA: ..., PO: ...} → 当前类型的值；其他值原样返回"""
    if isinstance(x, dict) and set(x) and set(x) <= set(list_types()):
        return x.get(ctype)
    return x


def load_library(ctype=None):
    """读取 library/common/ + library/<合同类型>/；类型专属的选项库、变量字典覆盖公共的同名项。
    ctype 为空时取第一个类型"""
    ctype = ctype or list_types()[0]
    settings = load_type(ctype)
    types = list_types()
    td = paths.type_dir(ctype)
    atoms = load_atoms(td)
    opts = {}
    for d in (paths.COMMON, td):
        for p in sorted(glob.glob(os.path.join(d, paths.OPTIONS, '*.yaml'))):
            opts[os.path.splitext(os.path.basename(p))[0]] = load_yaml(p, {})
    for o in opts.values():                      # 选项按合同类型过滤，默认值/节点可按类型区分
        o['默认'] = for_type(o.get('默认'), ctype)
        o['选项'] = {k: v for k, v in (o.get('选项') or {}).items()
                     if ctype in (v.get('适用') or types)}
        for v in o['选项'].values():
            if '节点' in v: v['节点'] = for_type(v['节点'], ctype) or []
    V = dict(load_yaml(os.path.join(paths.COMMON, paths.VARIABLES), {}))
    for k, v in (load_yaml(os.path.join(td, paths.VARIABLES), {}) or {}).items():
        V[k] = {**V.get(k, {}), **v}
    recipe = load_yaml(os.path.join(td, paths.RECIPE), {})
    pay = load_yaml(os.path.join(paths.COMMON, paths.PAYMENT_TERMS), {})
    presets = load_presets()
    entities = (presets.get('买方主体') or {}).get('条目') or {}
    merge_preset_options(opts, presets)
    found = load_atoms(td, paths.ANNEXES)
    order = (recipe.get('附件') or {}).get('顺序') or []
    lost = [a for a in order if a not in found]
    if lost:
        raise SystemExit(f'配方“附件/顺序”中的附件在 library/{ctype}/{paths.ANNEXES}/ 中找不到：{lost}')
    annexes = {a: found[a] for a in order}
    return Library(ctype, settings, atoms, opts, V, recipe, entities, pay, annexes)
