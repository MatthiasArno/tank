"""
MQTT Subscriber for tank sensor data
Subscribes to MQTT topics and stores data in SQLite
"""
import paho.mqtt.client as mqtt
import logging
import re
from typing import Optional
from database.db_handler import DatabaseHandler
from utils.plot_exporter import PlotExporter

logger = logging.getLogger(__name__)


class TankMQTTSubscriber:
    def __init__(self, broker_host: str, broker_port: int = 1883,
                 db_handler: Optional[DatabaseHandler] = None,
                 plot_exporter: Optional[PlotExporter] = None):
        self.broker_host = broker_host
        self.broker_port = broker_port
        self.db_handler = db_handler or DatabaseHandler()
        self.plot_exporter = plot_exporter

        # Connect PlotExporter with DatabaseHandler
        if self.plot_exporter and self.db_handler:
            self.db_handler.on_data_update = self.plot_exporter.export_all_plots

        self.client = mqtt.Client()
        self.client.on_connect = self.on_connect
        self.client.on_message = self.on_message
        self.client.on_disconnect = self.on_disconnect

        # Topic patterns
        self.level_pattern = re.compile(r'^tank/(\d+)/level$')
        self.temp_pattern = re.compile(r'^tank/(\d+)/temp/(.+)$')

    def on_connect(self, client, userdata, flags, rc):
        """Callback when connection established"""
        if rc == 0:
            logger.info(f"Connected to MQTT Broker {self.broker_host}:{self.broker_port}")
            # Subscribe to all relevant topics
            client.subscribe("tank/+/level")
            client.subscribe("tank/+/temp/+")
            logger.info("Topics subscribed: tank/+/level, tank/+/temp/+")
        else:
            logger.error(f"Connection failed with code: {rc}")

    def on_disconnect(self, client, userdata, rc):
        """Callback on connection loss"""
        if rc != 0:
            logger.warning(f"Unexpected disconnect. Code: {rc}")

    def on_message(self, client, userdata, msg):
        """
        Callback for incoming MQTT messages
        Processes level and temp topics
        """
        topic = msg.topic
        payload = msg.payload.decode('utf-8')

        logger.debug(f"Message received: {topic} -> {payload}")

        try:
            # Check if level measurement
            level_match = self.level_pattern.match(topic)
            if level_match:
                self.process_level_message(level_match, payload)
                return

            # Check if temperature measurement
            temp_match = self.temp_pattern.match(topic)
            if temp_match:
                self.process_temp_message(temp_match, payload)
                return

            logger.debug(f"Topic not processed: {topic}")

        except Exception as e:
            logger.error(f"Error processing message: {e}")

    def process_level_message(self, match, payload: str):
        """
        Processes level messages
        Format: 04.12.2025 13:01:18,721,718,720,1
        """
        tank_id = int(match.group(1))

        # Parse payload
        parts = payload.split(',')
        if len(parts) < 4:
            logger.warning(f"Invalid level format: {payload}")
            return

        # Extract timestamp and values
        timestamp = parts[0].strip()
        level_1 = int(parts[1].strip())
        level_2 = int(parts[2].strip())
        level_3 = int(parts[3].strip())
        # parts[4] is ignored (always 1)

        # Save to database
        self.db_handler.insert_level_measurement(
            timestamp, tank_id, level_1, level_2, level_3
        )
        logger.info(f"Level saved: Tank {tank_id}, Median={(level_1+level_2+level_3)/3:.0f}mm")

    def process_temp_message(self, match, payload: str):
        """
        Processes temperature messages
        Format: 04.12.2025 13:01:18,201
        """
        tank_id = int(match.group(1))
        sensor_name = match.group(2)

        # Ignore 'device' topic
        if sensor_name == 'device':
            return

        # Parse payload
        parts = payload.split(',')
        if len(parts) < 2:
            logger.warning(f"Invalid temp format: {payload}")
            return

        timestamp = parts[0].strip()
        temperature = int(parts[1].strip())

        # Save to database
        self.db_handler.insert_temp_measurement(
            timestamp, tank_id, sensor_name, temperature
        )
        logger.info(f"Temp saved: Tank {tank_id}, {sensor_name}, {temperature/10:.1f}°C")

    def start(self):
        """Starts the MQTT subscriber"""
        try:
            logger.info(f"Connecting to MQTT Broker {self.broker_host}:{self.broker_port}...")
            self.client.connect(self.broker_host, self.broker_port, 60)
            self.client.loop_forever()
        except KeyboardInterrupt:
            logger.info("Subscriber is stopping...")
            self.stop()
        except Exception as e:
            logger.error(f"Error starting subscriber: {e}")

    def stop(self):
        """Stops the MQTT subscriber"""
        self.client.loop_stop()
        self.client.disconnect()
        logger.info("Subscriber stopped")


if __name__ == "__main__":
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    # Start subscriber
    subscriber = TankMQTTSubscriber(broker_host="localhost")
    subscriber.start()