# Gold Signal Bot (for Plus500)

Plus500 has no trading API and bans automated control of its app, so this bot does
everything except press the button: it researches strategies, watches gold every
hour, and sends your phone an alert telling you exactly what to do on Plus500
(direction, size in oz, stop and target distances). You place the trade yourself.

## How it decides

1. **Weekly research (Saturday, market closed).** Backtests 6 strategy families
   (EMA cross, Donchian breakout, Supertrend, MACD trend, RSI pullback, Bollinger
   fade) on 1h and 4h gold bars over the last ~2 years, about 300 combinations,
   including Plus500's 0.66 spread, slippage and overnight funding.
2. **Walk-forward selection.** Each month, it picks the best strategy using only the
   previous 6 months, then records how that pick did in the following month, which
   it never saw. Only that unseen record counts.
3. **Gates.** Signals switch on only if the unseen record has 30+ trades, a profit
   factor of 1.15 or more, a max drawdown of 15R or less, and a positive total. If
   nothing passes, the bot stays silent and tells you so. That is a feature: no edge
   means no trades.
4. **Hourly signals.** At 4 minutes past each hour the current champion runs on the
   latest closed bar. You only get alerts when something changes: ENTER, EXIT, FLIP,
   or MOVE STOP.
5. **Kill switch.** Every signalled trade is logged to `state/ledger.csv`. If live
   results draw down more than 8R, the bot pauses itself and alerts you.

Results are in **R**: 1R is the amount risked per trade (1% of balance by default).

## Setup (about 10 minutes)

1. Push this folder to a **private** GitHub repo.
2. Install the **ntfy** app (Play Store / App Store). Subscribe to a long random
   topic name, e.g. `gold-7f3k9q2xw81m`. Anyone who knows the name can read it, so
   make it unguessable.
3. In the repo: Settings > Secrets and variables > Actions > New secret:
   `NTFY_TOPIC` = your topic name. (Telegram works too: `TELEGRAM_BOT_TOKEN` and
   `TELEGRAM_CHAT_ID`.)
4. Edit `config.json`: set `account_balance_aud` to your real balance and
   `risk_pct_per_trade` (1 is sensible; do not go above 2).
5. Actions tab > "Weekly strategy research" > Run workflow. Read
   `reports/report.md` and `reports/equity.png` when it finishes.
6. If the verdict is ON, the hourly workflow starts alerting on its own.

## Using the alerts on Plus500

- Stops and targets are given as **distances from your fill** because the bot
  watches COMEX gold futures (GC=F), which sit a few dollars from Plus500's price.
  Example: SELL fills at 3,667.10, alert says stop $32.40 ABOVE, so set the stop at
  3,699.50.
- Act within a few minutes of the alert. If price has already run more than about
  a third of the stop distance, skip the trade.
- The bot does not know about trades you place yourself. Keep manual trades
  separate in your head.

## Honest limits

- A strategy that passed walk-forward testing can still stop working. The kill switch
  and weekly re-selection limit the damage; they do not prevent losses.
- Run it for 4 to 8 weeks at small size (or just log the alerts) before trusting it
  with full size.
- GitHub's scheduler can run late by 5 to 15 minutes at busy times.

## Run locally

```
pip install -r requirements.txt
python -m pytest -q
python -m goldbot.research   # writes state/champion.json and reports/
python -m goldbot.live       # one signal check
```
