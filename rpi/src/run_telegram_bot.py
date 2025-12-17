#!/usr/bin/env python3
"""
Starts the Telegram Bot for Tank Monitoring
Telegram Chatbot for heating data
"""
import sys
import logging
from pathlib import Path

# Add src to Python path
sys.path.insert(0, str(Path(__file__).resolve().parent))

from messenger.bot_handler import TankTelegramBot
import config


def main():
    # Configure logging
    logging.basicConfig(
        level=getattr(logging, config.LOG_LEVEL),
        format=config.LOG_FORMAT
    )

    logger = logging.getLogger(__name__)

    # Check bot token
    if not config.TELEGRAM_BOT_TOKEN:
        logger.error("TELEGRAM_BOT_TOKEN not set!")
        logger.error("Set environment variable: export TELEGRAM_BOT_TOKEN='your-token'")
        sys.exit(1)

    # Check authorized user ID
    if not config.TELEGRAM_MY_ID:
        logger.warning("TELEGRAM_MY_ID not set - Bot responds to ALL users (insecure!)")
        logger.warning("Set environment variable: export TELEGRAM_MY_ID='your-user-id'")

    logger.info("Starting Telegram Bot...")
    logger.info(f"Database: {config.DATABASE_PATH}")
    logger.info(f"Output: {config.TELEGRAM_OUTPUT_DIR}")
    logger.info(f"Authorized User: {config.TELEGRAM_MY_ID or 'ALL (insecure!)'}")

    # Create and start bot
    bot = TankTelegramBot(
        token=config.TELEGRAM_BOT_TOKEN,
        db_path=config.DATABASE_PATH,
        output_dir=config.TELEGRAM_OUTPUT_DIR,
        authorized_user_id=config.TELEGRAM_MY_ID
    )

    try:
        bot.run()
    except KeyboardInterrupt:
        logger.info("Bot stopped by user...")
        bot.stop()
    except Exception as e:
        logger.error(f"Error in Telegram Bot: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
    