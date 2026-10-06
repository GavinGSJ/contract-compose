# -*- coding: utf-8 -*-
"""金额与数字：价款计算（含税→不含税/税额）、中英文大写、数字转中英文。"""
import re
from decimal import Decimal, ROUND_HALF_UP, InvalidOperation

# 币种：代码 → (符号, 中文名, 英文写法)；外币默认不计增值税
CURRENCIES = {'RMB': ('￥', '人民币', 'RMB'), 'USD': ('$', '美元', 'USD'),
              'EUR': ('€', '欧元', 'EUR'), 'GBP': ('£', '英镑', 'GBP')}
NO_TAX = '不涉及增值税'
TAX_RATES = ['13%', '9%', '6%', '0%', NO_TAX]


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
