"""Send alerts to your phone. Works with whichever is configured:

- ntfy (free Android/iOS app, no account): set secret NTFY_TOPIC to a long
  random topic name and subscribe to the same name in the app.
- Telegram: set TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID.
"""
import os

import requests


def send(title, body, priority="default", tags=""):
    print(f"\n=== {title} ===\n{body}\n")
    topic = os.getenv("NTFY_TOPIC")
    if topic:
        server = os.getenv("NTFY_SERVER", "https://ntfy.sh")
        requests.post(f"{server}/{topic}", data=body.encode(), timeout=20, headers={
            "Title": title.encode("ascii", "ignore").decode(),
            "Priority": priority, "Tags": tags}).raise_for_status()
    tok, chat = os.getenv("TELEGRAM_BOT_TOKEN"), os.getenv("TELEGRAM_CHAT_ID")
    if tok and chat:
        requests.post(f"https://api.telegram.org/bot{tok}/sendMessage", timeout=20,
                      json={"chat_id": chat, "text": f"{title}\n\n{body}"}).raise_for_status()
