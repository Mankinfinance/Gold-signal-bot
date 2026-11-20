import sys, itertools, pandas as pd, numpy as np
sys.path.insert(0, ".")
from multiprocessing import Pool
from goldbot import strategies as st
from goldbot.data import resample
from goldbot.engine import run, metrics
BPS = dict(XAU_USD=2.6, XAG_USD=8, WTICO_USD=6, XCU_USD=10, SPX500_USD=1.5, NAS100_USD=2, DE30_EUR=2, JP225_USD=3,
           EUR_USD=1.2, USD_JPY=1.5, GBP_USD=1.8, AUD_USD=1.8)
def load(m):
    h = pd.read_csv(f"./data/{m.lower()}_oanda_1h.csv.gz", index_col=0); h.index = pd.to_datetime(h.index, utc=True); return h
def job(a):
    m, tf, n, ex, stop = a
    df = resample(load(m), tf)
    t, _, _ = run(df, st.signals("donchian_breakout", df, dict(n=n, exit_n=ex)), stop, 0, True,
                  {"cost_bps": BPS[m], "overnight_funding_pct": 0.0326}, tf)
    t["mkt"] = m; t["cfg"] = f"{tf} {n}/{ex} stop{stop}"
    return t[["mkt", "cfg", "entry_time", "exit_time", "direction", "r"]]
if __name__ == "__main__":
    cfgs = [("1d", 20, 10, 2.0), ("1d", 55, 20, 2.0), ("1d", 55, 20, 3.0), ("4h", 55, 20, 2.0), ("4h", 90, 30, 2.0)]
    jobs = [(m, *c) for m in BPS for c in cfgs]
    with Pool() as p: T = pd.concat(p.map(job, jobs))
    T["entry_time"] = pd.to_datetime(T.entry_time, utc=True); T["exit_time"] = pd.to_datetime(T.exit_time, utc=True)
    T.to_pickle("research/multi.pkl")
    pd.set_option("display.width", 230)
    print("Total R per market (12 years), fixed rules, no tuning:")
    print(T.pivot_table(index="mkt", columns="cfg", values="r", aggfunc="sum").round(1))
    print("\nPORTFOLIO (all 12 markets, equal risk per trade):")
    for cfg, x in T.groupby("cfg"):
        x = x.sort_values("exit_time"); eq = x.r.cumsum(); dd = (eq.cummax().clip(lower=0) - eq).max()
        yr = x.r.groupby(x.exit_time.dt.year).sum()
        # max concurrent open positions
        ev = pd.concat([pd.Series(1, x.entry_time), pd.Series(-1, x.exit_time)]).sort_index().cumsum()
        print(f"{cfg:18s} trades {len(x):4d}  win {(x.r>0).mean():.0%}  total {x.r.sum():6.1f}R  per yr {x.r.sum()/11.9:5.1f}R  maxDD {dd:5.1f}R  "
              f"ret/DD {x.r.sum()/dd:4.1f}  pos years {(yr>0).sum()}/{len(yr)}  max open {int(ev.max())}  markets profitable {(x.groupby('mkt').r.sum()>0).sum()}/12")
    x = T[T.cfg == "1d 55/20 stop2.0"]; print("\nBy year, 1d 55/20 stop2 portfolio:", x.r.groupby(x.exit_time.dt.year).sum().round(1).to_dict())
