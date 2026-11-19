"""Phase 2: mirror the bot's position automatically on an OANDA account.

Off unless config.json has auto_trade.enabled = true AND the secrets
OANDA_TOKEN and OANDA_ACCOUNT_ID are set. Starts on the practice (demo) server.

Rules:
- Only touches XAU_USD trades it opened itself (tagged "goldbot").
- Opens only on a FRESH signal, never late into an old one.
- Stop is attached to every order at the broker, so it holds even if the
  bot or GitHub goes down.
- Stop distances come from the strategy and are applied to OANDA's own fill,
  so the futures/spot price gap does not matter.
"""
import math
import os

import requests

HOSTS = {"practice": "https://api-fxpractice.oanda.com",
         "live": "https://api-fxtrade.oanda.com"}
INSTRUMENT = "XAU_USD"
TAG = "goldbot"


class Oanda:
    def __init__(self, token, account, environment="practice", session=None):
        if environment not in HOSTS:
            raise ValueError(f"environment must be one of {list(HOSTS)}")
        self.base = f"{HOSTS[environment]}/v3/accounts/{account}"
        self.env = environment
        self.s = session or requests.Session()
        self.s.headers.update({"Authorization": f"Bearer {token}",
                               "Content-Type": "application/json"})

    def _req(self, method, path, **kw):
        r = self.s.request(method, self.base + path, timeout=20, **kw)
        if r.status_code >= 400:
            raise RuntimeError(f"OANDA {method} {path} -> {r.status_code}: {r.text[:300]}")
        return r.json()

    def summary(self):
        return self._req("GET", "/summary")["account"]

    def instrument(self):
        return self._req("GET", "/instruments", params={"instruments": INSTRUMENT})["instruments"][0]

    def mid(self, instrument):
        p = self._req("GET", "/pricing", params={"instruments": instrument})["prices"][0]
        return (float(p["bids"][0]["price"]) + float(p["asks"][0]["price"])) / 2

    def bot_trades(self):
        trades = self._req("GET", "/openTrades")["trades"]
        return [t for t in trades if t["instrument"] == INSTRUMENT
                and t.get("clientExtensions", {}).get("tag") == TAG]

    def market(self, units, stop_distance):
        u = units if not float(units).is_integer() else int(units)
        body = {"order": {"type": "MARKET", "instrument": INSTRUMENT, "units": str(u),
                          "timeInForce": "FOK", "positionFill": "OPEN_ONLY",
                          "stopLossOnFill": {"distance": f"{stop_distance:.2f}"},
                          "tradeClientExtensions": {"tag": TAG, "comment": "gold signal bot"}}}
        out = self._req("POST", "/orders", json=body)
        fill = out.get("orderFillTransaction")
        if not fill:
            raise RuntimeError(f"Order not filled: {out.get('orderCancelTransaction', out)}")
        return fill

    def close(self, trade_id):
        return self._req("PUT", f"/trades/{trade_id}/close", json={"units": "ALL"})

    def set_stop(self, trade_id, price, decimals=2):
        return self._req("PUT", f"/trades/{trade_id}/orders",
                         json={"stopLoss": {"price": f"{price:.{decimals}f}"}})


def from_env(cfg):
    at = cfg.get("auto_trade", {})
    tok, acc = os.getenv("OANDA_TOKEN"), os.getenv("OANDA_ACCOUNT_ID")
    if not at.get("enabled") or not tok or not acc:
        return None
    return Oanda(tok, acc, at.get("environment", "practice"))


def size_units(nav, currency, audusd, risk_pct, stop_usd, inst, max_units):
    risk = nav * risk_pct / 100
    risk_usd = risk * audusd if currency == "AUD" else risk
    raw = min(risk_usd / stop_usd, max_units)
    prec = int(inst.get("tradeUnitsPrecision", 0))
    units = math.floor(raw * 10 ** prec) / 10 ** prec
    return units if units >= float(inst.get("minimumTradeSize", 1)) else 0


def sync(broker, desired, cfg, send):
    """Make the OANDA account match the bot's desired position. Returns a log string."""
    at = cfg["auto_trade"]
    label = f"OANDA {broker.env.upper()}"
    trades = broker.bot_trades()
    held = 0 if not trades else (1 if float(trades[0]["currentUnits"]) > 0 else -1)
    want = desired["direction"] if desired else 0

    if trades and held != want:
        for t in trades:
            broker.close(t["id"])
        send(f"AUTO {label}: closed {'long' if held == 1 else 'short'}",
             f"Closed {len(trades)} bot trade(s) on {label}.", "default", "robot")
        trades = []

    if want and not trades:
        if not desired.get("new"):
            return "holding signal is old, not opening late"
        acct, inst = broker.summary(), broker.instrument()
        cur = acct.get("currency", "AUD")
        audusd = broker.mid("AUD_USD") if cur == "AUD" else 1.0
        units = size_units(float(acct["NAV"]), cur, audusd, at["risk_pct_per_trade"],
                           desired["risk"], inst, at["max_units"])
        if not units:
            send(f"AUTO {label}: trade skipped",
                 f"Position size rounds below OANDA's minimum for {INSTRUMENT}. "
                 "Account too small for this stop at the configured risk.", "default", "warning")
            return "too small"
        fill = broker.market(units * want, desired["risk"])
        send(f"AUTO {label}: opened {'long' if want == 1 else 'short'}",
             f"{units} oz {INSTRUMENT} at {fill.get('price')}\n"
             f"Stop ${desired['risk']:.2f} away, set at the broker.", "high", "robot")
        return "opened"

    if want and trades:
        t = trades[0]
        offset = desired["stop"] - desired["entry"]   # strategy stop relative to entry
        target = float(t["price"]) + offset
        cur = float(t.get("stopLossOrder", {}).get("price", "nan"))
        better = (target > cur) if want == 1 else (target < cur)
        if math.isnan(cur) or (better and abs(target - cur) >= 0.5):
            broker.set_stop(t["id"], target)
            return f"stop moved to {target:.2f}"
    return "in sync"
