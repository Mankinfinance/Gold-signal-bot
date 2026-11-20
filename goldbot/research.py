"""Walk-forward research: find which strategy (if any) has a real edge.

For every strategy family x parameter set x timeframe we backtest the full
history once. Then, rolling through time month by month:
  1. look only at the previous `train_months` of trades,
  2. pick the best parameter set per family, then the best family overall,
  3. record what that pick did in the NEXT month (data it never saw).
Stitching those unseen months together gives an honest out-of-sample (OOS)
track record of the whole selection process. If the best pick in a training
window has a negative score, the bot sits that month out.

The live champion is whatever the process picks from the most recent window,
and it is only switched on if the OOS record passes the gates in config.json.
"""
import json
from datetime import datetime, timezone

import pandas as pd

from . import ROOT, load_config
from . import strategies as st
from .data import fetch_hourly, resample
from .engine import run, metrics


def backtest_all(hourly, cfg, log=print):
    rows = []
    for tf in cfg["timeframes"]:
        df = resample(hourly, tf)
        families = st.PROFILES[cfg.get("strategy_profile", "max_profit")]
        for fam, (_, grid) in families.items():
            for p in grid:
                sig_p = {k: v for k, v in p.items() if k not in ("stop_atr", "rr", "trail")}
                sigs = st.signals(fam, df, sig_p)
                trades, _, _ = run(df, sigs, p["stop_atr"], p["rr"], p["trail"],
                                   cfg["plus500"], tf)
                trades["entry_time"] = pd.to_datetime(trades["entry_time"], utc=True)
                rows.append(dict(tf=tf, family=fam, params=p, trades=trades))
        log(f"backtested {tf}: {sum(r['tf'] == tf for r in rows)} configs")
    return rows


def _window(trades, start, end):
    m = (trades.entry_time >= start) & (trades.entry_time < end)
    return trades[m]


def pick(rows, start, end, min_trades, min_win=0.0):
    best_by_family = {}
    for i, row in enumerate(rows):
        t = _window(row["trades"], start, end)
        if len(t) < min_trades or (t.r > 0).mean() < min_win:
            continue
        s = metrics(t.r)["score"]
        key = (row["tf"], row["family"])
        if key not in best_by_family or s > best_by_family[key][0]:
            best_by_family[key] = (s, i)
    if not best_by_family:
        return None, best_by_family
    score, idx = max(best_by_family.values())
    return (idx if score > 0 else None), best_by_family


def walk_forward(rows, cfg):
    rc = cfg["research"]
    first = min(r["trades"].entry_time.min() for r in rows if len(r["trades"]))
    last = max(r["trades"].entry_time.max() for r in rows if len(r["trades"]))
    tr, te = pd.DateOffset(months=rc["train_months"]), pd.DateOffset(months=rc["test_months"])
    oos, windows, fam_oos = [], [], {}
    t0 = first.normalize()
    while t0 + tr < last:
        train_end, test_end = t0 + tr, t0 + tr + te
        idx, per_fam = pick(rows, t0, train_end, rc["min_train_trades"], rc.get("min_win_rate", 0))
        if idx is not None:
            t = _window(rows[idx]["trades"], train_end, test_end).copy()
            t["strategy"] = f'{rows[idx]["tf"]}:{rows[idx]["family"]}'
            oos.append(t)
        windows.append(dict(test_start=str(train_end.date()),
                            pick=None if idx is None else
                            f'{rows[idx]["tf"]}:{rows[idx]["family"]}',
                            params=None if idx is None else rows[idx]["params"],
                            oos_r=0 if idx is None else round(float(t.r.sum()), 2)))
        # also track each family on its own, for the report
        for key, (_, i) in per_fam.items():
            ft = _window(rows[i]["trades"], train_end, test_end)
            fam_oos.setdefault(f"{key[0]}:{key[1]}", []).append(ft)
        t0 += te
    oos_df = pd.concat(oos) if oos else pd.DataFrame(columns=["r"])
    fam_metrics = {k: metrics(pd.concat(v).r if v else []) for k, v in fam_oos.items()}
    final_idx, _ = pick(rows, last - tr, last + pd.Timedelta(days=1), rc["min_train_trades"],
                        rc.get("min_win_rate", 0))
    return oos_df, windows, fam_metrics, final_idx


def passes_gates(m, gates):
    reasons = []
    if m["trades"] < gates["min_oos_trades"]:
        reasons.append(f'only {m["trades"]} OOS trades (need {gates["min_oos_trades"]})')
    if m["profit_factor"] < gates["min_profit_factor"]:
        reasons.append(f'profit factor {m["profit_factor"]} < {gates["min_profit_factor"]}')
    if m["max_dd_r"] > gates["max_drawdown_r"]:
        reasons.append(f'drawdown {m["max_dd_r"]}R > {gates["max_drawdown_r"]}R')
    if m["win_rate"] < gates.get("min_win_rate", 0):
        reasons.append(f'win rate {m["win_rate"]:.0%} < {gates["min_win_rate"]:.0%}')
    if m["total_r"] <= 0:
        reasons.append("lost money out of sample")
    return not reasons, reasons


def write_report(oos_df, windows, fam_metrics, overall, ok, reasons, champion, hourly):
    rep = ROOT / "reports"
    rep.mkdir(exist_ok=True)
    oos_df.to_csv(rep / "oos_trades.csv", index=False)
    lines = [
        "# Gold strategy research report", "",
        f"Generated {datetime.now(timezone.utc):%Y-%m-%d %H:%M} UTC from "
        f"{hourly.index[0]:%Y-%m-%d} to {hourly.index[-1]:%Y-%m-%d} "
        f"({len(hourly)} hourly bars).", "",
        "All numbers are OUT OF SAMPLE (months the selection never saw), after spread,",
        "slippage and overnight funding. 1R = the amount risked on one trade.", "",
        "## Verdict", "",
        f"**{'LIVE: signals ON' if ok else 'NO PROVEN EDGE: signals OFF'}**", "",
    ]
    lines += [f"- {r}" for r in reasons]
    if champion:
        lines += ["", f"Current champion: `{champion['tf']}:{champion['family']}` "
                  f"with `{json.dumps(champion['params'])}`"]
    lines += ["", "## Adaptive selection (what the bot would actually have done)", "",
              "| trades | win rate | profit factor | avg R | total R | max drawdown R |",
              "|---|---|---|---|---|---|",
              f'| {overall["trades"]} | {overall["win_rate"]:.0%} | {overall["profit_factor"]}'
              f' | {overall["avg_r"]} | {overall["total_r"]} | {overall["max_dd_r"]} |', "",
              "## Each strategy on its own (best params re-picked monthly)", "",
              "| strategy | trades | win rate | PF | total R | max DD R |",
              "|---|---|---|---|---|---|"]
    for k, m in sorted(fam_metrics.items(), key=lambda kv: -kv[1]["total_r"]):
        lines.append(f'| {k} | {m["trades"]} | {m["win_rate"]:.0%} | {m["profit_factor"]}'
                     f' | {m["total_r"]} | {m["max_dd_r"]} |')
    lines += ["", "## Month by month", "", "| test month | picked | OOS R |", "|---|---|---|"]
    lines += [f'| {w["test_start"]} | {w["pick"] or "sat out"} | {w["oos_r"]} |'
              for w in windows]
    (rep / "report.md").write_text("\n".join(lines) + "\n")
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        if len(oos_df):
            s = oos_df.sort_values("exit_time")
            fig, ax = plt.subplots(figsize=(9, 4))
            ax.plot(pd.to_datetime(s.exit_time, utc=True), s.r.cumsum())
            ax.set_title("Out-of-sample equity (R)")
            ax.axhline(0, lw=0.5, color="grey")
            fig.tight_layout()
            fig.savefig(rep / "equity.png", dpi=120)
    except Exception as e:  # chart is optional
        print("chart skipped:", e)


def fixed_main(cfg, hourly, log=print):
    """A strategy pinned in config.json: no re-selection, just a fresh backtest
    summary. Plus500 alerts stay off unless fixed_champion.plus500_alerts is true;
    the OANDA practice account trades it (auto_trade.demo_trades_when_gates_fail)."""
    fc = cfg["fixed_champion"]
    df = resample(hourly, fc["tf"])
    sig_p = {k: v for k, v in fc["params"].items() if k not in ("stop_atr", "rr", "trail")}
    p = fc["params"]
    trades, _, _ = run(df, st.signals(fc["family"], df, sig_p), p["stop_atr"], p["rr"], p["trail"],
                       cfg["plus500"], fc["tf"])
    m = metrics(trades.r)
    on = bool(fc.get("plus500_alerts"))
    out = dict(updated=datetime.now(timezone.utc).isoformat(), enabled=on, fixed=True,
               reasons=[] if on else ["fixed demo strategy: Plus500 alerts off until the demo proves it"],
               champion=dict(tf=fc["tf"], family=fc["family"], params=fc["params"]),
               backtest_recent=m, why=fc.get("why", ""))
    (ROOT / "state").mkdir(exist_ok=True)
    (ROOT / "state" / "champion.json").write_text(json.dumps(out, indent=2))
    log(json.dumps(out, indent=2))
    return out


def main(hourly=None, log=print):
    cfg = load_config()
    if cfg.get("fixed_champion"):
        hourly = fetch_hourly(cfg["symbol"]) if hourly is None else hourly
        return fixed_main(cfg, hourly, log)
    hourly = fetch_hourly(cfg["symbol"]) if hourly is None else hourly
    rows = backtest_all(hourly, cfg, log)
    oos_df, windows, fam_metrics, final_idx = walk_forward(rows, cfg)
    overall = metrics(oos_df.r)
    ok, reasons = passes_gates(overall, cfg["live_gates"])
    champion = None
    if final_idx is not None:
        r = rows[final_idx]
        champion = dict(tf=r["tf"], family=r["family"], params=r["params"])
    elif ok:
        ok, reasons = False, ["no strategy scores positively in the latest window"]
    out = dict(updated=datetime.now(timezone.utc).isoformat(), enabled=ok,
               reasons=reasons, champion=champion, oos=overall)
    (ROOT / "state").mkdir(exist_ok=True)
    (ROOT / "state" / "champion.json").write_text(json.dumps(out, indent=2))
    write_report(oos_df, windows, fam_metrics, overall, ok, reasons, champion, hourly)
    log(json.dumps(out, indent=2))
    return out


if __name__ == "__main__":
    main()
