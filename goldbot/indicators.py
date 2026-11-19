"""Causal technical indicators (each value only uses data up to that bar)."""
import numpy as np
import pandas as pd


def ema(s, n):
    return s.ewm(span=n, adjust=False, min_periods=n).mean()


def wilder(s, n):
    return s.ewm(alpha=1 / n, adjust=False, min_periods=n).mean()


def atr(df, n=14):
    pc = df["close"].shift()
    tr = pd.concat([df["high"] - df["low"], (df["high"] - pc).abs(),
                    (df["low"] - pc).abs()], axis=1).max(axis=1)
    return wilder(tr, n)


def rsi(s, n=14):
    d = s.diff()
    up = wilder(d.clip(lower=0), n)
    dn = wilder(-d.clip(upper=0), n)
    return 100 - 100 / (1 + up / dn.replace(0, np.nan))


def adx(df, n=14):
    h, l = df["high"], df["low"]
    upm, dnm = h.diff(), -l.diff()
    pdm = pd.Series(np.where((upm > dnm) & (upm > 0), upm, 0.0), index=df.index)
    ndm = pd.Series(np.where((dnm > upm) & (dnm > 0), dnm, 0.0), index=df.index)
    a = atr(df, n)
    pdi = 100 * wilder(pdm, n) / a
    ndi = 100 * wilder(ndm, n) / a
    dx = 100 * (pdi - ndi).abs() / (pdi + ndi).replace(0, np.nan)
    return wilder(dx, n)


def bollinger(s, n=20, k=2.0):
    m = s.rolling(n).mean()
    sd = s.rolling(n).std()
    return m - k * sd, m, m + k * sd


def donchian(df, n):
    """Channel of the PRIOR n bars (excludes current bar)."""
    return df["high"].rolling(n).max().shift(), df["low"].rolling(n).min().shift()


def macd(s, fast=12, slow=26, sig=9):
    m = ema(s, fast) - ema(s, slow)
    return m, ema(m, sig)


def supertrend(df, n=10, mult=3.0):
    a = atr(df, n).to_numpy()
    h, l, c = (df[k].to_numpy() for k in ("high", "low", "close"))
    hl2 = (h + l) / 2
    ub, lb = hl2 + mult * a, hl2 - mult * a
    dirn = np.zeros(len(df))
    fu, fl = ub.copy(), lb.copy()
    for i in range(1, len(df)):
        if np.isnan(a[i]):
            continue
        if np.isnan(fu[i - 1]):
            continue
        fu[i] = ub[i] if (ub[i] < fu[i - 1] or c[i - 1] > fu[i - 1]) else fu[i - 1]
        fl[i] = lb[i] if (lb[i] > fl[i - 1] or c[i - 1] < fl[i - 1]) else fl[i - 1]
        if c[i] > fu[i - 1]:
            dirn[i] = 1
        elif c[i] < fl[i - 1]:
            dirn[i] = -1
        else:
            dirn[i] = dirn[i - 1]
    return pd.Series(dirn, index=df.index)
