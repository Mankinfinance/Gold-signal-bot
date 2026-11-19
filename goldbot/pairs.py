"""Gold vs silver statistical arbitrage (RESEARCH ONLY, not traded live).

Tested Nov 2026 on Jun 2024 to Nov 2026 hourly data: 0 of 144 setups were
profitable after Plus500 costs; walk-forward -15R. See reports/pairs_report.md.

Spread = log(gold) - beta * log(silver), where beta is a rolling hedge ratio
estimated on the previous `lookback` bars only. z = how many standard
deviations the spread is from its recent average.

  z > +entry  -> SHORT the spread: sell gold, buy silver (beta x the notional)
  z < -entry  -> LONG the spread:  buy gold, sell silver
  exit when z comes back inside +/-exit_z, or stop when it stretches a further
  stop_z beyond entry, or after max_hold bars.

Signals at bar close, fills at the NEXT bar's close. Costs: both legs' spreads
plus overnight funding on both legs. Results are in R, where 1R = the loss if
the stop is hit (stop distance in z x spread volatility at entry).
"""
import numpy as np
import pandas as pd

from .data import TF_HOURS, resample
from .engine import _rollover_mask


def build(gold, silver, lookback):
    df = pd.concat({"g": gold.close, "s": silver.close}, axis=1).dropna()
    lg, ls = np.log(df.g), np.log(df.s)
    # All window stats come from the PREVIOUS `lookback` bars, and the spread's
    # mean/std are computed with that same window's beta, so beta drift does not
    # leak into the z-score.
    r = lambda x: x.rolling(lookback)
    m_g, m_s = r(lg).mean().shift(1), r(ls).mean().shift(1)
    v_g, v_s = r(lg).var().shift(1), r(ls).var().shift(1)
    cov = r(lg).cov(ls).shift(1)
    beta = cov / v_s
    mu = m_g - beta * m_s
    sd = np.sqrt((v_g + beta ** 2 * v_s - 2 * beta * cov).clip(lower=1e-12))
    df["beta"], df["z"], df["sd"] = beta, (lg - beta * ls - mu) / sd, sd
    return df.dropna()


def run(df, entry, exit_z, stop_z, max_hold, costs, tf="1h"):
    g, s, z, beta, sd = (df[k].to_numpy() for k in ("g", "s", "z", "beta", "sd"))
    roll = _rollover_mask(df.index, tf)
    gcost = costs["spread_usd"] / g          # fraction of gold notional
    scost = costs["silver_spread_usd"] / s   # fraction of silver notional
    fund = costs["overnight_funding_pct"] / 100
    trades, pos = [], None
    pending = None
    for i in range(1, len(df)):
        if pending is not None:
            kind, d = pending
            pending = None
            if kind == "open":
                pos = dict(d=d, i0=i, g0=g[i], s0=s[i], b=beta[i - 1],
                           risk=(stop_z) * sd[i - 1], funding=0.0,
                           cost=gcost[i] + abs(beta[i - 1]) * scost[i])
            else:
                gr = np.log(g[i] / pos["g0"])
                sr = np.log(s[i] / pos["s0"])
                pnl = pos["d"] * (gr - pos["b"] * sr) - pos["cost"] - pos["funding"]
                trades.append(dict(entry_time=str(df.index[pos["i0"]]), exit_time=str(df.index[i]),
                                   direction=pos["d"], beta=pos["b"], entry_g=pos["g0"],
                                   entry_s=pos["s0"], r=pnl / pos["risk"], reason=d))
                pos = None
        if pos is not None:
            if roll[i]:
                pos["funding"] += fund * (1 + abs(pos["b"]))
            d = pos["d"]
            if (d == 1 and z[i] >= -exit_z) or (d == -1 and z[i] <= exit_z):
                pending = ("close", "converged")
            elif (d == 1 and z[i] <= -(entry + stop_z)) or (d == -1 and z[i] >= entry + stop_z):
                pending = ("close", "stop")
            elif i - pos["i0"] >= max_hold:
                pending = ("close", "time")
        elif z[i] >= entry:
            pending = ("open", -1)
        elif z[i] <= -entry:
            pending = ("open", 1)
    t = pd.DataFrame(trades, columns=["entry_time", "exit_time", "direction", "beta",
                                      "entry_g", "entry_s", "r", "reason"])
    return t, pos, pending


GRID = [dict(lookback=lb, entry=e, exit_z=x, stop_z=sz, max_hold=mh)
        for lb in (100, 250, 500) for e in (1.5, 2.0, 2.5) for x in (0.0, 0.5)
        for sz in (1.5, 2.5) for mh in (100, 300)]


def backtest_all(gold_h, silver_h, cfg, tfs=("1h", "4h")):
    costs = {**cfg["plus500"], "silver_spread_usd": cfg["plus500"].get("silver_spread_usd", 0.035)}
    rows = []
    for tf in tfs:
        g, s = resample(gold_h, tf), resample(silver_h, tf)
        cache = {}
        for p in GRID:
            if p["lookback"] not in cache:
                cache[p["lookback"]] = build(g, s, p["lookback"])
            t, _, _ = run(cache[p["lookback"]], p["entry"], p["exit_z"], p["stop_z"],
                          p["max_hold"], costs, tf)
            t["entry_time"] = pd.to_datetime(t["entry_time"], utc=True)
            rows.append(dict(tf=tf, family="gold_silver_pairs", params=p, trades=t))
    return rows
