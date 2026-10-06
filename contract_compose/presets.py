# -*- coding: utf-8 -*-
"""预存信息库（library/common/presets/*.yaml）：读取与写回（写回前自动备份）。"""
import os, glob, shutil, datetime
import yaml

from . import paths


def load_presets():
    """读取 presets/*.yaml，返回 {库名: {名称, 说明, 字段: {变量: 显示名}, 条目: {条目名: {变量: 值}}}}"""
    out = {}
    for p in sorted(glob.glob(os.path.join(paths.PRESETS, '*.yaml'))):
        d = yaml.safe_load(open(p, encoding='utf-8')) or {}
        name = d.get('名称') or os.path.splitext(os.path.basename(p))[0]
        d.setdefault('字段', {}); d['条目'] = d.get('条目') or {}
        d['_文件'] = p
        out[name] = d
    return out


def save_preset(d, keep_backups=30):
    """写回预存库文件；写之前把旧文件存到 presets/backups/（保留最近 keep_backups 份）"""
    p = d.get('_文件') or os.path.join(paths.PRESETS, d['名称'] + '.yaml')
    bak = paths.PRESET_BACKUPS; os.makedirs(bak, exist_ok=True)
    stem = os.path.splitext(os.path.basename(p))[0]
    if os.path.exists(p):
        shutil.copy2(p, os.path.join(bak, f"{stem}_{datetime.datetime.now():%Y%m%d-%H%M%S}.yaml"))
        olds = sorted(glob.glob(os.path.join(bak, stem + '_2*.yaml')))
        for f in olds[:-keep_backups]:
            try: os.remove(f)
            except OSError: pass
    clean = {k: v for k, v in d.items() if not k.startswith('_')}
    clean['条目'] = {n: {k: ('' if v is None else str(v)) for k, v in e.items()} for n, e in clean['条目'].items()}
    with open(p, 'w', encoding='utf-8') as f:
        f.write('# 预存信息库（可在表单“预存信息管理”页面中编辑）\n')
        f.write(yaml.safe_dump(clean, allow_unicode=True, sort_keys=False, width=1000))
    d['_文件'] = p
    return p
