"""
Alarm Handler for Telegram Bot
Alarm API with periodic messages
Alarm function enable/disable with "heating alarm on/off"
Uses config.evaluate_alarm for evaluation
Database Watch - evaluate_alarm on every DB update
"""
import logging
import asyncio
from typing import Optional
from telegram import Bot
from database.db_handler import DatabaseHandler
import config

logger = logging.getLogger(__name__)


class AlarmHandler:
    def __init__(self, bot: Bot, db_handler: DatabaseHandler, chat_id: int):
        """
        Initializes the alarm handler

        Args:
            bot: Telegram Bot instance
            db_handler: Database Handler
            chat_id: Chat ID of the authorized user
        """
        self.bot = bot
        self.db_handler = db_handler
        self.chat_id = chat_id
        self.alarm_task: Optional[asyncio.Task] = None
        self.alarm_stopped = False
        self.repetition = 0  # Repetition counter
        self.last_alarm_time = 0  # Timestamp of last alarm

        # Alarm status (on/off)
        self.alarm_enabled = True  # Default: Alarm is enabled

        # Register callback for DB updates
        # Save previous callback for chaining (e.g. PlotExporter)
        self._previous_callback = self.db_handler.on_data_update
        self.db_handler.on_data_update = self._on_db_update_sync

    def is_alarm_active(self) -> bool:
        """
        Checks if an alarm is currently running

        Returns:
            True if alarm is running
        """
        return self.alarm_task is not None and not self.alarm_task.done()

    def is_alarm_enabled(self) -> bool:
        """
        Checks if alarm function is enabled

        Returns:
            True if alarm is enabled
        """
        return self.alarm_enabled

    def enable_alarm(self):
        """
        Enables alarm function
        """
        if not self.alarm_enabled:
            self.alarm_enabled = True
            logger.info("Alarm function enabled")
        else:
            logger.info("Alarm function was already enabled")

    def disable_alarm(self):
        """
        Disables alarm function
        Also stops active alarms
        """
        if self.alarm_enabled:
            self.alarm_enabled = False
            logger.info("Alarm function disabled")
            # Stop active alarm if present
            if self.is_alarm_active():
                self.alarm_stopped = True
                self.repetition = 0
                if self.alarm_task:
                    self.alarm_task.cancel()
                self.alarm_task = None
        else:
            logger.info("Alarm function was already disabled")

    def _on_db_update_sync(self):
        """
        Synchronous callback for DB updates
        Called by DatabaseHandler (synchronously)
        Triggers asynchronous alarm check and calls previous callback
        """
        logger.info("=== AlarmHandler._on_db_update_sync called ===")
        try:
            # Call previous callback (e.g. PlotExporter)
            if self._previous_callback:
                logger.debug(f"Calling previous callback: {self._previous_callback}")
                self._previous_callback()
                logger.debug("Previous callback completed")
            else:
                logger.debug("No previous callback present")

            # Create task for asynchronous alarm check            
            try:
                loop = asyncio.get_running_loop()
                logger.info(f"Event loop found: {loop}")
                # Schedule in running loop
                asyncio.create_task(self._check_alarm_on_update())
                logger.info("✓ Alarm check task created and triggered by DB update")
            except RuntimeError as e:
                # No running loop - this is a problem!
                logger.error(f"✗ NO running event loop - alarm check NOT possible! Error: {e}")
                logger.error("This means: Bot is not running or running in different process!")
        except Exception as e:
            logger.error(f"Error in _on_db_update_sync: {e}", exc_info=True)

    async def _check_alarm_on_update(self):
        """
        Checks alarm conditions on DB update
        Only if alarm is enabled
        Uses config.evaluate_alarm
        """
        try:
            logger.debug("_check_alarm_on_update called")
            
            if not self.alarm_enabled:
                logger.debug("Alarm function is disabled, skipping check")
                return

            # Get current temperatures, wait a bit until record is completely written
            await asyncio.sleep(5)
            temps = self._get_current_temperatures()
            logger.debug(f"Current temperatures: {temps}")

            if not temps:
                logger.debug("No temperature data for alarm check")
                return

            # Evaluate alarm condition
            logger.debug(f"Calling evaluate_alarm with repetition={self.repetition}")
            # Wait for multiple mqtt data to complete            
            alarm_result = config.evaluate_alarm(temps, self.repetition)
            logger.debug(f"evaluate_alarm result: {alarm_result}")

            if alarm_result:
                text, timeout, max_repetitions = alarm_result                
                if not self.is_alarm_active():
                    # Start new alarm
                    logger.info("Alarm condition met, starting alarm")
                    self.alarm_stopped = False
                    self.repetition = 0
                    self.alarm_task = asyncio.create_task(
                        self._alarm_loop(text, timeout, max_repetitions)
                    )
                else:
                    logger.debug("Alarm already active, skipping")
            else:
                # No alarm condition anymore
                if self.is_alarm_active():
                    logger.info("Alarm condition no longer met, stopping alarm")
                    self.alarm_stopped = True
                    self.repetition = 0
                    if self.alarm_task:
                        self.alarm_task.cancel()
                    self.alarm_task = None
                    await self.bot.send_message(
                        chat_id=self.chat_id,
                        text="✅ Alarm ended: Temperatures back to normal range"
                    )

        except Exception as e:
            logger.error(f"Error in _check_alarm_on_update: {e}", exc_info=True)

    async def start_alarm_monitoring(self):
        """
        Initializes alarm monitoring (DB callback already registered)
        No periodic check needed anymore - triggered by DB updates
        """
        logger.info("Alarm monitoring initialized (DB callback active)")
        # Perform initial check
        await self._check_alarm_on_update()

    async def test_alarm(self):
        """
        Sends test alarm after 15 seconds
        For testing alarm functionality
        """
        logger.info("Alarm test started - sending message in 15 seconds")

        try:
            # Wait 15 seconds
            await asyncio.sleep(15)

            # Send test message
            await self.bot.send_message(
                chat_id=self.chat_id,
                text="🧪 Alarm test"
            )
            logger.info("Alarm test message sent")

        except asyncio.CancelledError:
            logger.info("Alarm test cancelled")
        except Exception as e:
            logger.error(f"Error during alarm test: {e}", exc_info=True)

    async def _alarm_loop(self, text: str, timeout: int, max_repetitions: int):
        """
        Main alarm loop with repetitions
        Runs until user sends "stop" or max_repetitions reached
        Uses passed alarm parameters

        Args:
            text: Alarm text from evaluate_alarm
            timeout: Wait time between repetitions in seconds
            max_repetitions: Maximum number of repetitions
        """
        try:
            while not self.alarm_stopped and self.repetition < max_repetitions:
                # Send alarm message
                await self._send_alarm_message(text, self.repetition, max_repetitions)

                self.repetition += 1

                # Maximum repetitions reached?
                if self.repetition >= max_repetitions:
                    logger.info(f"Maximum repetitions reached ({max_repetitions})")
                    await self.bot.send_message(
                        chat_id=self.chat_id,
                        text=f"⚠️ Alarm maximum reached ({max_repetitions} repetitions).\n"
                             f"Please check the heating!"
                    )
                    break

                # Wait timeout seconds
                await asyncio.sleep(timeout)

        except asyncio.CancelledError:
            # Alarm stopped by user
            logger.info("Alarm loop cancelled by user")
            await self.bot.send_message(
                chat_id=self.chat_id,
                text="⏹️ Alarm stopped"
            )
        except Exception as e:
            logger.error(f"Error in alarm loop: {e}", exc_info=True)
            await self.bot.send_message(
                chat_id=self.chat_id,
                text=f"❌ Error in alarm system: {e}"
            )
        finally:
            self.alarm_task = None
            self.repetition = 0

    def _get_current_temperatures(self) -> dict:
        """
        Gets the most recent temperatures from the database

        Returns:
            Dictionary with sensor names and temperatures
            Format: {'2-ABV': temp, '3-ABR': temp, ...}
        """
        try:
            import sqlite3
            with sqlite3.connect(self.db_handler.db_path) as conn:
                cursor = conn.cursor()
                # Get latest temperatures (max 1 hour old)
                cursor.execute("""
                    SELECT sensor_name, temperature
                    FROM temp_measurements
                    WHERE timestamp >= datetime('now', 'localtime', '-1 hour')
                    GROUP BY sensor_name
                    HAVING timestamp = MAX(timestamp)
                """)
                results = cursor.fetchall()

                # Convert to dictionary (temperature in °C, not tenth-degrees)
                temps = {sensor: temp / 10.0 for sensor, temp in results}
                logger.debug(f"Current temperatures: {temps}")
                return temps

        except Exception as e:
            logger.error(f"Error retrieving temperatures: {e}")
            return {}

    async def _send_alarm_message(self, text: str, repetition: int, max_repetitions: int):
        """
        Sends an alarm message

        Args:
            text: Alarm text
            repetition: Current repetition
            max_repetitions: Maximum number of repetitions
        """
        message = (
            f"{text}\n\n"
            f"Repetition: {repetition + 1}/{max_repetitions}\n"            
        )

        try:
            await self.bot.send_message(chat_id=self.chat_id, text=message)
            logger.info(f"Alarm message sent (repetition {repetition + 1}/{max_repetitions})")
        except Exception as e:
            logger.error(f"Error sending alarm message: {e}")