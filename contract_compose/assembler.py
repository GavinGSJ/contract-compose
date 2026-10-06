# -*- coding: utf-8 -*-
"""
合同组装器：按 配方 + 选项库 + 变量 把原子组装成 Word 合同。

目录结构见 paths.py：
    library/common/   预存库、付款条款库、通用选项库、通用变量字典
    library/FA|PO/    各合同类型的原子、配方、样式模板、块、表格、专属选项库与变量字典

用法（在项目根目录运行）：
    python -m contract_compose configs/示例_FA_防腐油漆.yaml
    python -m contract_compose --母本 FA     # 用全部默认值生成，用于和母本比对

依赖：pip install python-docx pyyaml lxml
"""
import os, re, sys, copy, glob, argparse
import yaml
from docx import Document
from docx.oxml.ns import qn
from lxml import etree

from . import paths
from .paths import ROOT, COMMON
TYPES = ['FA', 'PO']
CTYPE = 'FA'                                                            # 当前合同类型（load_library 设置）


def type_dir(ctype=None):
    return paths.type_dir(ctype or CTYPE)
W = 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'
XML_SPACE = '{http://www.w3.org/XML/1998/namespace}space'
MISS_L, MISS_R = '\u0001', '\u0002'          # 未填变量标记（内部使用）
MARK_VARS = False                                       # 母本标注模式：所有变量显示为黄色“【变量：名称｜母本值】”
LABEL = '待填'
NA_MARK = '（不适用 Not Applicable）'                # 不适用条款标题后缀
NA_EXCLUDE = ['PRI-02', 'PAY-02']                # 付款条款不做不适用标注（未用节点直接不出现）


# ======================= 读取原子库 =======================
def _yaml(p, default=None):
    return (yaml.safe_load(open(p, encoding='utf-8')) or default) if os.path.exists(p) else default


def for_type(x, ctype):
    """取按合同类型区分的值：{FA: ..., PO: ...} → 当前类型的值；其他值原样返回"""
    if isinstance(x, dict) and set(x) and set(x) <= set(TYPES):
        return x.get(ctype)
    return x


def load_library(ctype=None):
    """读取 library/common/ + library/<合同类型>/ 下的原子库；类型专属的选项库、变量字典覆盖公共的同名项"""
    global CTYPE, PAY
    CTYPE = ctype or CTYPE
    td = type_dir()
    atoms = {}
    for p in glob.glob(os.path.join(td, paths.ATOMS, '*.md')):
        _, fm, body = open(p, encoding='utf-8').read().split('---', 2)
        m = yaml.safe_load(fm)
        atoms[m['id']] = {'meta': m, 'body': body.strip('\n')}
    opts = {}
    for d in (COMMON, td):
        for p in sorted(glob.glob(os.path.join(d, paths.OPTIONS, '*.yaml'))):
            opts[os.path.splitext(os.path.basename(p))[0]] = _yaml(p, {})
    for o in opts.values():                      # 选项按合同类型过滤，默认值/节点可按类型区分
        o['默认'] = for_type(o.get('默认'), CTYPE)
        o['选项'] = {k: v for k, v in (o.get('选项') or {}).items()
                     if CTYPE in (v.get('适用') or TYPES)}
        for v in o['选项'].values():
            if '节点' in v: v['节点'] = for_type(v['节点'], CTYPE) or []
    V = dict(_yaml(os.path.join(COMMON, paths.VARIABLES), {}))
    for k, v in (_yaml(os.path.join(td, paths.VARIABLES), {}) or {}).items():
        V[k] = {**V.get(k, {}), **v}
    recipe = _yaml(os.path.join(td, paths.RECIPE), {})
    PAY = _yaml(os.path.join(COMMON, paths.PAYMENT_TERMS), {})
    presets = load_presets()
    entities = (presets.get('买方主体') or {}).get('条目') or {}
    merge_preset_options(opts, presets)
    return atoms, opts, V, recipe, entities


def end_punct(text, en=False):
    """条款句末补句号（中文“。”，英文“.”）"""
    t = str(text or '').strip()
    if not t or t.startswith('{{'):
        return t
    if en:
        return t if t[-1] in '.。' else t + '.'
    return t if t[-1] in '。.' else t + '。'


def merge_preset_options(opts, presets):
    """把预存库中的项目条款并入选项库（如 质保期 ← 预存库/项目信息），按项目编号自动选用"""
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


# ======================= 计算变量：价款、技术协议 =======================
from decimal import Decimal, ROUND_HALF_UP, InvalidOperation

# 币种：代码 → (符号, 中文名, 英文写法)；外币默认不计增值税
CURRENCIES = {'RMB': ('￥', '人民币', 'RMB'), 'USD': ('$', '美元', 'USD'),
              'EUR': ('€', '欧元', 'EUR'), 'GBP': ('£', '英镑', 'GBP')}
NO_TAX = '不涉及增值税'
TAX_RATES = ['13%', '9%', '6%', '0%', NO_TAX]
YES = ('是', '有', 'true', 'True', True, '1', 1)


def parse_amount(x):
    if x in (None, ''): return None
    try:
        return Decimal(re.sub(r'[^\d.\-]', '', str(x))).quantize(Decimal('0.01'), ROUND_HALF_UP)
    except InvalidOperation:
        return None


def fmt_money(x, sym):
    return f'{sym}{x:,.2f}'


def cn_upper(x):
    """金额中文大写：113000 → 壹拾壹万叁仟元整"""
    D = '零壹贰叁肆伍陆柒捌玖'
    x = Decimal(x).quantize(Decimal('0.01'), ROUND_HALF_UP)
    neg = x < 0; x = abs(x)
    n = int(x); jiao = int(x * 10) % 10; fen = int(x * 100) % 10

    def four(g):
        out, zero = '', False
        for i, u in ((3, '仟'), (2, '佰'), (1, '拾'), (0, '')):
            d = g // 10 ** i % 10
            if d == 0:
                zero = bool(out)
            else:
                if zero: out += '零'; zero = False
                out += D[d] + u
        return out
    groups = []
    while n: groups.append(n % 10000); n //= 10000
    big = ['', '万', '亿', '万亿']
    s, prev = '', None
    for i in range(len(groups) - 1, -1, -1):
        g = groups[i]
        if g == 0:
            prev = 0; continue
        if s and (prev == 0 or prev % 10 == 0 or g < 1000): s += '零'
        s += four(g) + big[i]; prev = g
    s = (s + '元') if s else ''
    if jiao == 0 and fen == 0:
        s = (s or '零元') + '整'
    else:
        if jiao: s += D[jiao] + '角'
        elif s: s += '零'
        s += (D[fen] + '分') if fen else '整'
    return ('负' if neg else '') + s


def en_words(x):
    """金额英文大写：113000 → ONE HUNDRED AND THIRTEEN THOUSAND ONLY"""
    ONES = 'ZERO ONE TWO THREE FOUR FIVE SIX SEVEN EIGHT NINE TEN ELEVEN TWELVE THIRTEEN FOURTEEN FIFTEEN ' \
           'SIXTEEN SEVENTEEN EIGHTEEN NINETEEN'.split()
    TENS = 'ZERO TEN TWENTY THIRTY FORTY FIFTY SIXTY SEVENTY EIGHTY NINETY'.split()

    def h(n):
        w = []
        if n >= 100:
            w.append(ONES[n // 100] + ' HUNDRED'); n %= 100
            if n: w.append('AND')
        if n >= 20:
            w.append(TENS[n // 10] + ('-' + ONES[n % 10] if n % 10 else ''))
        elif n or not w:
            w.append(ONES[n])
        return ' '.join(w)
    x = Decimal(x).quantize(Decimal('0.01'), ROUND_HALF_UP)
    n = int(x); cents = int(x * 100) % 100
    if n == 0:
        words = 'ZERO'
    else:
        parts = []
        for v, name in ((10 ** 9, ' BILLION'), (10 ** 6, ' MILLION'), (10 ** 3, ' THOUSAND'), (1, '')):
            if n >= v:
                parts.append(h(n // v) + name); n %= v
        if len(parts) > 1 and 0 < int(x) % 1000 < 100 and 'AND' not in parts[-1]:
            parts.insert(-1, 'AND')
        words = ' '.join(parts)
    if cents:
        words += ' AND CENTS ' + h(cents)
    return words + ' ONLY'


def price_calc(total, currency='RMB', rate=None):
    """由含税总价计算不含税价、税额。rate 为 None/空/“（自动）”时：人民币 13%，外币不涉及增值税"""
    currency = currency if currency in CURRENCIES else 'RMB'
    if rate in (None, '', '（自动）'):
        rate = '13%' if currency == 'RMB' else NO_TAX
    incl = parse_amount(total)
    taxed = rate != NO_TAX
    r = Decimal(str(rate).rstrip('%')) / 100 if taxed else Decimal(0)
    out = {'币种': currency, '税率': rate, '计税': taxed}
    if incl is not None:
        excl = (incl / (1 + r)).quantize(Decimal('0.01'), ROUND_HALF_UP)
        out.update(含税=incl, 不含税=excl, 税额=incl - excl)
    return out


def derive_values(values):
    """由表单填写的值计算出合同中使用的变量（不覆盖已有的同名计算变量以外的内容）"""
    d = {}
    # ---- 质保期自定义：补句号
    for k, en in (('质保期_自定义', False), ('质保期_自定义_en', True)):
        if values.get(k): d[k] = end_punct(values[k], en)
    # ---- 技术协议
    if str(values.get('有技术协议', '是')) in [str(y) for y in YES]:
        d['技术协议说明'] = ('（编号 No.：{{技术协议号}}；版本 Rev.：{{技术协议版本}}；日期 Date：{{技术协议日期}}）')
        d['技术协议目录标注'] = ''
    else:
        d['技术协议说明'] = d['技术协议目录标注'] = NA_MARK
        if not values.get('技术协议号'): d['技术协议号'] = 'N/A'
    # ---- 合同价款
    c = price_calc(values.get('含税总价'), values.get('币种') or 'RMB', values.get('增值税率'))
    sym, cn, code = CURRENCIES[c['币种']]
    d['价款_币种中文'], d['价款_币种代码'] = cn, code
    d['价款_计税'] = '含税' if c['计税'] else '不含税'        # PO 价格表：含增值税行 / 不含增值税行
    d['增值税率'] = (c['税率'] if str(c['税率']).endswith('%') else f"{c['税率']}%") if c['计税'] else 'N/A'
    if '含税' in c:
        d['价款_含税_表'] = fmt_money(c['含税'], sym)
        d['价款_不含税_表'] = fmt_money(c['不含税'], sym)
        d['价款_税额_表'] = fmt_money(c['税额'], sym) if c['计税'] else 'N/A'
        d['价款_大写'] = cn_upper(c['含税'])
        d['价款_英文大写'] = en_words(c['含税'])
    else:
        for k in ('价款_含税_表', '价款_不含税_表', '价款_税额_表', '价款_大写', '价款_英文大写'):
            d[k] = '{{含税总价}}'
        if not c['计税']: d['价款_税额_表'] = 'N/A'
    return d


# ======================= 预存信息库 =======================
PRESET_DIR = paths.PRESETS


def load_presets():
    """读取 library/common/presets/*.yaml，返回 {库名: {名称, 说明, 字段: {变量: 显示名}, 条目: {条目名: {变量: 值}}}}"""
    out = {}
    for p in sorted(glob.glob(os.path.join(PRESET_DIR, '*.yaml'))):
        d = yaml.safe_load(open(p, encoding='utf-8')) or {}
        name = d.get('名称') or os.path.splitext(os.path.basename(p))[0]
        d.setdefault('字段', {}); d['条目'] = d.get('条目') or {}
        d['_文件'] = p
        out[name] = d
    return out


def save_preset(d, keep_backups=30):
    """写回预存库文件；写之前把旧文件存到 presets/backups/"""
    import shutil, datetime
    p = d.get('_文件') or os.path.join(PRESET_DIR, d['名称'] + '.yaml')
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


# ======================= 选项、变量、引用 =======================
def choose(name, o, values, choices):
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


PAY = {}


def pay_node(n):
    """取付款节点在当前合同类型下的定义（公共字段 + 类型专属字段）；该类型不适用时返回 None"""
    nd = PAY['节点'].get(n)
    if not nd:
        return None
    part = nd.get(CTYPE)
    if any(t in nd for t in TYPES) and part is None:
        return None
    base = {k: v for k, v in nd.items() if k not in TYPES}
    return {**base, **(part or {})}


def pay_nodes_available():
    return [n for n in (for_type(PAY.get('顺序'), CTYPE) or []) if pay_node(n)]


def payment_nodes(o, k, opts, values, choices):
    """返回 (节点列表, 质保方式)"""
    nodes = list(o['选项'][k].get('节点') or [])
    if k == '自定义':
        nodes = list(choices.get('付款节点') or [])
    mode = choose('质保方式', opts['质保方式'], values, choices) if '质保方式' in opts else '质保函'
    add = for_type(PAY.get('质保金模式追加'), CTYPE)
    if mode == '质保金' and add and add not in nodes:
        nodes.append(add)
    seq = for_type(PAY.get('顺序_质保金' if mode == '质保金' else '顺序'), CTYPE) \
        or for_type(PAY.get('顺序'), CTYPE) or []
    nodes = [n for n in seq if n in nodes] + [n for n in nodes if n not in seq]
    nodes = [n for n in nodes if pay_node(n) and pay_node(n).get('仅当质保方式') in (None, mode)]
    return nodes, mode


def pay_optional_docs(nodes):
    """所选节点中可选的单据：[(单据ID, 显示文字)]"""
    out, docs = [], PAY['单据']
    def walk(ids):
        for d in ids:
            d = d['单据'] if isinstance(d, dict) else d
            v = docs.get(d)
            if isinstance(v, dict):
                if '组' in v: walk(v['组']); continue
                if v.get('可选') and d not in [x for x, _ in out]:
                    t = v.get('正文', ''); t = t[0] if isinstance(t, list) else t
                    out.append((d, t))
                walk(v.get('子项') or [])
    for n in nodes:
        nd = pay_node(n) or {}
        walk(nd.get('单据', []) + (nd.get('单据_质保金') or []))
    return out


def pay_fields(o, k, opts, choices):
    """付款方案用到的变量：先各节点比例，再其他“付款”类变量（如付款天数、主材名称），按出现顺序"""
    nodes, _ = payment_nodes(o, k, opts, {}, choices)
    text = render_payment(o, k, opts, {}, choices, {})
    names = []
    for m in re.findall(r'\{\{([^}]+)\}\}', text):
        m = m.split(':', 1)[1] if m.startswith(('英文数字:', '中文数字:')) else m
        if m not in names and not m.startswith(('ref:', 'table:')): names.append(m)
    ratios = [pay_node(n)['比例变量'] for n in nodes]
    return ratios + [x for x in names if x not in ratios]


def render_payment(o, k, opts, values, choices, used):
    """按合同类型的排版输出付款节点：FA 为 4.2 下的 a) b)（单据为 1) 2)），PO 为 3.2.1 子条款（单据为 a. b.）"""
    nodes, mode = payment_nodes(o, k, opts, values, choices)
    used['质保方式'] = mode
    extra = set(choices.get('付款可选单据') or [])
    docs = PAY['单据']
    sub = for_type(PAY.get('排版'), CTYPE) == '子条款'
    T, B, D, DC, D2 = ('### ', '', '- ', '  ', '  - ') if sub else ('- ', '  ', '  - ', '    ', '    - ')

    def doc_lines(ids, ratio, lv=D, cont=DC):
        out = []
        for d in ids:
            if isinstance(d, dict):
                if d.get('质保方式') and d['质保方式'] != mode: continue
                if d.get('无节点') and d['无节点'] in nodes: continue
                if d.get('有节点') and d['有节点'] not in nodes: continue
                d = d['单据']
            v = docs[d]
            if isinstance(v, dict) and '组' in v:
                out += doc_lines(v['组'], ratio, lv, cont); continue
            table = None; children = []
            if isinstance(v, dict):
                if v.get('可选') and d not in extra: continue
                table, children = v.get('表格'), v.get('子项') or []
                v = v.get('正文', '')
            lines = v if isinstance(v, list) else [v]
            lines = [x.replace('{{本节点比例}}', '{{%s}}' % ratio) for x in lines]
            out.append(lv + lines[0])
            out += [cont + x for x in lines[1:]]
            if children:
                out += doc_lines(children, ratio, D2, '      ' if not sub else '    ')
            if table:
                out.append('{{table:%s}}' % table)
        return out
    parts = []
    for n in nodes:
        nd = pay_node(n)
        body = nd.get('正文_质保金') if mode == '质保金' and nd.get('正文_质保金') else nd.get('正文', [])
        ratio = nd.get('比例变量', '')
        parts.append(T + nd['标题'])
        parts += [B + x.replace('{{本节点比例}}', '{{%s}}' % ratio) for x in body]
        dl = nd.get('单据_质保金') if mode == '质保金' and nd.get('单据_质保金') is not None else nd.get('单据', [])
        parts += doc_lines(dl, ratio)
    return '\n\n'.join(parts)


def expand_options(text, opts, values, choices, used):
    lines = []
    for line in text.split('\n'):
        m = re.fullmatch(r'\s*\{\{选项:([^}]+)\}\}\s*', line)
        if m and m.group(1) in opts and opts[m.group(1)]['类型'] == '付款方案':
            o = opts[m.group(1)]; k = choose(m.group(1), o, values, choices); used[m.group(1)] = k
            lines.append(render_payment(o, k, opts, values, choices, used))
        elif m and m.group(1) in opts and opts[m.group(1)]['类型'] == '段落':
            o = opts[m.group(1)]; k = choose(m.group(1), o, values, choices); used[m.group(1)] = k
            lines.append(o['选项'][k]['正文'])
        else:
            lines.append(line)
    text = '\n'.join(lines)

    def rep(m):
        kind, name = m.group(1), m.group(2)
        en = name.endswith('_en'); base = name[:-3] if en else name
        o = opts[base]; k = choose(base, o, values, choices); used[base] = k
        if kind == '选项':
            if o['类型'] == '字母选择':
                return k
            opt = o['选项'][k]
            if opt.get('状态') == '待补':
                return f'{MISS_L}选项“{base}/{k}”尚无文字{MISS_R}'
            return opt['英文' if en else '中文']
        items = list(o['选项'].items())
        if o.get('列表格式') == '逐项':
            return '\n\n'.join('- ' + v['列表文字'] for _, v in items)
        if en:
            return '; '.join(f'{kk}) {v["英文"]}' for kk, v in items) + '.'
        return '；'.join(f'{kk}) {v["中文"]}' for kk, v in items) + '。'
    return re.sub(r'\{\{(选项|选项列表):([^}]+)\}\}', rep, text)


def num_en(x):
    """整数 → 英文小写：60 → sixty；15 → fifteen"""
    try: n = int(Decimal(str(x)))
    except Exception: return str(x)
    return en_words(n).replace(' ONLY', '').lower()


def num_cn(x):
    """数字 → 中文小写（用于“百分之…”）：0.5 → 零点五；15 → 十五；1.5 → 一点五"""
    D = '零一二三四五六七八九'
    try: d = Decimal(str(x).strip())
    except Exception: return str(x)
    ip, _, fp = format(d.normalize(), 'f').partition('.')
    n = int(ip)
    def small(n):
        if n < 10: return D[n]
        out = ''
        for i, u in ((3, '千'), (2, '百'), (1, '十'), (0, '')):
            q = n // 10 ** i % 10
            if q: out += D[q] + u
            elif out and n % 10 ** i: out += '零' if not out.endswith('零') else ''
        out = out.rstrip('零')
        return out[1:] if out.startswith('一十') else out
    return small(n) + ('点' + ''.join(D[int(c)] for c in fp) if fp else '')


def resolve_values(text, V, values, missing, regress=False, keep=None, na=False):
    def rep(m):
        k = m.group(1)
        if k.startswith(('ref:', 'table:')):
            return m.group(0)
        if k.startswith(('英文数字:', '中文数字:')):      # {{英文数字:付款天数}} → sixty
            kind, var = k.split(':', 1)
            val = resolve_values('{{%s}}' % var, V, values, missing, regress, keep, na)
            if MISS_L in val or val.startswith('{{'):
                return val
            return (num_en if kind == '英文数字' else num_cn)(val)
        if MARK_VARS and not k.startswith('选项'):
            v = V.get(k, {})
            ref = v.get('母本值') if v.get('母本值') not in (None, '') else v.get('默认值')
            return MISS_L + k + ('｜' + str(ref) if ref not in (None, '') else '') + MISS_R
        if k in values and values[k] is not None:      # 明确给出的值（含空值）直接使用
            return str(values[k])
        v = V.get(k, {})
        if regress:
            if v.get('类别') == '自动（主体库）':
                return m.group(0)
            if v.get('母本值') not in (None, ''):
                return str(v['母本值'])
            if keep is not None and k not in keep and v.get('默认值') in (None, ''):
                return ''
        if v.get('默认值') not in (None, ''):
            return str(v['默认值'])
        if na:                                         # 不适用条款：未填变量写 N/A，不计入待填
            return 'N/A'
        missing.add(k)
        return m.group(0) if regress else f'{MISS_L}{k}{MISS_R}'
    return re.sub(r'\{\{([^}]+)\}\}', rep, text)


def numbering(atoms, order, start=1):
    refs = {}; ch = start - 1; c1 = c2 = 0
    for aid in order:
        lv = atoms[aid]['meta']['层级']
        if lv == '章': ch += 1; c1 = 0; refs[aid] = str(ch)
        elif lv == '条款': c1 += 1; c2 = 0; refs[aid] = f'{ch}.{c1}'
        else: c2 += 1; refs[aid] = f'{ch}.{c1}.{c2}'
    return refs


# ======================= Word 写入 =======================
class Writer:
    MARKS = [('### ', '合同-子条款', 'C2'), ('## ', '合同-条款', 'C1'), ('# ', '合同-章标题', 'H1'),
             ('  - ', '合同-列项二级', 'L2'), ('  + ', '合同-列项二级', 'N2'), ('- ', '合同-列项', 'L1'),
             ('+ ', '合同-列项', 'N1'), ('<顶格> ', '合同-正文（顶格）', 'P'),
             ('    ', '合同-正文（二级续行）', 'CONT'), ('  ', '合同-正文（列项续行）', 'CONT')]
    FALLBACK = {'合同-正文（二级续行）': '合同-正文（列项续行）'}

    def __init__(self, template):
        self.doc = Document(template)
        self.body = self.doc.element.body
        self.sect = self.body.find(qn('w:sectPr'))
        for e in list(self.body):
            if e is not self.sect:
                self.body.remove(e)
        self.sid = {s.name: s.style_id for s in self.doc.styles}
        self.numxml = self.doc.part.numbering_part.element
        # 模板中已有的编号实例保留（1 = 章节/条款/列项主编号；其他为块中使用的独立列项）
        self.next_num = max([int(n.get(qn('w:numId'))) for n in self.numxml.findall(qn('w:num'))] + [1]) + 1
        self.list_num = None; self.groups = 0; self.prev = 'H1'

    def add(self, e):
        self.sect.addprevious(e); return e

    def new_num(self):
        nid = str(self.next_num); self.next_num += 1
        n = etree.SubElement(self.numxml, qn('w:num')); n.set(qn('w:numId'), nid)
        a = etree.SubElement(n, qn('w:abstractNumId')); a.set(qn('w:val'), '0')
        for lv in ('3', '4', '5', '6'):
            o = etree.SubElement(n, qn('w:lvlOverride')); o.set(qn('w:ilvl'), lv)
            s = etree.SubElement(o, qn('w:startOverride')); s.set(qn('w:val'), '1')
        return nid

    def runs(self, p, text):
        text = text.replace('\\*', '\u0003')
        bold = und = False
        for tok in re.split(r'(\*\*|<u>|</u>|<br>|\t|\u0001[^\u0002]*\u0002)', text):
            if not tok:
                continue
            if tok == '**': bold = not bold; continue
            if tok == '<u>': und = True; continue
            if tok == '</u>': und = False; continue
            r = etree.SubElement(p, qn('w:r'))
            rp = etree.SubElement(r, qn('w:rPr'))
            if bold: etree.SubElement(rp, qn('w:b'))
            if und: etree.SubElement(rp, qn('w:u')).set(qn('w:val'), 'single')
            if tok == '<br>': etree.SubElement(r, qn('w:br'))
            elif tok == '\t': etree.SubElement(r, qn('w:tab'))
            elif tok.startswith(MISS_L):
                etree.SubElement(rp, qn('w:highlight')).set(qn('w:val'), 'yellow')
                t = etree.SubElement(r, qn('w:t')); t.text = '【' + LABEL + '：' + tok[1:-1] + '】'
            else:
                t = etree.SubElement(r, qn('w:t')); t.text = tok.replace('\u0003', '*')
                t.set(XML_SPACE, 'preserve')
            if not len(rp): r.remove(rp)

    def para(self, style, text, num=None):
        p = etree.Element(qn('w:p')); ppr = etree.SubElement(p, qn('w:pPr'))
        style = style if style in self.sid else self.FALLBACK.get(style, '合同-正文')
        etree.SubElement(ppr, qn('w:pStyle')).set(qn('w:val'), self.sid[style])
        if num:
            n = etree.SubElement(ppr, qn('w:numPr'))
            etree.SubElement(n, qn('w:ilvl')).set(qn('w:val'), num[1])
            etree.SubElement(n, qn('w:numId')).set(qn('w:val'), num[0])
        self.runs(p, text)
        return self.add(p)

    def line(self, line):
        for mark, style, kind in self.MARKS:
            if line.startswith(mark):
                text = line[len(mark):]; break
        else:
            style, kind, text = '合同-正文', 'P', line
        num = None
        if kind in ('H1', 'C1', 'C2'):
            self.list_num = None; self.groups = 0
        elif kind in ('L1', 'N1'):
            if self.prev not in ('L1', 'L2', 'N1', 'N2', 'CONT'):      # 新的一组列项
                self.groups += 1
                self.list_num = self.new_num() if self.groups > 1 else None
            if kind == 'N1': num = (self.list_num or '1', '5')       # 数字列项 1) 2)：显式编号
            elif self.list_num: num = (self.list_num, '3')
        elif kind == 'L2' and self.list_num:
            num = (self.list_num, '4')
        elif kind == 'N2':
            num = (self.list_num or '1', '6')
        self.para(style, text.strip(), num)
        self.prev = kind

    def block(self, path, fill):
        root = etree.parse(path).getroot()
        for e in root:
            e = copy.deepcopy(e)
            strip_ids(e); fill(e)
            self.add(e)


def strip_ids(e):
    W14 = '{http://schemas.microsoft.com/office/word/2010/wordml}'
    for x in e.iter():
        for a in (W14 + 'paraId', W14 + 'textId'):
            if a in x.attrib: del x.attrib[a]


def fill_xml(e, fn):
    """替换 XML 中 w:t 文本里的 {{变量}}；未填变量所在的 run 标黄"""
    for t in e.iter(qn('w:t')):
        if t.text and '{{' in t.text:
            new = fn(t.text)
            if MISS_L in new:
                r = t.getparent(); rp = r.find(qn('w:rPr'))
                if rp is None: rp = etree.Element(qn('w:rPr')); r.insert(0, rp)
                if rp.find(qn('w:highlight')) is None:
                    etree.SubElement(rp, qn('w:highlight')).set(qn('w:val'), 'yellow')
                new = re.sub(MISS_L + r'([^' + MISS_R + r']*)' + MISS_R, '【' + LABEL + r'：\1】', new)
            t.text = new


# ======================= 主流程 =======================
def build(cfg, regress=False, keep=None):
    atoms, opts, V, recipe, entities = load_library(cfg.get('合同类型') or 'FA')
    values = dict(cfg.get('变量') or {})
    ent = cfg.get('买方主体') or (next(iter(entities)) if entities else None)
    if ent:
        if ent not in entities:
            raise SystemExit(f'预存库“买方主体”中没有“{ent}”，可选：{list(entities)}')
        for k, v in entities[ent].items(): values.setdefault(k, v)
    if regress: values = {}
    else: values.update(derive_values(values))
    choices = cfg.get('选项') or {}
    conds = set(cfg.get('条件') or [])
    # 所有条款一律保留；条件不成立或列入“不适用”的条款标注不适用（付款条款除外）
    order = [it['原子'] for it in recipe['顺序'] if '原子' in it]
    na = set() if regress else {it['原子'] for it in recipe['顺序']
                                if '原子' in it and it.get('条件') and it['条件'] not in conds}
    if not regress:
        na |= set(cfg.get('不适用') or [])
        for it in recipe['顺序']:                  # 仅在某选项取某值时适用（如 仲裁细则 仅当 争议解决=仲裁）
            for k, v in (it.get('仅当选项') or {}).items():
                if k in opts and choose(k, opts[k], values, choices) != str(v):
                    na.add(it['原子'])
    na -= set(NA_EXCLUDE)
    chap = {a['meta']['章']: aid for aid, a in atoms.items() if a['meta']['层级'] == '章'}
    inherit = {aid for aid in order if chap.get(atoms[aid]['meta']['章']) in na}   # 整章不适用
    refs = numbering(atoms, order, recipe.get('编号起始', 1))
    used, missing = {}, set()

    def fill(text, is_na=False):
        t = expand_options(text, opts, values, choices, used)
        t = resolve_values(t, V, values, missing, regress, keep, is_na)
        t = resolve_values(t, V, values, missing, regress, keep, is_na)   # 计算变量中嵌套的 {{变量}}
        return re.sub(r'\{\{ref:([^}]+)\}\}', lambda m: refs[m.group(1)], t)

    def mark(aid, t):
        if aid in na or aid in inherit:
            t = t.replace('N/A%', 'N/A')
        if aid not in na or (aid in inherit and atoms[aid]['meta']['层级'] != '章'):
            return t                                   # 整章不适用时只在章标题标注
        first, _, rest = t.partition('\n')
        m = re.match(r'(#+ |<顶格> )?(.*)', first.rstrip())
        lead, head = m.group(1) or '', m.group(2)
        first = lead + (head + NA_MARK if len(head) <= 80 else NA_MARK + head)   # 长条款文字：标注放在开头
        return first + ('\n' + rest if rest else '')

    w = Writer(os.path.join(type_dir(), recipe['样式模板']))
    rendered = [(aid, mark(aid, fill(atoms[aid]['body'], aid in na or aid in inherit))) for aid in order]
    for item in recipe['顺序']:
        if '块' in item:
            w.block(os.path.join(type_dir(), paths.BLOCKS, item['块'] + '.xml'), lambda e: fill_xml(e, fill))
        elif '目录' in item:
            w.para('合同-目录标题', item.get('标题', '目录CONTENT'))
            for x in item.get('前置行', ['第一部分 合同条款 Part I Contract Text']):
                w.para('toc 1', x)
            nfmt = item.get('编号格式', '{n}')
            heads = [(refs[aid], re.sub(r'^# ', '', t.split('\n')[0]).replace('**', ''))
                     for aid, t in rendered if atoms[aid]['meta']['层级'] == '章']
            for i, (n, h) in enumerate(heads):
                p = etree.Element(qn('w:p')); ppr = etree.SubElement(p, qn('w:pPr'))
                etree.SubElement(ppr, qn('w:pStyle')).set(qn('w:val'), w.sid['toc 1'])
                r = etree.SubElement(p, qn('w:r'))
                if i == 0:
                    etree.SubElement(r, qn('w:fldChar')).set(qn('w:fldCharType'), 'begin')
                    it = etree.SubElement(r, qn('w:instrText')); it.set(XML_SPACE, 'preserve')
                    it.text = ' TOC \\o "1-1" \\n \\h \\z \\u '
                    etree.SubElement(r, qn('w:fldChar')).set(qn('w:fldCharType'), 'separate')
                etree.SubElement(r, qn('w:t')).text = nfmt.format(n=n)
                etree.SubElement(r, qn('w:tab'))
                t = etree.SubElement(r, qn('w:t')); t.text = h; t.set(XML_SPACE, 'preserve')
                if i == len(heads) - 1:
                    etree.SubElement(r, qn('w:fldChar')).set(qn('w:fldCharType'), 'end')
                w.add(p)
            if item.get('附加块'):
                w.block(os.path.join(type_dir(), paths.BLOCKS, item['附加块'] + '.xml'), lambda e: fill_xml(e, fill))
    for aid, text in rendered:
        for line in text.split('\n'):
            if not line.strip():
                continue
            m = re.fullmatch(r'\s*\{\{table:([^}]+)\}\}\s*', line)
            if m:
                def tv(x):                              # 表格名中的 $变量（如 PO-SCO-$价款_计税）
                    k = x.group(1); v = V.get(k, {})
                    return str(values.get(k) or v.get('母本值') or v.get('默认值') or '')
                tid = re.sub(r'\$([\w\u4e00-\u9fff]+)', tv, m.group(1))
                w.block(os.path.join(type_dir(), paths.TABLES, tid + '.xml'), lambda e: fill_xml(e, fill))
                w.prev = 'TABLE'
            else:
                w.line(line)
    # 页眉页脚
    for rel in w.doc.part.rels.values():
        if rel.reltype.endswith(('/header', '/footer')):
            fill_xml(rel.target_part.element, fill)
    shown = [a for a in order if a in na and not (a in inherit and atoms[a]['meta']['层级'] != '章')]
    return w.doc, used, missing, order, shown


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('配置', nargs='?')
    ap.add_argument('--标注', metavar='合同类型', help='生成“变量标注版”母本：所有变量黄色高亮并写明变量名')
    ap.add_argument('--母本', metavar='合同类型', help='用全部默认值生成（FA 或 PO），用于与母本比对')
    a = ap.parse_args()
    if a.标注:
        global MARK_VARS, LABEL
        MARK_VARS, LABEL = True, '变量'
        cfg = {'合同类型': a.标注}
        out = os.path.join(paths.type_dir(a.标注), f'{a.标注}母本_变量标注版.docx')
        os.makedirs(os.path.dirname(out), exist_ok=True)
        doc, used, missing, order, na = build(cfg, regress=True)
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
    rep = [f'已生成：{os.path.relpath(out, ROOT)}（{cfg.get("合同类型") or "FA"}）', f'条款原子：{len(order)} 个',
           '选用的写法：' + '、'.join(f'{k}={v}' for k, v in used.items()),
           '标注不适用：' + ('、'.join(na) or '无')]
    if not a.母本:
        rep += [f'未填变量（{len(missing)} 个，Word 中黄色标出）：' + ('、'.join(sorted(missing)) or '无')]
    print('\n'.join(rep))
    if not a.母本:
        open(os.path.splitext(out)[0] + '_生成报告.txt', 'w', encoding='utf-8').write('\n'.join(rep) + '\n')


if __name__ == '__main__':
    main()
