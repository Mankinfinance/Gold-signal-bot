"""Market data: hourly gold bars from Yahoo Finance, resampled as needed.

GC=F is COMEX gold futures. It tracks Plus500's XAU price closely but sits a few
dollars away (futures basis), so signals report stop and target as DISTANCES
from your fill rather than absolute levels.
"""
from datetime import datetime, timezone

import pandas as pd

TF_HOURS = {"1h": 1, "4h": 4}


def fetch_hourly(symbol="GC=F", period="730d"):
    import yfinance as yf

    df = yf.download(symbol, period=period, interval="1h", auto_adjust=False,
                     progress=False, multi_level_index=False)
    if df is None or df.empty:
        raise RuntimeError(f"No data returned for {symbol}")
    df = df.rename(columns=str.lower)[["open", "high", "low", "close"]].dropna()
    idx = df.index
    df.index = idx.tz_localize("UTC") if idx.tz is None else idx.tz_convert("UTC")
    return df[~df.index.duplicated(keep="last")].sort_index()


def fetch_last_price(symbol):
    import yfinance as yf

    df = yf.download(symbol, period="5d", interval="1h", progress=False,
                     multi_level_index=False)
    return float(df["Close"].dropna().iloc[-1])


def resample(df, tf):
    if tf == "1h":
        return df
    rule = f"{TF_HOURS[tf]}h"
    out = df.resample(rule, origin="epoch").agg(
        {"open": "first", "high": "max", "low": "min", "close": "last"})
    return out.dropna()


def drop_incomplete(df, tf, now=None):
    """Remove the bar still forming, so signals only use closed bars."""
    now = now or datetime.now(timezone.utc)
    end = df.index[-1] + pd.Timedelta(hours=TF_HOURS[tf])
    return df.iloc[:-1] if end > now else df
