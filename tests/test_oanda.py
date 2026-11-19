"""OANDA sync logic against a fake broker (no network)."""
import pytest

from goldbot import oanda

CFG = {"auto_trade": {"enabled": True, "environment": "practice",
                      "risk_pct_per_trade": 1.0, "max_units": 10}}


class FakeBroker:
    env = "practice"

    def __init__(self, trades=(), nav=3595, prec=0, min_size=1):
        self.trades = list(trades)
        self.nav, self.prec, self.min_size = nav, prec, min_size
        self.calls = []

    def bot_trades(self):
        return self.trades

    def summary(self):
        return {"NAV": str(self.nav), "currency": "AUD"}

    def instrument(self):
        return {"tradeUnitsPrecision": self.prec, "minimumTradeSize": str(self.min_size)}

    def mid(self, _):
        return 0.65

    def market(self, units, dist):
        self.calls.append(("market", units, dist))
        self.trades = [{"id": "9", "currentUnits": str(units), "price": "3670.00",
                        "stopLossOrder": {"price": str(3670 - (1 if units > 0 else -1) * dist)}}]
        return {"price": "3670.00"}

    def close(self, tid):
        self.calls.append(("close", tid))

    def set_stop(self, tid, price):
        self.calls.append(("stop", tid, round(price, 2)))


def short(new=True, entry=3700.0, stop=3720.0):
    return dict(direction=-1, entry=entry, stop=stop, risk=20.0, new=new)


def noop(*a, **k):
    pass


def test_opens_fresh_signal_with_broker_stop():
    b = FakeBroker(nav=100000, prec=1)
    assert oanda.sync(b, short(), CFG, noop) == "opened"
    kind, units, dist = b.calls[0]
    assert kind == "market" and units < 0 and dist == 20.0
    assert units == pytest.approx(-10)  # capped at max_units


def test_does_not_open_late():
    b = FakeBroker()
    assert "old" in oanda.sync(b, short(new=False), CFG, noop)
    assert b.calls == []


def test_small_account_skips_instead_of_oversizing():
    b = FakeBroker(nav=3595, prec=0, min_size=1)  # 1% = $23 risk, $20 stop -> 1.17 oz -> 1
    assert oanda.sync(b, short(), CFG, noop) == "opened"
    b = FakeBroker(nav=1000, prec=0, min_size=1)  # 0.32 oz -> below minimum
    assert oanda.sync(b, short(), CFG, noop) == "too small"


def test_flip_closes_then_opens():
    b = FakeBroker(trades=[{"id": "1", "currentUnits": "2", "price": "3650"}], nav=100000, prec=1)
    oanda.sync(b, short(), CFG, noop)
    assert b.calls[0] == ("close", "1") and b.calls[1][0] == "market"


def test_exit_closes():
    b = FakeBroker(trades=[{"id": "1", "currentUnits": "-2", "price": "3650"}])
    oanda.sync(b, None, CFG, noop)
    assert b.calls == [("close", "1")]


def test_trailing_stop_only_tightens():
    t = {"id": "1", "currentUnits": "-2", "price": "3650.00", "stopLossOrder": {"price": "3670.00"}}
    b = FakeBroker(trades=[t])
    # strategy stop now 5 above entry -> OANDA stop 3655, tighter than 3670
    oanda.sync(b, short(new=False, entry=3700, stop=3705), CFG, noop)
    assert b.calls == [("stop", "1", 3655.0)]
    b = FakeBroker(trades=[t])
    oanda.sync(b, short(new=False, entry=3700, stop=3730), CFG, noop)  # looser: ignore
    assert b.calls == []


def test_disabled_without_secrets(monkeypatch):
    monkeypatch.delenv("OANDA_TOKEN", raising=False)
    assert oanda.from_env(CFG) is None
    assert oanda.from_env({"auto_trade": {"enabled": False}}) is None
