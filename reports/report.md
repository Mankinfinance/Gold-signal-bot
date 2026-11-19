# Gold strategy research report

Generated 2026-11-19 20:48 UTC from 2024-06-30 to 2026-11-19 (13737 hourly bars).

All numbers are OUT OF SAMPLE (months the selection never saw), after spread,
slippage and overnight funding. 1R = the amount risked on one trade.

## Verdict

**NO PROVEN EDGE: signals OFF**

- drawdown 15.29R > 15R

Current champion: `1h:bb_fade` with `{"n": 20, "k": 2.5, "trend_n": 200, "stop_atr": 1.5, "rr": 2.0, "trail": false, "session": true}`

## Adaptive selection (what the bot would actually have done)

| trades | win rate | profit factor | avg R | total R | max drawdown R |
|---|---|---|---|---|---|
| 114 | 33% | 1.7 | 0.412 | 47.01 | 15.29 |

## Each strategy on its own (best params re-picked monthly)

| strategy | trades | win rate | PF | total R | max DD R |
|---|---|---|---|---|---|
| 1h:macd_trend | 370 | 35% | 1.44 | 61.0 | 11.2 |
| 1h:ema_cross | 79 | 28% | 2.19 | 56.3 | 8.56 |
| 1h:donchian_breakout | 188 | 37% | 1.23 | 24.22 | 14.74 |
| 4h:macd_trend | 104 | 39% | 1.5 | 18.47 | 8.51 |
| 4h:supertrend_flip | 60 | 42% | 1.72 | 17.12 | 6.02 |
| 4h:ema_cross | 67 | 30% | 1.23 | 7.45 | 7.4 |
| 4h:rsi_pullback | 101 | 69% | 1.2 | 5.75 | 6.02 |
| 1h:bb_fade | 74 | 60% | 1.06 | 1.52 | 8.64 |
| 1h:rsi_pullback | 324 | 62% | 1.01 | 1.03 | 10.55 |
| 4h:donchian_breakout | 57 | 30% | 0.93 | -2.19 | 10.05 |
| 4h:bb_fade | 18 | 50% | 0.67 | -2.41 | 3.37 |
| 1h:supertrend_flip | 236 | 30% | 0.75 | -36.03 | 40.28 |

## Month by month

| test month | picked | OOS R |
|---|---|---|
| 2025-01-02 | 1h:supertrend_flip | -0.97 |
| 2025-02-02 | 1h:supertrend_flip | -0.08 |
| 2025-03-02 | 1h:supertrend_flip | 3.65 |
| 2025-04-02 | 1h:ema_cross | -2.98 |
| 2025-05-02 | 1h:supertrend_flip | -5.37 |
| 2025-06-02 | 1h:supertrend_flip | -1.93 |
| 2025-07-02 | 1h:ema_cross | 5.25 |
| 2025-08-02 | 1h:ema_cross | 12.45 |
| 2025-09-02 | 1h:ema_cross | -0.73 |
| 2025-10-02 | 1h:ema_cross | 5.65 |
| 2025-11-02 | 1h:ema_cross | -1.19 |
| 2025-12-02 | 1h:ema_cross | -2.19 |
| 2026-01-02 | 1h:ema_cross | 14.96 |
| 2026-02-02 | 1h:ema_cross | -1.03 |
| 2026-03-02 | 1h:ema_cross | 12.35 |
| 2026-04-02 | 1h:ema_cross | 0.0 |
| 2026-05-02 | 1h:ema_cross | 0.0 |
| 2026-06-02 | 1h:ema_cross | 4.57 |
| 2026-07-02 | 1h:ema_cross | -0.23 |
| 2026-08-02 | 1h:ema_cross | 8.64 |
| 2026-09-02 | 1h:ema_cross | -4.12 |
| 2026-10-02 | 1h:ema_cross | 1.73 |
| 2026-11-02 | 1h:ema_cross | -1.42 |
