#!/usr/bin/env python3
"""
Starts the MQTT Subscriber for tank sensor data
"""
import sys
import logging
from pathlib import Path

# Add src to Python path
sys.path.insert(0, str(Path(__file__).resolve().parent))

from mqtt.subscriber import TankMQTTSubscriber
from database.db_handler import DatabaseHandler
import config


def main():
    # Configure logging
    logging.basicConfig(
        level=getattr(logging, config.LOG_LEVEL),
        format=config.LOG_FORMAT
    )

    logger = logging.getLogger(__name__)
    logger.info("Starting MQTT Subscriber...")

    # Initialize database
    db_handler = DatabaseHandler(db_path=config.DATABASE_PATH)

    # Create and start subscriber
    subscriber = TankMQTTSubscriber(
        broker_host=config.MQTT_BROKER_HOST,
        broker_port=config.MQTT_BROKER_PORT,
        db_handler=db_handler
    )

    try:
        subscriber.start()
    except KeyboardInterrupt:
        logger.info("Subscriber stopped by user...")
        subscriber.stop()
    except Exception as e:
        logger.error(f"Error in subscriber: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
    