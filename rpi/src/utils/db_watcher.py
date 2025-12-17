"""
Database File Watcher for inter-process communication
Uses inotify (Linux) to detect DB changes

When MQTT (different process) writes to DB, the bot is triggered
"""
import logging
import asyncio
from pathlib import Path
from typing import Callable, Optional
import os

logger = logging.getLogger(__name__)

try:
    import inotify.adapters
    INOTIFY_AVAILABLE = True
except ImportError:
    INOTIFY_AVAILABLE = False
    logger.warning("inotify not available - falling back to polling")


class DatabaseWatcher:
    """
    Monitors DB file for changes (cross-process)

    When another process (MQTT) writes to DB,
    the callback is called
    """

    def __init__(self, db_path: str, callback: Callable):
        """
        Args:
            db_path: Path to SQLite database
            callback: Async callback function on DB change
        """
        self.db_path = Path(db_path).resolve()
        self.callback = callback
        self.running = False
        self.watch_task: Optional[asyncio.Task] = None

        if not self.db_path.exists():
            raise FileNotFoundError(f"Database not found: {self.db_path}")

        logger.info(f"DatabaseWatcher initialized for: {self.db_path}")
        logger.info(f"inotify available: {INOTIFY_AVAILABLE}")

    async def start(self):
        """Starts DB watching"""
        if self.running:
            logger.warning("DatabaseWatcher already running")
            return

        self.running = True

        if INOTIFY_AVAILABLE:
            self.watch_task = asyncio.create_task(self._watch_with_inotify())
            logger.info("✓ DB watch started with inotify")
        else:
            self.watch_task = asyncio.create_task(self._watch_with_polling())
            logger.info("✓ DB watch started with polling (5s)")

    async def stop(self):
        """Stops DB watching"""
        self.running = False
        if self.watch_task:
            self.watch_task.cancel()
            try:
                await self.watch_task
            except asyncio.CancelledError:
                pass
        logger.info("DatabaseWatcher stopped")

    async def _watch_with_inotify(self):
        """
        Native Linux inotify - very efficient
        Triggers immediately on DB write access
        """
        logger.info("Starting inotify watcher...")

        # Create inotify watcher in thread pool (blocking I/O)
        def watch_blocking():
            i = inotify.adapters.Inotify()

            # Watch DB file for changes
            watch_path = str(self.db_path.parent)
            i.add_watch(watch_path)

            logger.info(f"Watching: {watch_path}")
            logger.info("Waiting for DB changes...")

            for event in i.event_gen(yield_nones=False):
                if not self.running:
                    break

                (_, type_names, path, filename) = event

                # Only react to our DB file
                if filename == self.db_path.name:
                    # MODIFY = data written
                    # CLOSE_WRITE = write access completed
                    if 'IN_MODIFY' in type_names or 'IN_CLOSE_WRITE' in type_names:
                        logger.debug(f"DB changed: {type_names}")
                        return True  # Signal: change detected

            return False

        try:
            while self.running:
                # Execute blocking watch in thread
                loop = asyncio.get_running_loop()
                changed = await loop.run_in_executor(None, watch_blocking)

                if changed and self.running:
                    logger.info("=== DB change detected (inotify) ===")
                    try:
                        await self.callback()
                    except Exception as e:
                        logger.error(f"Error in callback: {e}", exc_info=True)

        except asyncio.CancelledError:
            logger.info("inotify watcher stopped")
        except Exception as e:
            logger.error(f"Error in inotify watcher: {e}", exc_info=True)

    async def _watch_with_polling(self):
        """
        Fallback: polling on mtime
        Less efficient, but works everywhere
        """
        logger.info("Starting polling watcher (every 5s)...")
        last_mtime = self.db_path.stat().st_mtime

        try:
            while self.running:
                await asyncio.sleep(5)  # Poll every 5 seconds

                if not self.running:
                    break

                try:
                    current_mtime = self.db_path.stat().st_mtime

                    if current_mtime > last_mtime:
                        logger.info("=== DB change detected (Polling) ===")
                        last_mtime = current_mtime

                        try:
                            await self.callback()
                        except Exception as e:
                            logger.error(f"Error in callback: {e}", exc_info=True)

                except OSError as e:
                    logger.error(f"Error checking DB: {e}")

        except asyncio.CancelledError:
            logger.info("Polling watcher stopped")