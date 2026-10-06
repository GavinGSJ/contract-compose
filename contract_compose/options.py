# -*- coding: utf-8 -*-
"""选项库：确定每个选项变量选用哪种写法；把预存库中的项目条款并入选项。"""


def end_punct(text, en=False):
    """条款句末补句号（中文“。”，英文“.”）"""
    t = str(text or '').strip()
    if not t or t.startswith('{{'):
        return t
    if en:
        return t if t[-1] in '.。' else t + '.'
    return t if t[-1] in '。.' else t + '。'


def merge_preset_options(opts, presets):
    """把预存库中的项目条款并入选项库（如 质保期 ← presets/项目信息），按项目编号自动选用"""
    for name, o in opts.items():
        src = o.get('预存来源')
        if not src or src.get('库') not in presets:
            continue
        o.setdefault('项目预设', {})
        new = {}
        for code, e in presets[src['库']]['条目'].items():
            zh, en = e.get(src['中文']), e.get(src['英文'])
            if not (zh or en):
                continue
            new[str(code)] = {'名称': src.get('名称', '项目预设'), '中文': end_punct(zh), '英文': end_punct(en, True)}
            o['项目预设'][str(code).strip().upper()] = str(code)
        # 项目预设排在模板默认之后、自定义之前
        items = list(o['选项'].items())
        tail = [(k, v) for k, v in items if k == '自定义']
        o['选项'] = dict([(k, v) for k, v in items if k != '自定义'] + list(new.items()) + tail)


def choose(name, o, values, choices):
    """选项变量的取值：明确选择 → 项目预设（按项目编号）→ 跟随变量 → 默认"""
    if choices.get(name):
        k = str(choices[name])
        if k not in o['选项']:
            raise SystemExit(f'选项库“{name}”中没有选项“{k}”，可选：{list(o["选项"])}')
        return k
    pid = str(values.get('项目编号', '')).strip().upper()
    if o.get('项目预设') and pid in o['项目预设']:
        return o['项目预设'][pid]
    if o.get('跟随变量') and values.get(o['跟随变量']):
        k = str(values[o['跟随变量']]).split()[0]
        if k in o['选项']:
            return k
    return str(o['默认'])
