"""Download long hourly history (mid prices) from OANDA. Read-only."""
import os
import sys

import pandas as pd
import requests

from .oanda import HOSTS


def candles(instrument, start="2015-01-01T00:00:00Z", gran="H1", env="practice"):
    tok = os.environ["OANDA_TOKEN"]
    url = f"{HOSTS[env]}/v3/instruments/{instrument}/candles"
    rows, frm = [], start
    while True:
        r = requests.get(url, headers={"Authorization": f"Bearer {tok}"}, timeout=30,
                         params={"granularity": gran, "price": "M", "from": frm, "count": 5000})
        r.raise_for_status()
        cs = [c for c in r.json()["candles"] if c["complete"]]
        if not cs:
            break
        rows += [(c["time"], *(float(c["mid"][k]) for k in "ohlc")) for c in cs]
        if len(cs) < 4999:
            break
        frm = cs[-1]["time"]
    df = pd.DataFrame(rows, columns=["Datetime", "open", "high", "low", "close"])
    df["Datetime"] = pd.to_datetime(df.Datetime)
    return df.drop_duplicates("Datetime").set_index("Datetime")


if __name__ == "__main__":
    # args: INSTRUMENT or INSTRUMENT:GRANULARITY:START, e.g. XAU_USD:D:2003-01-01
    for arg in sys.argv[1:] or ["XAU_USD"]:
        inst, gran, start = (arg.split(":") + ["H1", "2015-01-01"][len(arg.split(":")) - 1:])[:3]
        df = candles(inst, start=f"{start}T00:00:00Z", gran=gran)
        tag = "1h" if gran == "H1" else gran.lower()
        df.to_csv(f"data/{inst.lower()}_oanda_{tag}.csv.gz", compression="gzip")
        print(inst, gran, len(df), df.index[0], df.index[-1])
