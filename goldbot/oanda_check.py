"""Read-only: find out whether the OANDA token is for demo or live, and list
the accounts it can see with their balances. Never places orders."""
import os

import requests

from .oanda import HOSTS

tok = os.environ["OANDA_TOKEN"]
for env, host in HOSTS.items():
    r = requests.get(f"{host}/v3/accounts", headers={"Authorization": f"Bearer {tok}"}, timeout=20)
    print(f"{env}: HTTP {r.status_code}")
    if r.ok:
        for a in r.json()["accounts"]:
            s = requests.get(f"{host}/v3/accounts/{a['id']}/summary",
                             headers={"Authorization": f"Bearer {tok}"}, timeout=20).json()["account"]
            print(f"  account {a['id']}  currency {s['currency']}  NAV {s['NAV']}  "
                  f"hedging {s.get('hedgingEnabled')}  matches secret: {a['id'] == os.getenv('OANDA_ACCOUNT_ID', '').strip()}")
