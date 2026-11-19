"""Scheduled signal run. Works out what the champion strategy wants to hold right
now, compares it with what it last told you, and alerts only on changes:
ENTER, EXIT, FLIP, or MOVE STOP.

It also keeps a paper ledger of every signalled trade (state/ledger.csv) and
switches itself off if live results draw down more than the kill switch allows.
"""
import json
import math
from datetime import datetime, timezone

import pandas as pd

from . import ROOT, load_config
from . import strategies as st
from .data import TF_HOURS, drop_incomplete, fetch_hourly, fetch_last_price, resample
from .engine import run, metrics
from .notify import send
from . import oanda

STATE = ROOT / "state"
LIVE = STATE / "live.json"
LEDGER = STATE / "ledger.csv"


def _load(path, default):
    return json.loads(path.read_text()) if path.exists() else default


def size_position(cfg, stop_usd, price, audusd):
    p = cfg["plus500"]
    risk_aud = cfg["account_balance_aud"] * cfg["risk_pct_per_trade"] / 100
    oz = risk_aud * audusd / stop_usd
    max_oz = (cfg["account_balance_aud"] * cfg["max_margin_pct_of_balance"] / 100
              * audusd) / (price * p["initial_margin_pct"] / 100)
    oz = min(oz, max_oz)
    units = math.floor(oz / p["unit_oz"])
    oz = round(units * p["unit_oz"], 2)
    margin_aud = oz * price * p["initial_margin_pct"] / 100 / audusd
    return oz, units, oz * stop_usd / audusd, margin_aud


def desired_position(df, champ, cfg):
    """Replay the strategy and apply any decision made at the latest close."""
    p, tf = champ["params"], champ["tf"]
    sig_p = {k: v for k, v in p.items() if k not in ("stop_atr", "rr", "trail")}
    sigs = st.signals(champ["family"], df, sig_p)
    trades, pos, pending = run(df, sigs, p["stop_atr"], p["rr"], p["trail"],
                               cfg["plus500"], tf)
    from .indicators import atr
    last_close, last_atr = float(df.close.iloc[-1]), float(atr(df).iloc[-1])
    signal_bar = str(df.index[-1])
    if pending in (1, -1) and (pos is None or pos["direction"] == -pending):
        risk = p["stop_atr"] * last_atr
        d = pending
        pos = dict(direction=d, entry_time=f"after {signal_bar}", entry=last_close,
                   stop=last_close - d * risk,
                   target=last_close + d * p["rr"] * risk if p["rr"] else None,
                   risk=risk, new=True)
    elif pending == 2:
        pos = None
    return pos, trades


def fmt_dir(d):
    return "BUY (long)" if d == 1 else "SELL (short)"


def entry_msg(pos, champ, cfg, audusd, price):
    oz, units, risk_aud, margin = size_position(cfg, pos["risk"], price, audusd)
    side = "BELOW" if pos["direction"] == 1 else "ABOVE"
    tside = "ABOVE" if pos["direction"] == 1 else "BELOW"
    lines = [f"Open {fmt_dir(pos['direction'])} on Plus500 Gold now.",
             f"Size: {oz} oz ({units} units of 0.15 oz)",
             f"Stop loss: ${pos['risk']:.2f} {side} your fill price",
             f"Take profit: ${pos['risk'] * champ['params']['rr']:.2f} {tside} your fill"
             if pos["target"] else "Take profit: none, the bot will trail the stop and tell you when to exit",
             f"Risk: about AU${risk_aud:,.0f} ({cfg['risk_pct_per_trade']}% of balance)",
             f"Margin: about AU${margin:,.0f}",
             f"Reference price (futures): {pos['entry']:,.2f}",
             f"Strategy: {champ['tf']} {champ['family']}"]
    return "\n".join(lines)


def auto_trade(cfg, desired):
    """Phase 2: mirror the position on OANDA if enabled. Never crashes the alerts."""
    try:
        broker = oanda.from_env(cfg)
        if broker:
            print("OANDA:", oanda.sync(broker, desired, cfg, send))
    except Exception as e:
        send("AUTO-TRADE ERROR", f"{e}\nCheck your OANDA account manually.", "urgent", "warning")


def main(now=None, hourly=None, quiet_unchanged=True):
    cfg = load_config()
    champ_file = _load(STATE / "champion.json", {"enabled": False, "reasons": ["research not run yet"]})
    live = _load(LIVE, {"position": None, "paused": False, "last_bar": None})

    at = cfg.get("auto_trade", {})
    alerts_on = bool(champ_file.get("enabled")) and not live.get("paused")
    # Demo account may trade a champion that narrowly failed the gates, to build
    # a live track record with practice money. Never applies to a live account.
    demo_on = (at.get("enabled") and at.get("environment") == "practice"
               and at.get("demo_trades_when_gates_fail") and champ_file.get("champion")
               and not live.get("paused"))

    if not alerts_on and live.get("position"):
        send("GOLD: close your bot position",
             "Plus500 signals are now OFF ("
             + "; ".join(champ_file.get("reasons") or ["kill switch"]) +
             "). Close the position the bot opened.", "high", "warning")
        live["position"] = None
        LIVE.write_text(json.dumps(live, indent=2))
    if not alerts_on and not demo_on:
        auto_trade(cfg, None)
        print("Signals off:", champ_file.get("reasons"), "paused" if live.get("paused") else "")
        return
    if not alerts_on:
        print("Plus500 alerts OFF (gates failed); OANDA demo still trading.")

    champ = champ_file["champion"]
    tf = champ["tf"]
    hourly = fetch_hourly(cfg["symbol"], period="120d") if hourly is None else hourly
    df = drop_incomplete(resample(hourly, tf), tf, now)
    last_bar = str(df.index[-1])
    if live.get("last_bar") == last_bar and quiet_unchanged:
        print("No new closed bar since last run.")
        return
    if (now or datetime.now(timezone.utc)) - df.index[-1] > pd.Timedelta(hours=TF_HOURS[tf] + 3):
        print("Market closed or data stale, nothing to do.")
        return

    pos, trades = desired_position(df, champ, cfg)
    old = live.get("position")
    price = float(df.close.iloc[-1])
    try:
        audusd = fetch_last_price(cfg["fx_symbol"])
    except Exception:
        audusd = 0.65

    # paper ledger: trades the engine closed since the last processed bar
    if live.get("last_bar") and len(trades):
        new = trades[pd.to_datetime(trades.exit_time, utc=True) > pd.Timestamp(live["last_bar"])]
        if len(new):
            new = new.assign(strategy=f"{tf}:{champ['family']}")
            new.to_csv(LEDGER, mode="a", header=not LEDGER.exists(), index=False)

    engine_pos = dict(pos) if pos else None  # before any display adjustments
    if not alerts_on:
        auto_trade(cfg, engine_pos)
        live.update(position=None, last_bar=last_bar)
        LIVE.write_text(json.dumps(live, indent=2, default=str))
        return
    if pos and not old and not pos.get("new"):
        pos = None  # alerts just switched on mid-trade: never alert a late entry
    same = (old and pos and old["direction"] == pos["direction"]
            and (pos.get("new") is None))
    if old and not pos:
        send("GOLD: EXIT now", f"Close your {fmt_dir(old['direction'])} gold position.\n"
             f"Reference price (futures): {price:,.2f}\nStrategy: {tf} {champ['family']}",
             "high", "checkered_flag")
    elif pos and not old:
        send(f"GOLD: {fmt_dir(pos['direction'])}", entry_msg(pos, champ, cfg, audusd, price),
             "high", "chart_with_upwards_trend" if pos["direction"] == 1
             else "chart_with_downwards_trend")
    elif pos and old and not same:
        send(f"GOLD: FLIP to {fmt_dir(pos['direction'])}",
             f"Close your {fmt_dir(old['direction'])} first, then:\n\n"
             + entry_msg(pos, champ, cfg, audusd, price), "high", "repeat")
    elif same and abs(pos["stop"] - old["stop"]) >= 0.25 * pos["risk"]:
        moved = pos["stop"] - old["stop"]
        locked = pos["direction"] * (pos["stop"] - pos["entry"])
        send("GOLD: move your stop",
             f"Move your stop loss {'up' if moved > 0 else 'down'} by ${abs(moved):.2f}.\n"
             + (f"This locks in about ${locked:.2f}/oz of profit." if locked > 0
                else f"Your stop is now ${-locked:.2f}/oz from break-even."), "default", "lock")
    else:
        print("No change. Holding:" if pos else "No change. Flat.", pos)
        if pos and old:
            pos["stop"] = old["stop"]  # keep the last stop we told you about

    auto_trade(cfg, engine_pos)
    if pos:
        pos.pop("new", None)
    live.update(position=pos, last_bar=last_bar)

    # kill switch on live paper results
    if LEDGER.exists():
        led = pd.read_csv(LEDGER)
        m = metrics(led.r)
        if m["max_dd_r"] > cfg["live_gates"]["kill_switch_live_drawdown_r"]:
            live["paused"] = True
            send("GOLD BOT PAUSED", f"Live drawdown hit {m['max_dd_r']}R. Signals stopped until "
                 "you reset it (delete state/ledger.csv and set paused to false).", "urgent", "rotating_light")
    LIVE.write_text(json.dumps(live, indent=2, default=str))


if __name__ == "__main__":
    main()
