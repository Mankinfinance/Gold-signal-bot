# Gold vs silver pairs (stat arb): research result

Tested 2026-11-19 on hourly COMEX gold (GC=F) and silver (SI=F), Jun 2024 to Nov 2026,
with Plus500-style costs on both legs (gold spread 0.66, silver spread 0.035) and
overnight funding on both legs.

| | Result |
|---|---|
| Setups tested | 144 (1h and 4h; lookback 100/250/500; entry z 1.5/2.0/2.5; exit, stop and time-stop variants) |
| Profitable over the full period (no selection) | 0 of 144 |
| Walk-forward (6-month train, 1-month test) | 61 trades, 48% win rate, profit factor 0.55, -15.0R |
| Holdout Jun to Nov 2026 | 27 trades, -3.9R |

Verdict: not traded. The gold/silver spread trended for weeks at a time over this
period (silver rally, then gold crash) instead of reverting, and two-leg retail costs
are too high for the small reversions that did occur. Re-test with
`goldbot.pairs.backtest_all` if conditions change.
