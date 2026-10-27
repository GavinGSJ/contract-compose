# -*- coding: utf-8 -*-
"""分批交货计划：首批日期 + 批数 + 间隔月数 → 每批的交货日期（如 S416 每三个月交付一船套）。"""
import re, calendar

from .money import num_cn

DATE = re.compile(r'^\s*(\d{4})\s*[年\-/.]\s*(\d{1,2})\s*[月\-/.]\s*(\d{1,2})\s*日?\s*$')


def parse_date(text):
    """2027年1月26日 / 2027-01-26 / 2027/1/26 / 2027.1.26 → (年, 月, 日)；不是日期返回 None"""
    m = DATE.match(str(text or ''))
    if not m:
        return None
    y, mo, d = (int(x) for x in m.groups())
    return (y, mo, d) if 1 <= mo <= 12 and 1 <= d <= calendar.monthrange(y, mo)[1] else None


def add_months(date, k):
    """加 k 个月，日期超过当月天数时取当月最后一天"""
    y, mo, d = date
    t = y * 12 + (mo - 1) + k
    y, mo = divmod(t, 12); mo += 1
    return (y, mo, min(d, calendar.monthrange(y, mo)[1]))


def fmt(date):
    return '%d年%d月%d日' % date


def plan_lines(first, count, interval, first_fmt, other_fmt):
    """每批一行。first_fmt、other_fmt 中 {日期} 换成日期、{序号} 换成中文序号（二、三…）。
    日期、批数、间隔不合法时返回 None"""
    d0 = parse_date(first)
    try:
        n, step = int(str(count).strip()), int(str(interval).strip())
    except ValueError:
        return None
    if d0 is None or not 1 <= n <= 50 or step < 0:
        return None
    out = []
    for i in range(n):
        f = first_fmt if i == 0 else other_fmt
        out.append(f.replace('{序号}', num_cn(i + 1)).replace('{日期}', fmt(add_months(d0, i * step))))
    return out
