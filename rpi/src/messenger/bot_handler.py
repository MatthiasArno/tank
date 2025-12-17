import logging
import asyncio
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from database.db_handler import DatabaseHandler
from utils.plot_exporter_mpl import PlotExporterMPL
from messenger.alarm_handler import AlarmHandler
from utils.db_watcher import DatabaseWatcher

logger = logging.getLogger(__name__)


class TankTelegramBot:
    """
    Telegram Bot for Tank Monitoring
    Sends heating data as PNG graphics
    """

    def __init__(self, token: str, db_path: str, output_dir: str, authorized_user_id: str = None):
        """
        Initializes the Telegram Bot

        Args:
            token: Telegram Bot Token
            db_path: Path to SQLite Database
            output_dir: Temporary directory for PNG export
            authorized_user_id: Authorized Telegram User ID (only this user may use the bot)
        """
        self.token = token
        self.authorized_user_id = authorized_user_id
        self.db_handler = DatabaseHandler(db_path=db_path)
        # Explicitly use matplotlib for PNG export (no Chrome/Kaleido needed)
        self.plot_exporter = PlotExporterMPL(
            db_handler=self.db_handler,
            output_dir=output_dir
        )

        # Bot Application
        self.app = Application.builder().token(token).build()

        # Initialize alarm handler immediately (uses authorized_user_id as chat_id)
        # Chat ID is updated on first /start if needed
        if authorized_user_id:
            self.alarm_handler = AlarmHandler(
                bot=self.app.bot,
                db_handler=self.db_handler,
                chat_id=int(authorized_user_id)  # User ID = Chat ID for private chats
            )
            logger.info(f"Alarm handler initialized for user {authorized_user_id}")

            # DB Watcher for inter-process communication
            try:
                self.db_watcher = DatabaseWatcher(
                    db_path=db_path,
                    callback=self.alarm_handler._check_alarm_on_update
                )
                logger.info("✓ DatabaseWatcher initialized (inotify)")
            except Exception as e:
                logger.error(f"Error during initialization of DatabaseWatcher: {e}")
                self.db_watcher = None
        else:
            self.alarm_handler = None
            self.db_watcher = None
            logger.warning("Alarm handler not initialized - TELEGRAM_MY_ID missing")

        # Register command handlers
        self.app.add_handler(CommandHandler("start", self.cmd_start))
        self.app.add_handler(CommandHandler("help", self.cmd_help))

        # Message handler for text messages
        self.app.add_handler(MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            self.handle_message
        ))

        logger.info(f"Telegram Bot initialized. Authorized user: {authorized_user_id or 'unsecure bot!'}")
        logger.info("Plot Exporter: matplotlib (RPi optimized, no Chrome)")

    def _is_authorized(self, user_id: int) -> bool:
        """
        Checks if user is authorized

        Args:
            user_id: Telegram User ID

        Returns:
            True if authorized or no authorization configured
        """
        if not self.authorized_user_id:
            return True
        return str(user_id) == str(self.authorized_user_id)

    async def cmd_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """
        /start Command Handler
        """
        user_id = update.effective_user.id
        chat_id = update.effective_chat.id

        # Authorization check
        if not self._is_authorized(user_id):
            logger.warning(f"Unauthorized access from user {user_id}")
            return

        # Perform initial alarm check
        if self.alarm_handler:
            await self.alarm_handler.start_alarm_monitoring()
            alarm_status = "🟢 ON" if self.alarm_handler.is_alarm_enabled() else "🔴 OFF"
        else:
            alarm_status = "⚠️ NOT AVAILABLE (TELEGRAM_MY_ID missing)"

        welcome_msg = (
            "🔥 Welcome to the Tank Monitoring Bot!\n\n"
            "Available commands:\n"
            "• heating day - 7-day view\n"
            "• heating month - 30-day view + forecast\n"
            "• heating alarm on/off - Enable/disable alarm function\n"
            "• heating alarm test - Test alarm after 15s\n"
            "• /help - Show this help\n\n"
            f"🚨 Alarm function: {alarm_status}"
        )
        await update.message.reply_text(welcome_msg)
        logger.info(f"Start command from user {user_id}")

    async def cmd_help(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """
        /help Command Handler
        Shows alarm status
        """
        user_id = update.effective_user.id

        # Authorization check
        if not self._is_authorized(user_id):
            logger.warning(f"Unauthorized access from user {user_id}")
            return

        # Show alarm status
        if self.alarm_handler:
            alarm_status = "🟢 ON" if self.alarm_handler.is_alarm_enabled() else "🔴 OFF"
            alarm_info = f"Alarm function is {alarm_status}"
        else:
            alarm_info = "Alarm function not initialized"

        help_msg = (
            "📊 Tank Monitoring Bot - Help\n\n"
            "Send one of the following messages:\n\n"
            "• heating day\n"
            "  → 7-day view with all temperature and tank level values\n\n"
            "• heating month\n"
            "  → 30-day view with Min/Max temperatures, tank level + 30-day forecast\n\n"
            "• heating alarm on\n"
            "  → Enables the alarm function\n\n"
            "• heating alarm off\n"
            "  → Disables the alarm function\n\n"
            "• heating alarm test\n"
            "  → Tests the alarm function (message after 15s)\n\n"
            "The graphics show:\n"
            "🌡️ Temperatures (ABV, ABR, NBV, NBR, AUS)\n"
            "💧 Tank Level (median of measurements)\n"
            "🔮 Forecast (30-day consumption prediction, as far as weather data available)\n\n"
            f"🚨 Alarm monitoring: {alarm_info}\n"
            "Alarms are automatically sent when temperatures fall below 15°C."
        )
        await update.message.reply_text(help_msg)
        logger.info(f"Help command from user {user_id}")

    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """
        Handler for text messages
        "heating day" → 7-day PNG
        "heating month" → 30-day PNG
        "heating alarm on/off" → Enable/disable alarm function
        """
        message_text = update.message.text.lower().strip()
        user_id = update.effective_user.id

        logger.info(f"Message from user {user_id}: {message_text}")

        # Authorization check
        if not self._is_authorized(user_id):
            logger.warning(f"Unauthorized access from user {user_id}")
            return

        # heating day
        if message_text == "heating day":
            await self.send_7day_plot(update)
            return

        # heating month
        if message_text == "heating month":
            await self.send_30day_plot(update)
            return

        # heating alarm on
        if message_text == "heating alarm on":
            await self.handle_alarm_enable(update)
            return

        # heating alarm off
        if message_text == "heating alarm off":
            await self.handle_alarm_disable(update)
            return

        # heating alarm test
        if message_text == "heating alarm test":
            await self.handle_alarm_test(update)
            return

        # Unknown message
        await update.message.reply_text(
            "❓ Command not recognized.\n"
            "Send /help for available commands."
        )

    async def send_7day_plot(self, update: Update):
        """
        Sends 7-day view as PNG
        "heating day"
        """
        user_id = update.effective_user.id
        logger.info(f"7-day plot requested from user {user_id}")

        await update.message.reply_text("📊 Creating 7-day view...")

        try:
            # Use plot_exporter
            png_path = self.plot_exporter.export_7day_plot()

            if png_path:
                with open(png_path, 'rb') as photo:
                    await update.message.reply_photo(
                        photo=photo,
                        caption="🔥 Heating - 7 Day View\n"
                                "🌡️ Temperatures: All readings\n"
                                "💧 Tank Level: Median of sensors"
                    )
                logger.info(f"7-day plot sent to user {user_id}")
            else:
                await update.message.reply_text(
                    "❌ Error creating graphic. Please try again later."
                )
                logger.error(f"Error exporting 7-day plot for user {user_id}")

        except Exception as e:
            logger.error(f"Error while sending 7-day plot: {e}", exc_info=True)
            await update.message.reply_text(
                "❌ Error while sending the graphic."
            )

    async def send_30day_plot(self, update: Update):
        """
        Sends 30-day view as PNG with forecast
        "heating month"
        Includes forecast as 3rd diagram
        """
        user_id = update.effective_user.id
        logger.info(f"30-day + forecast plot requested from user {user_id}")

        await update.message.reply_text("📊 Creating 30-day view + forecast...")

        try:
            # Use 30-day + forecast version
            png_path = self.plot_exporter.export_30day_with_forecast_plot()

            if png_path:
                with open(png_path, 'rb') as photo:
                    await update.message.reply_photo(
                        photo=photo,
                        caption="🔥 Heating - 30 Day View + Forecast\n"
                                "🌡️ Temperatures: Min/Max per day\n"
                                "💧 Tank Level: Last value of the day\n"
                                "🔮 Forecast: 30 day consumption forecast (as far as available)"
                    )
                logger.info(f"30-day + forecast plot sent to user {user_id}")
            else:
                await update.message.reply_text(
                    "❌ Error creating the graphic. Please try again later."
                )
                logger.error(f"Error exporting 30-day + forecast plot for user {user_id}")

        except Exception as e:
            logger.error(f"Error while sending 30-day + forecast plot: {e}", exc_info=True)
            await update.message.reply_text(
                "❌ Error while sending the graphic."
            )

    async def handle_alarm_enable(self, update: Update):
        """
        Enables alarm function
        """
        user_id = update.effective_user.id
        logger.info(f"'heating alarm on' from user {user_id}")

        if self.alarm_handler is None:
            await update.message.reply_text(
                "ℹ️ Alarm system is not initialized.\n"
                "Send /start to initialize the bot."
            )
            return

        if self.alarm_handler.is_alarm_enabled():
            await update.message.reply_text(
                "ℹ️ Alarm function is already enabled."
            )
        else:
            self.alarm_handler.enable_alarm()
            await update.message.reply_text(
                "🟢 Alarm function enabled.\n"
                "At temperatures below 15°C alarms will be sent."
            )
            logger.info(f"Alarm function enabled by user {user_id}")
            # Perform check immediately
            await self.alarm_handler._check_alarm_on_update()

    async def handle_alarm_disable(self, update: Update):
        """
        Disables alarm function
        """
        user_id = update.effective_user.id
        logger.info(f"'heating alarm off' from user {user_id}")

        if self.alarm_handler is None:
            await update.message.reply_text(
                "ℹ️ Alarm system is not initialized.\n"
                "Send /start to initialize the bot."
            )
            return

        if not self.alarm_handler.is_alarm_enabled():
            await update.message.reply_text(
                "ℹ️ Alarm function is already disabled."
            )
        else:
            self.alarm_handler.disable_alarm()
            await update.message.reply_text(
                "🔴 Alarm function disabled.\n"
                "No more alarms will be sent."
            )
            logger.info(f"Alarm function disabled by user {user_id}")

    async def handle_alarm_test(self, update: Update):
        """
        Starts alarm test (sends "Alarm test" after 15s)
        """
        user_id = update.effective_user.id
        logger.info(f"'heating alarm test' from user {user_id}")

        if self.alarm_handler is None:
            await update.message.reply_text(
                "ℹ️ Alarm system is not initialized.\n"
                "Send /start to initialize the bot."
            )
            return

        await update.message.reply_text(
            "🧪 Alarm test started!\n"
            "You will receive a test message in 15 seconds."
        )
        logger.info(f"Alarm test started by user {user_id}")

        # Start test asynchronously
        asyncio.create_task(self.alarm_handler.test_alarm())

    def run(self):
        """
        Starts the Telegram Bot and DB Watcher
        """
        logger.info("Starting Telegram Bot...")

        # Start DB Watcher in event loop
        if self.db_watcher:
            async def start_watcher_and_bot():
                # Start DB Watcher
                await self.db_watcher.start()
                logger.info("✓ DB Watcher running")

                # Bot then runs in run_polling
                # (run_polling blocks, so watcher starts first)

            # Execute watcher start before bot start
            import asyncio
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(start_watcher_and_bot())

        self.app.run_polling(allowed_updates=Update.ALL_TYPES)

    async def _stop_watcher(self):
        """Stops DB Watcher"""
        if self.db_watcher:
            await self.db_watcher.stop()

    def stop(self):
        """
        Stops the Telegram Bot and DB Watcher
        """
        logger.info("Stopping Telegram Bot...")

        # Stop DB Watcher
        if self.db_watcher:
            import asyncio
            try:
                loop = asyncio.get_event_loop()
                loop.run_until_complete(self._stop_watcher())
            except:
                pass

        # Cleanup is automatically handled by run_polling