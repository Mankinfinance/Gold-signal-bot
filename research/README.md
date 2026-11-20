# Research scripts (run from the repo root)

| Script | Question | Result (Nov 2026) |
|---|---|---|
| `robust.py` | Is gold Donchian breakout robust across 168 settings, 4h and daily, 2015-2026? | Yes on gold: 92% (4h) and 83% (daily) of settings profitable; daily 55/20, 2 ATR trail: +33R, DD 3.3R |
| `multi.py` | Do the same fixed rules work on 12 OANDA markets? | No: only gold profitable; portfolio -150R with 0.0326%/night funding |
| `multi2.py` | Gross vs spread vs funding per market | Gross portfolio +36.9R, of which gold +48.6R; other 11 markets -11.7R before any costs |

Gold's profit came from long trades during the 2015-2026 bull market (daily longs +36.5R, shorts -3.3R).
