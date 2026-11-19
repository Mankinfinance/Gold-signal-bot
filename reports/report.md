# Gold strategy research report

Generated 2026-11-19 20:18 UTC from 2024-06-30 to 2026-11-19 (13674 hourly bars).

All numbers are OUT OF SAMPLE (months the selection never saw), after spread,
slippage and overnight funding. 1R = the amount risked on one trade.

## Verdict

**LIVE: signals ON**


Current champion: `1h:ema_cross` with `{"fast": 20, "slow": 100, "adx_min": 20, "stop_atr": 2.0, "rr": 0, "trail": true}`

## Adaptive selection (what the bot would actually have done)

| trades | win rate | profit factor | avg R | total R | max drawdown R |
|---|---|---|---|---|---|
| 122 | 31% | 1.41 | 0.259 | 31.61 | 14.33 |

## Each strategy on its own (best params re-picked monthly)

| strategy | trades | win rate | PF | total R | max DD R |
|---|---|---|---|---|---|
| 1h:macd_trend | 413 | 36% | 1.4 | 61.96 | 11.2 |
| 1h:ema_cross | 95 | 26% | 1.56 | 33.68 | 8.56 |
| 4h:supertrend_flip | 68 | 46% | 1.98 | 25.03 | 5.55 |
| 4h:macd_trend | 108 | 41% | 1.52 | 18.95 | 7.71 |
| 1h:donchian_breakout | 209 | 38% | 1.16 | 17.62 | 16.63 |
| 1h:bb_fade | 82 | 62% | 1.24 | 6.62 | 5.93 |
| 4h:rsi_pullback | 102 | 70% | 1.19 | 4.94 | 6.34 |
| 4h:donchian_breakout | 56 | 34% | 1.11 | 3.11 | 9.08 |
| 4h:ema_cross | 70 | 29% | 1.07 | 2.54 | 12.2 |
| 4h:bb_fade | 18 | 50% | 0.67 | -2.41 | 3.37 |
| 1h:supertrend_flip | 278 | 31% | 0.88 | -17.83 | 28.65 |
| 1h:rsi_pullback | 483 | 59% | 0.85 | -18.27 | 22.92 |

## Month by month

| test month | picked | OOS R |
|---|---|---|
| 2025-01-02 | 1h:supertrend_flip | 5.76 |
| 2025-02-02 | 1h:ema_cross | -3.48 |
| 2025-03-02 | 1h:ema_cross | 7.69 |
| 2025-04-02 | 1h:ema_cross | -2.98 |
| 2025-05-02 | 1h:supertrend_flip | -5.37 |
| 2025-06-02 | 1h:supertrend_flip | -1.93 |
| 2025-07-02 | 1h:ema_cross | 5.25 |
| 2025-08-02 | 1h:ema_cross | 1.79 |
| 2025-09-02 | 1h:ema_cross | -2.81 |
| 2025-10-02 | 1h:ema_cross | 3.61 |
| 2025-11-02 | 1h:ema_cross | -1.02 |
| 2025-12-02 | 1h:ema_cross | -2.03 |
| 2026-01-02 | 1h:ema_cross | 14.96 |
| 2026-02-02 | 1h:ema_cross | -2.1 |
| 2026-03-02 | 1h:ema_cross | 12.35 |
| 2026-04-02 | 1h:ema_cross | 0.0 |
| 2026-05-02 | 1h:ema_cross | -1.15 |
| 2026-06-02 | 1h:ema_cross | 2.52 |
| 2026-07-02 | 1h:ema_cross | -5.01 |
| 2026-08-02 | 4h:supertrend_flip | 2.92 |
| 2026-09-02 | 1h:ema_cross | -2.33 |
| 2026-10-02 | 1h:ema_cross | 4.2 |
| 2026-11-02 | 1h:ema_cross | 0.77 |
