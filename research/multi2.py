import sys, pandas as pd
sys.path.insert(0, "."); sys.path.insert(0, "research")
from multiprocessing import Pool
from multi import BPS, load
from goldbot import strategies as st
from goldbot.data import resample
from goldbot.engine import run
def job(a):
    m, label, bps, fund = a
    df = resample(load(m), "1d")
    t, _, _ = run(df, st.signals("donchian_breakout", df, dict(n=55, exit_n=20)), 2.0, 0, True,
                  {"cost_bps": bps, "overnight_funding_pct": fund}, "1d")
    hold = (pd.to_datetime(t.exit_time) - pd.to_datetime(t.entry_time)).dt.days.mean()
    return dict(mkt=m, case=label, R=round(t.r.sum(), 1), hold_days=round(hold, 1))
if __name__ == "__main__":
    jobs = [(m, l, b, f) for m in BPS for (l, b, f) in [("1 gross (no costs)", 0, 0), ("2 spread only", BPS[m], 0),
                                                         ("3 spread + 0.01%/night", BPS[m], 0.01), ("4 spread + 0.0326%/night", BPS[m], 0.0326)]]
    with Pool() as p: d = pd.DataFrame(p.map(job, jobs))
    pd.set_option("display.width", 200)
    t = d.pivot(index="mkt", columns="case", values="R"); t["avg hold days"] = d.groupby("mkt").hold_days.first()
    t.loc["PORTFOLIO"] = t.sum(); print(t.round(1).to_string())
