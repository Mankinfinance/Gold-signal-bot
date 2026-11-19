"""Strategy families and their parameter grids.

Each strategy returns four boolean Series evaluated at bar CLOSE:
long_entry, short_entry, long_exit, short_exit. The engine acts on them at the
NEXT bar's open, so nothing peeks into the future.

Risk params shared by every family:
  stop_atr : initial stop distance in ATR(14) multiples
  rr       : fixed target as a multiple of the stop distance (0 = no target)
  trail    : trail the stop at stop_atr * ATR behind the best close
"""
from itertools import product

import pandas as pd

from . import indicators as ind


def _cross_up(a, b):
    return (a > b) & (a.shift() <= b.shift())


def _cross_dn(a, b):
    return (a < b) & (a.shift() >= b.shift())


def ema_cross(df, fast, slow, adx_min, **_):
    f, s = ind.ema(df.close, fast), ind.ema(df.close, slow)
    strong = ind.adx(df) > adx_min
    up, dn = _cross_up(f, s), _cross_dn(f, s)
    return up & strong, dn & strong, dn, up


def donchian_breakout(df, n, exit_n, **_):
    hi, lo = ind.donchian(df, n)
    xhi, xlo = ind.donchian(df, exit_n)
    trend = ind.ema(df.close, 200)
    le = (df.close > hi) & (df.close > trend)
    se = (df.close < lo) & (df.close < trend)
    return le, se, df.close < xlo, df.close > xhi


def rsi_pullback(df, period, lo, trend_n, **_):
    r = ind.rsi(df.close, period)
    t = ind.ema(df.close, trend_n)
    le = (df.close > t) & (r < lo)
    se = (df.close < t) & (r > 100 - lo)
    return le, se, r > 55, r < 45


def bb_fade(df, n, k, trend_n, **_):
    lo, mid, hi = ind.bollinger(df.close, n, k)
    t = ind.ema(df.close, trend_n)
    back_in_lo = (df.close > lo) & (df.close.shift() <= lo.shift())
    back_in_hi = (df.close < hi) & (df.close.shift() >= hi.shift())
    return back_in_lo & (df.close > t), back_in_hi & (df.close < t), \
        df.close >= mid, df.close <= mid


def supertrend_flip(df, n, mult, **_):
    d = ind.supertrend(df, n, mult)
    up, dn = (d == 1) & (d.shift() == -1), (d == -1) & (d.shift() == 1)
    return up, dn, dn, up


def macd_trend(df, fast, slow, trend_n, **_):
    m, s = ind.macd(df.close, fast, slow)
    t = ind.ema(df.close, trend_n)
    up, dn = _cross_up(m, s), _cross_dn(m, s)
    return up & (df.close > t), dn & (df.close < t), dn, up


def _grid(**kw):
    keys = list(kw)
    return [dict(zip(keys, v)) for v in product(*kw.values())]


TREND_RISK = dict(stop_atr=[2.0, 3.0], rr=[0, 3.0], trail=[True, False])
REVERT_RISK = dict(stop_atr=[1.5, 2.5], rr=[1.0, 2.0], trail=[False])

FAMILIES = {
    "ema_cross": (ema_cross, _grid(fast=[10, 20], slow=[50, 100], adx_min=[0, 20],
                                   **TREND_RISK)),
    "donchian_breakout": (donchian_breakout, _grid(n=[20, 55], exit_n=[10, 20],
                                                   **TREND_RISK)),
    "supertrend_flip": (supertrend_flip, _grid(n=[10, 14], mult=[2.5, 3.5],
                                               **TREND_RISK)),
    "macd_trend": (macd_trend, _grid(fast=[12], slow=[26], trend_n=[100, 200],
                                     **TREND_RISK)),
    "rsi_pullback": (rsi_pullback, _grid(period=[2, 5], lo=[10, 25],
                                         trend_n=[100, 200], **REVERT_RISK)),
    "bb_fade": (bb_fade, _grid(n=[20], k=[2.0, 2.5], trend_n=[100, 200],
                               **REVERT_RISK)),
}


def signals(family, df, params):
    fn = FAMILIES[family][0]
    out = fn(df, **params)
    return [pd.Series(x, index=df.index).fillna(False).astype(bool) for x in out]
