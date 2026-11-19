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


# session=True only allows entries 07:00-20:00 UTC (London + New York). Chosen in
# Nov 2026 testing: it was the best setup on Jul 2025-May 2026 and stayed the best
# on the untouched Jun-Nov 2026 holdout.
TREND_RISK = dict(stop_atr=[2.0, 3.0], rr=[0, 3.0], trail=[True, False], session=[False, True])
REVERT_RISK = dict(stop_atr=[1.5, 2.5], rr=[1.0, 2.0], trail=[False], session=[False, True])

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


def _htf_trend(df):
    """Direction of the next timeframe up (1h -> 4h EMA50, 4h -> daily EMA20),
    using only higher-timeframe bars that had fully closed."""
    step = df.index.to_series().diff().median()
    rule, n = ("4h", 50) if step <= pd.Timedelta(hours=1) else ("1D", 20)
    hc = df.close.resample(rule, **({"origin": "epoch"} if rule == "4h" else {})).last().dropna()
    up = (hc > ind.ema(hc, n)).astype(float).where(ind.ema(hc, n).notna())
    up = up.shift(1)  # label at bar START; shift so we only use closed bars
    return up.reindex(df.index, method="ffill")


# High win-rate profile: quick small target (0.2-0.33x the risk) with a wide stop.
# Wins ~85-90% of trades; each loss costs about 5 wins, so profit per trade is small.
HW_RISK = dict(stop_atr=[2.5, 4.0], rr=[0.2, 0.33], trail=[False], session=[False, True])
HIGH_WIN_FAMILIES = {
    "donchian_breakout": (donchian_breakout, _grid(n=[20, 55], exit_n=[10, 20], **HW_RISK)),
    "bb_fade": (bb_fade, _grid(n=[20], k=[2.0, 2.5], trend_n=[100, 200], **HW_RISK)),
    "rsi_pullback": (rsi_pullback, _grid(period=[2, 5], lo=[10, 25], trend_n=[100, 200], **HW_RISK)),
    "ema_cross": (ema_cross, _grid(fast=[10, 20], slow=[50, 100], adx_min=[0, 20], **HW_RISK)),
}
PROFILES = {"max_profit": FAMILIES, "high_win_rate": HIGH_WIN_FAMILIES}


def signals(family, df, params):
    p = dict(params)
    session, htf = p.pop("session", False), p.pop("htf", False)
    volf = p.pop("volf", False)
    p.pop("partial_r", None)
    fn = FAMILIES[family][0]
    le, se, lx, sx = [pd.Series(x, index=df.index).fillna(False).astype(bool)
                      for x in fn(df, **p)]
    if session:  # London open to New York afternoon, UTC
        hrs = pd.Series(df.index.hour, index=df.index)
        m = (hrs >= 7) & (hrs < 20)
        le, se = le & m, se & m
    if volf:  # skip panic spikes and dead markets
        ratio = ind.atr(df, 14) / ind.atr(df, 200)
        m = (ratio > 0.6) & (ratio < 1.8)
        le, se = le & m, se & m
    if htf:
        t = _htf_trend(df)
        le, se = le & (t == 1), se & (t == 0)
    return [le, se, lx, sx]
