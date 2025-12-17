#!/usr/bin/env python3
"""
Reset Telegram Bot Connection
Deletes webhooks and resets bot connections
"""
import sys
import requests
import config

# Bot token from config
BOT_TOKEN = config.TELEGRAM_BOT_TOKEN

if not BOT_TOKEN:
    print("Error: TELEGRAM_BOT_TOKEN not set!")
    sys.exit(1)

# Delete webhook
url = f"https://api.telegram.org/bot{BOT_TOKEN}/deleteWebhook?drop_pending_updates=true"
print(f"Deleting webhook and pending updates...")

response = requests.get(url)
print(f"Status: {response.status_code}")
print(f"Response: {response.json()}")

if response.status_code == 200:
    print("\n✓ Bot connection reset!")
    print("Wait 5 seconds and then restart the bot.")
else:
    print("\n✗ Error during reset!")
    sys.exit(1)
    