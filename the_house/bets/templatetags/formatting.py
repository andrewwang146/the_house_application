from decimal import Decimal, ROUND_HALF_UP
from django import template

register = template.Library()

TWOP = Decimal('0.01')
THREEP = Decimal('0.001')

@register.filter
def money(val):
    if val is None or val == '':
        return "0.00"
    d = Decimal(val).quantize(TWOP, rounding=ROUND_HALF_UP)
    return f"{d:.2f}"

@register.filter
def oddsfmt(val):
    if val is None or val == '':
        return ""
    d = Decimal(val)
    if d < Decimal('1.01'):
        d = d.quantize(THREEP, rounding=ROUND_HALF_UP)
        return f"{d:.3f}"
    d = d.quantize(TWOP, rounding=ROUND_HALF_UP)
    return f"{d:.2f}"

@register.filter
def get_item(d, key):
    try:
        return d.get(key)
    except Exception:
        return None

@register.filter
def mul(a, b):
    try:
        return Decimal(a) * Decimal(b)
    except Exception:
        return Decimal('0')

@register.filter
def sub(a, b):
    try:
        return Decimal(a) - Decimal(b)
    except Exception:
        return Decimal('0')
