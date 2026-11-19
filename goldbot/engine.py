"""Bar-by-bar backtest engine, also used live to work out the current position.

Rules (deliberately conservative):
- Signals at bar close, fills at next bar open.
- If the stop and target are both touched inside one bar, the stop is assumed hit.
- If price gaps through the stop, the fill is the open (worse than the stop).
- Every trade pays spread + slippage, and overnight funding at each 22:00 UTC
  rollover it is held through.
- Results are in R: profit divided by the initial risk (entry to stop), so they
  are independent of position size.
"""
from dataclasses import dataclass, asdict

import numpy as np
import pandas as pd

from . import indicators as ind
from .data import TF_HOURS


@dataclass
class Position:
    direction: int
    entry_time: str
    entry: float
    stop: float
    target: float | None
    risk: float
    best: float
    funding: float = 0.0


def _rollover_mask(index, tf):
    """True for bars whose span crosses the 22:00 UTC funding rollover."""
    h = TF_HOURS[tf]
    start = index.hour + index.minute / 60
    end = start + h
    return np.asarray(((start < 22) & (end >= 22)) | (end >= 46), dtype=bool)


def run(df, sigs, stop_atr, rr, trail, costs, tf="1h"):
    le, se, lx, sx = (s.to_numpy() for s in sigs)
    o, h, l, c = (df[k].to_numpy() for k in ("open", "high", "low", "close"))
    a = ind.atr(df).to_numpy()
    roll = _rollover_mask(df.index, tf)
    times = df.index
    cost = costs["spread_usd"] + costs["slippage_usd"]
    fund_rate = costs["overnight_funding_pct"] / 100

    trades, pos, pending = [], None, 0

    def close(i, price, reason):
        nonlocal pos
        pnl = pos.direction * (price - pos.entry) - cost - pos.funding
        trades.append(dict(entry_time=pos.entry_time, exit_time=str(times[i]),
                           direction=pos.direction, entry=pos.entry, exit=price,
                           risk=pos.risk, r=pnl / pos.risk, reason=reason))
        pos = None

    for i in range(1, len(df)):
        # 1) act on the decision made at the previous close
        if pending and (pos is None or pending == -pos.direction):
            if pos is not None:
                close(i, o[i], "flip")
            risk = stop_atr * a[i - 1]
            if risk > 0 and not np.isnan(risk):
                d = pending
                pos = Position(d, str(times[i]), o[i], o[i] - d * risk,
                               o[i] + d * rr * risk if rr else None, risk, o[i])
        elif pending == 2 and pos is not None:
            close(i, o[i], "exit_signal")
        pending = 0

        # 2) intrabar stop / target
        if pos is not None:
            d = pos.direction
            if (d == 1 and o[i] <= pos.stop) or (d == -1 and o[i] >= pos.stop):
                close(i, o[i], "stop_gap")
            elif (d == 1 and l[i] <= pos.stop) or (d == -1 and h[i] >= pos.stop):
                close(i, pos.stop, "stop")
            elif pos.target is not None and (
                    (d == 1 and h[i] >= pos.target) or (d == -1 and l[i] <= pos.target)):
                close(i, pos.target, "target")

        # 3) end of bar bookkeeping
        if pos is not None:
            if roll[i]:
                pos.funding += fund_rate * c[i]
            if trail and not np.isnan(a[i]):
                d = pos.direction
                pos.best = max(pos.best, c[i]) if d == 1 else min(pos.best, c[i])
                new = pos.best - d * stop_atr * a[i]
                pos.stop = max(pos.stop, new) if d == 1 else min(pos.stop, new)

        # 4) decisions at this close
        if pos is None:
            pending = 1 if le[i] else (-1 if se[i] else 0)
        else:
            if pos.direction == 1 and se[i]:
                pending = -1
            elif pos.direction == -1 and le[i]:
                pending = 1
            elif (pos.direction == 1 and lx[i]) or (pos.direction == -1 and sx[i]):
                pending = 2

    t = pd.DataFrame(trades, columns=["entry_time", "exit_time", "direction", "entry",
                                      "exit", "risk", "r", "reason"])
    return t, (asdict(pos) if pos else None), pending


def metrics(r):
    r = pd.Series(r, dtype=float)
    n = len(r)
    if n == 0:
        return dict(trades=0, win_rate=0, profit_factor=0, avg_r=0, total_r=0,
                    max_dd_r=0, score=-1e9)
    wins, losses = r[r > 0].sum(), -r[r < 0].sum()
    eq = r.cumsum()
    dd = (eq.cummax().clip(lower=0) - eq).max()
    return dict(trades=n, win_rate=round(float((r > 0).mean()), 3),
                profit_factor=round(float(wins / losses), 2) if losses > 0 else 99.0,
                avg_r=round(float(r.mean()), 3), total_r=round(float(r.sum()), 2),
                max_dd_r=round(float(dd), 2),
                score=float(r.mean() * np.sqrt(n)))
