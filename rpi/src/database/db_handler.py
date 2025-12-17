"""
SQLite Database Handler for heating data
Saves MQTT data from tank sensors
"""
import sqlite3
from datetime import datetime
from typing import List, Tuple, Optional
import logging

logger = logging.getLogger(__name__)


class DatabaseHandler:
    def __init__(self, db_path: str = "tank_data.db", on_data_update=None):
        self.db_path = db_path
        self.on_data_update = on_data_update
        self.init_database()

    def init_database(self):
        """Initializes the database with required tables"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            # Table for tank level measurements
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS level_measurements (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp DATETIME NOT NULL,
                    tank_id INTEGER NOT NULL,
                    level_1 INTEGER NOT NULL,
                    level_2 INTEGER NOT NULL,
                    level_3 INTEGER NOT NULL,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Table for temperature measurements
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS temp_measurements (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp DATETIME NOT NULL,
                    tank_id INTEGER NOT NULL,
                    sensor_name TEXT NOT NULL,
                    temperature INTEGER NOT NULL,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Indices for faster queries
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_level_timestamp
                ON level_measurements(timestamp DESC)
            """)

            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_temp_timestamp
                ON temp_measurements(timestamp DESC, sensor_name)
            """)

            conn.commit()
            logger.info(f"Database initialized: {self.db_path}")

    def insert_level_measurement(self, timestamp: str, tank_id: int,
                                 level_1: int, level_2: int, level_3: int):
        """
        Saves a tank level measurement
        Format: tank/1/level 04.12.2025 13:01:18,721,718,720,1
        """
        try:
            # Convert timestamp
            dt = datetime.strptime(timestamp, "%d.%m.%Y %H:%M:%S")

            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO level_measurements
                    (timestamp, tank_id, level_1, level_2, level_3)
                    VALUES (?, ?, ?, ?, ?)
                """, (dt, tank_id, level_1, level_2, level_3))
                conn.commit()
                logger.debug(f"Tank level saved: Tank {tank_id}, {dt}")

                # Callback for plot export
                if self.on_data_update:
                    logger.debug(f"Calling on_data_update callback (Level)")
                    self.on_data_update()
                    logger.debug("on_data_update callback completed")
                else:
                    logger.warning("No on_data_update callback registered!")
        except Exception as e:
            logger.error(f"Error saving tank level: {e}")

    def insert_temp_measurement(self, timestamp: str, tank_id: int,
                               sensor_name: str, temperature: int):
        """
        Saves a temperature measurement
        Format: tank/1/temp/1-AUS 04.12.2025 13:01:18,201
        """
        try:
            # Convert timestamp
            dt = datetime.strptime(timestamp, "%d.%m.%Y %H:%M:%S")

            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO temp_measurements
                    (timestamp, tank_id, sensor_name, temperature)
                    VALUES (?, ?, ?, ?)
                """, (dt, tank_id, sensor_name, temperature))
                conn.commit()
                logger.debug(f"Temperature saved: Tank {tank_id}, {sensor_name}, {dt}")

                # Callback for plot export and alarm
                if self.on_data_update:
                    logger.debug(f"Calling on_data_update callback (Sensor: {sensor_name})")
                    self.on_data_update()
                    logger.debug("on_data_update callback completed")
                else:
                    logger.warning("No on_data_update callback registered!")
        except Exception as e:
            logger.error(f"Error saving temperature: {e}")

    def get_daily_temp_minmax(self, days: int = 30) -> List[Tuple]:
        """
        Gets min/max temperature values per day for the last N days
        Grouped by day and sensor
        If no data in last N days, show last available data
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            # First try data from last N days
            cursor.execute("""
                SELECT
                    DATE(timestamp) as date,
                    sensor_name,
                    MIN(temperature) as temp_min,
                    MAX(temperature) as temp_max
                FROM temp_measurements
                WHERE timestamp >= datetime('now', 'localtime', '-' || ? || ' days')
                GROUP BY DATE(timestamp), sensor_name
                ORDER BY date, sensor_name
            """, (days,))
            results = cursor.fetchall()

            # If no data, get last available data
            if not results:
                logger.warning(f"No data in last {days} days, showing last available data")
                cursor.execute("""
                    SELECT
                        DATE(timestamp) as date,
                        sensor_name,
                        MIN(temperature) as temp_min,
                        MAX(temperature) as temp_max
                    FROM temp_measurements
                    WHERE timestamp >= (
                        SELECT MAX(DATE(timestamp, '-' || ? || ' days'))
                        FROM temp_measurements
                    )
                    GROUP BY DATE(timestamp), sensor_name
                    ORDER BY date, sensor_name
                """, (days,))
                results = cursor.fetchall()

            return results

    def get_hourly_temps(self, days: int = 7) -> List[Tuple]:
        """
        Gets all temperature values for the last N days
        Grouped hourly for better performance
        If no data in last N days, show last available data
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT
                    datetime(timestamp) as timestamp,
                    sensor_name,
                    AVG(temperature) as temperature
                FROM temp_measurements
                WHERE timestamp >= datetime('now', 'localtime', '-' || ? || ' days')
                GROUP BY strftime('%Y-%m-%d %H:00:00', timestamp), sensor_name
                ORDER BY timestamp, sensor_name
            """, (days,))
            results = cursor.fetchall()

            # If no data, get last available data
            if not results:
                logger.warning(f"No data in last {days} days, showing last available data")
                cursor.execute("""
                    SELECT
                        datetime(timestamp) as timestamp,
                        sensor_name,
                        AVG(temperature) as temperature
                    FROM temp_measurements
                    WHERE timestamp >= datetime((
                        SELECT MAX(timestamp)
                        FROM temp_measurements
                    ), '-' || ? || ' days')
                    GROUP BY strftime('%Y-%m-%d %H:00:00', timestamp), sensor_name
                    ORDER BY timestamp, sensor_name
                """, (days,))
                results = cursor.fetchall()

            return results

    def get_daily_level_median(self, days: int = 30) -> List[Tuple]:
        """
        Gets the last tank level per day (median of 3 values)
        If no data in last N days, show last available data
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                WITH daily_last AS (
                    SELECT
                        DATE(timestamp) as date,
                        level_1,
                        level_2,
                        level_3,
                        ROW_NUMBER() OVER (PARTITION BY DATE(timestamp) ORDER BY timestamp DESC) as rn
                    FROM level_measurements
                    WHERE timestamp >= datetime('now', 'localtime', '-' || ? || ' days')
                )
                SELECT
                    date,
                    (level_1 + level_2 + level_3) / 3.0 as level_median
                FROM daily_last
                WHERE rn = 1
                ORDER BY date
            """, (days,))
            results = cursor.fetchall()

            # If no data, get last available data
            if not results:
                logger.warning(f"No data in last {days} days, showing last available data")
                cursor.execute("""
                    WITH daily_last AS (
                        SELECT
                            DATE(timestamp) as date,
                            level_1,
                            level_2,
                            level_3,
                            ROW_NUMBER() OVER (PARTITION BY DATE(timestamp) ORDER BY timestamp DESC) as rn
                        FROM level_measurements
                        WHERE timestamp >= (
                            SELECT MAX(DATE(timestamp, '-' || ? || ' days'))
                            FROM level_measurements
                        )
                    )
                    SELECT
                        date,
                        (level_1 + level_2 + level_3) / 3.0 as level_median
                    FROM daily_last
                    WHERE rn = 1
                    ORDER BY date
                """, (days,))
                results = cursor.fetchall()

            return results

    def get_hourly_level_median(self, days: int = 7) -> List[Tuple]:
        """
        Gets tank levels hourly (median of 3 values)
        If no data in last N days, show last available data
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT
                    datetime(timestamp) as timestamp,
                    (level_1 + level_2 + level_3) / 3.0 as level_median
                FROM level_measurements
                WHERE timestamp >= datetime('now', 'localtime', '-' || ? || ' days')
                ORDER BY timestamp
            """, (days,))
            results = cursor.fetchall()

            # If no data, get last available data
            if not results:
                logger.warning(f"No data in last {days} days, showing last available data")
                cursor.execute("""
                    SELECT
                        datetime(timestamp) as timestamp,
                        (level_1 + level_2 + level_3) / 3.0 as level_median
                    FROM level_measurements
                    WHERE timestamp >= datetime((
                        SELECT MAX(timestamp)
                        FROM level_measurements
                    ), '-' || ? || ' days')
                    ORDER BY timestamp
                """, (days,))
                results = cursor.fetchall()

            return results
        