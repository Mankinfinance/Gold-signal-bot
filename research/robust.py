import sys, itertools, pandas as pd, numpy as np
sys.path.insert(0, ".")
from multiprocessing import Pool
from goldbot import strategies as st
from goldbot.data import resample
from goldbot.engine import run, metrics
h = pd.read_csv("./data/xau_usd_oanda_1h.csv.gz", index_col=0); h.index = pd.to_datetime(h.index, utc=True)
DF = {tf: resample(h, tf) for tf in ("4h", "1d")}
COST = {"cost_bps": 2.6, "overnight_funding_pct": 0.0326}
def job(a):
    tf, n, ex, stop = a
    if ex >= n: return None
    df = DF[tf]; t, _, _ = run(df, st.signals("donchian_breakout", df, dict(n=n, exit_n=ex)), stop, 0, True, COST, tf)
    y = pd.to_datetime(t.exit_time, utc=True).dt.year; yr = t.r.groupby(y).sum()
    m = metrics(t.r)
    return dict(tf=tf, n=n, exit=ex, stop=stop, trades=m["trades"], win=m["win_rate"], pf=m["profit_factor"], tot=m["total_r"], dd=m["max_dd_r"], pos_yrs=int((yr > 0).sum()), yrs=len(yr),
                pre2023=round(t.r[y < 2023].sum(), 1), post2023=round(t.r[y >= 2023].sum(), 1))
if __name__ == "__main__":
    jobs = list(itertools.product(["4h", "1d"], [20, 30, 40, 55, 70, 90, 120], [10, 20, 30, 40], [2.0, 3.0, 4.0]))
    with Pool() as p: res = [r for r in p.map(job, jobs) if r]
    d = pd.DataFrame(res); d.to_pickle("research/robust.pkl")
    pd.set_option("display.width", 200)
    for tf in ("4h", "1d"):
        x = d[d.tf == tf]
        print(f"\n{tf}: {len(x)} settings, {(x.tot > 0).mean():.0%} profitable over 12y, median {x.tot.median():.1f}R, "
              f"profitable BOTH pre-2023 and 2023+: {((x.pre2023 > 0) & (x.post2023 > 0)).mean():.0%}")
        print("median total R by entry lookback n x stop:"); print(x.pivot_table(index="n", columns="stop", values="tot", aggfunc="median").round(1))
    print("\nTop 8 by return/drawdown:"); d["ratio"] = d.tot / d.dd.clip(lower=1)
    print(d.sort_values("ratio", ascending=False).head(8).to_string(index=False))
