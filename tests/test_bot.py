"""Mechanical tests on synthetic prices. These check the code is correct, they
say nothing about whether any strategy makes money."""
import json

import numpy as np
import pandas as pd
import pytest

import goldbot
from goldbot import engine, live, research
from goldbot import strategies as st

COSTS = dict(spread_usd=0.66, slippage_usd=0.3, overnight_funding_pct=0.0326)


def synth(n=24 * 400, seed=1):
    rng = np.random.default_rng(seed)
    idx = pd.date_range("2025-01-01", periods=n, freq="1h", tz="UTC")
    drift = np.repeat(rng.normal(0, 0.4, n // 500 + 1), 500)[:n]
    c = 3000 + np.cumsum(drift + rng.normal(0, 4, n))
    o = np.r_[c[0], c[:-1]]
    h = np.maximum(o, c) + rng.uniform(0, 3, n)
    l = np.minimum(o, c) - rng.uniform(0, 3, n)
    return pd.DataFrame(dict(open=o, high=h, low=l, close=c), index=idx)


def bars(rows):
    idx = pd.date_range("2025-01-06 00:00", periods=len(rows), freq="1h", tz="UTC")
    return pd.DataFrame(rows, columns=["open", "high", "low", "close"], index=idx)


def flags(n, at):
    s = pd.Series(False, index=range(n))
    for i in at:
        s[i] = True
    return s


def test_long_hits_target_next_bar_fill():
    # 20 quiet bars so ATR exists, then a long signal and a rally
    rows = [(100, 101, 99, 100)] * 20 + [(100, 101, 99, 100), (100, 106, 100, 105)]
    df = bars(rows)
    n = len(df)
    sigs = [flags(n, [19]), flags(n, []), flags(n, []), flags(n, [])]
    sigs = [s.set_axis(df.index) for s in sigs]
    t, pos, _ = engine.run(df, sigs, stop_atr=1.0, rr=2.0, trail=False, costs=COSTS)
    assert len(t) == 1
    tr = t.iloc[0]
    assert tr.entry == 100  # filled at next open, not signal close
    assert tr.reason == "target"
    assert tr.r == pytest.approx((4 - 0.96) / 2, rel=1e-3)  # ATR=2 so risk=2, target=+4


def test_stop_wins_when_both_touched_and_gap_fills_worse():
    rows = [(100, 101, 99, 100)] * 20 + [(100, 101, 99, 100), (100, 110, 90, 100)]
    df = bars(rows)
    n = len(df)
    sigs = [s.set_axis(df.index) for s in
            [flags(n, [19]), flags(n, []), flags(n, []), flags(n, [])]]
    t, _, _ = engine.run(df, sigs, 1.0, 2.0, False, COSTS)
    assert t.iloc[0].reason == "stop"
    rows = [(100, 101, 99, 100)] * 21 + [(90, 91, 89, 90)]
    df = bars(rows)
    t, _, _ = engine.run(df, sigs, 1.0, 2.0, False, COSTS)
    assert t.iloc[0].reason == "stop_gap" and t.iloc[0].exit == 90


def test_signals_are_causal():
    df = synth(3000)
    for fam, (_, grid) in st.FAMILIES.items():
        p = {k: v for k, v in grid[0].items() if k not in ("stop_atr", "rr", "trail")}
        full = st.signals(fam, df, p)
        cut = st.signals(fam, df.iloc[:2000], p)
        for a, b in zip(full, cut):
            assert (a.iloc[:2000] == b).all(), fam


def test_research_and_live_end_to_end(tmp_path, monkeypatch):
    monkeypatch.setattr(goldbot, "ROOT", tmp_path)
    monkeypatch.setattr(research, "ROOT", tmp_path)
    monkeypatch.setattr(live, "STATE", tmp_path / "state")
    monkeypatch.setattr(live, "LIVE", tmp_path / "state" / "live.json")
    monkeypatch.setattr(live, "LEDGER", tmp_path / "state" / "ledger.csv")
    monkeypatch.setattr(live, "fetch_last_price", lambda s: 0.65)
    (tmp_path / "config.json").write_text(
        (goldbot.Path(__file__).resolve().parent.parent / "config.json").read_text())
    df = synth()
    out = research.main(hourly=df, log=lambda *a: None)
    assert (tmp_path / "reports" / "report.md").exists()
    # force a champion on so the live path is exercised regardless of verdict
    out["enabled"] = True
    out["champion"] = dict(tf="1h", family="supertrend_flip",
                           params=st.FAMILIES["supertrend_flip"][1][0])
    (tmp_path / "state" / "champion.json").write_text(json.dumps(out))
    sent = []
    monkeypatch.setattr(live, "send", lambda *a, **k: sent.append(a[0]))
    for end in range(len(df) - 300, len(df), 1):
        sub = df.iloc[:end]
        live.main(now=sub.index[-1] + pd.Timedelta(minutes=62), hourly=sub)
    assert any("BUY" in s or "SELL" in s or "FLIP" in s for s in sent)
    assert any("EXIT" in s or "FLIP" in s or "stop" in s for s in sent)


def test_sizing_respects_units_and_risk():
    cfg = goldbot.load_config()
    oz, units, risk_aud, margin = live.size_position(cfg, stop_usd=30, price=3670, audusd=0.65)
    assert oz == pytest.approx(units * 0.15)
    assert risk_aud <= cfg["account_balance_aud"] * cfg["risk_pct_per_trade"] / 100 + 1e-6


def test_demo_trades_but_no_alerts_when_gates_fail(tmp_path, monkeypatch):
    for mod in (goldbot,):
        monkeypatch.setattr(mod, "ROOT", tmp_path)
    monkeypatch.setattr(live, "STATE", tmp_path / "state")
    monkeypatch.setattr(live, "LIVE", tmp_path / "state" / "live.json")
    monkeypatch.setattr(live, "LEDGER", tmp_path / "state" / "ledger.csv")
    monkeypatch.setattr(live, "fetch_last_price", lambda s: 0.65)
    cfg = json.loads((goldbot.Path(__file__).resolve().parent.parent / "config.json").read_text())
    cfg["auto_trade"].update(enabled=True, environment="practice", demo_trades_when_gates_fail=True)
    (tmp_path / "config.json").write_text(json.dumps(cfg))
    (tmp_path / "state").mkdir()
    (tmp_path / "state" / "champion.json").write_text(json.dumps(dict(
        enabled=False, reasons=["drawdown"], champion=dict(
            tf="1h", family="supertrend_flip", params=st.FAMILIES["supertrend_flip"][1][0]))))
    sent, synced = [], []
    monkeypatch.setattr(live, "send", lambda *a, **k: sent.append(a[0]))
    monkeypatch.setattr(live, "auto_trade", lambda c, d: synced.append(d))
    df = synth()
    for end in range(len(df) - 200, len(df)):
        sub = df.iloc[:end]
        live.main(now=sub.index[-1] + pd.Timedelta(minutes=62), hourly=sub)
    assert sent == []                      # no Plus500 alerts
    assert any(d is not None for d in synced)  # but demo got positions to mirror
    # live account must never trade ungated
    cfg["auto_trade"]["environment"] = "live"
    (tmp_path / "config.json").write_text(json.dumps(cfg))
    synced.clear()
    live.main(now=df.index[-1] + pd.Timedelta(minutes=62), hourly=df)
    assert all(d is None for d in synced)


def test_scale_out_banks_half_then_breakeven():
    # ATR=2 -> risk 2. Bar 21 rallies to +1R (102), bar 22 falls back to entry.
    rows = [(100, 101, 99, 100)] * 21 + [(100, 102.5, 100, 102), (102, 102, 99.5, 100)]
    df = bars(rows)
    n = len(df)
    sigs = [s.set_axis(df.index) for s in
            [flags(n, [19]), flags(n, []), flags(n, []), flags(n, [])]]
    t, _, _ = engine.run(df, sigs, 1.0, 0, False, {**COSTS, "overnight_funding_pct": 0}, partial_r=1.0)
    assert len(t) == 1 and t.iloc[0].reason == "stop" and t.iloc[0].exit == 100
    assert t.iloc[0].r == pytest.approx((0.5 * 2 - 0.96) / 2, rel=1e-3)
