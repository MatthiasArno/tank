"""
Matplotlib Plot Exporter for Telegram Bot
Lightweight alternative to Kaleido (no Chrome required)
Optimized for RPi Lite OS
"""
import logging
from pathlib import Path
from datetime import datetime
from database.db_handler import DatabaseHandler
from utils.plot_generator_mpl import (
    create_30day_plot_mpl,
    create_7day_plot_mpl,
    create_30day_with_forecast_plot_mpl,
    create_forecast_plot_mpl
)

logger = logging.getLogger(__name__)


class PlotExporterMPL:
    """
    Matplotlib-based plot exporter
    No Chrome/Kaleido dependency - perfect for RPi Lite OS
    """

    def __init__(self, db_handler: DatabaseHandler, output_dir: str):
        self.db_handler = db_handler
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

        logger.info(f"PlotExporterMPL initialized. Output: {self.output_dir}")

    def export_30day_plot(self, file_path: str = None) -> str:
        """
        Exports 30-day view as PNG with matplotlib

        Args:
            file_path: Optional path for the PNG file

        Returns:
            str: Path to saved file or None on error
        """
        try:
            if not file_path:
                file_path = str(self.output_dir / "tank_30days_mpl.png")

            success = create_30day_plot_mpl(self.db_handler, file_path)

            if success:
                logger.info(f"MPL 30-day plot exported: {file_path}")
                return file_path
            else:
                logger.error("Error exporting MPL 30-day plot")
                return None

        except Exception as e:
            logger.error(f"Error exporting MPL 30-day plot: {e}", exc_info=True)
            return None

    def export_7day_plot(self, file_path: str = None) -> str:
        """
        Exports 7-day view as PNG with matplotlib

        Args:
            file_path: Optional path for the PNG file

        Returns:
            str: Path to saved file or None on error
        """
        try:
            if not file_path:
                file_path = str(self.output_dir / "tank_7days_mpl.png")

            success = create_7day_plot_mpl(self.db_handler, file_path)

            if success:
                logger.info(f"MPL 7-day plot exported: {file_path}")
                return file_path
            else:
                logger.error("Error exporting MPL 7-day plot")
                return None

        except Exception as e:
            logger.error(f"Error exporting MPL 7-day plot: {e}", exc_info=True)
            return None

    def export_forecast_plot(self, file_path: str = None, days: int = 30) -> str:
        """
        Exports forecast view as PNG with matplotlib

        Args:
            file_path: Optional path for the PNG file
            days: Number of forecast days (default: 30, uses what is available)

        Returns:
            str: Path to saved file or None on error
        """
        try:
            if not file_path:
                file_path = str(self.output_dir / "tank_forecast_mpl.png")

            success = create_forecast_plot_mpl(self.db_handler, file_path, days=days)

            if success:
                logger.info(f"MPL forecast plot exported: {file_path}")
                return file_path
            else:
                logger.error("Error exporting MPL forecast plot")
                return None

        except Exception as e:
            logger.error(f"Error exporting MPL forecast plot: {e}", exc_info=True)
            return None

    def export_30day_with_forecast_plot(self, file_path: str = None) -> str:
        """
        Exports 30-day view WITH forecast as PNG

        Args:
            file_path: Optional path for the PNG file

        Returns:
            str: Path to saved file or None on error
        """
        try:
            if not file_path:
                file_path = str(self.output_dir / "tank_30days_forecast_mpl.png")

            success = create_30day_with_forecast_plot_mpl(self.db_handler, file_path)

            if success:
                logger.info(f"MPL 30-day + forecast plot exported: {file_path}")
                return file_path
            else:
                logger.error("Error exporting MPL 30-day + forecast plot")
                return None

        except Exception as e:
            logger.error(f"Error exporting MPL 30-day + forecast plot: {e}", exc_info=True)
            return None

    def export_all_plots(self) -> bool:
        """
        Exports all views (30 days, 7 days, 30 days+forecast, forecast) as PNG
        With timestamp for archiving
        Includes forecast plots

        Returns:
            bool: True if successful, False on error
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        import shutil

        try:
            success_all = True

            # 30-day plot
            file_30 = self.output_dir / "tank_30days_mpl.png"
            file_30_ts = self.output_dir / f"tank_30days_mpl_{timestamp}.png"

            success_30 = create_30day_plot_mpl(self.db_handler, str(file_30))
            if success_30:
                shutil.copy2(file_30, file_30_ts)
                logger.info(f"30-day plot saved: {file_30}")
            else:
                success_all = False

            # 7-day plot
            file_7 = self.output_dir / "tank_7days_mpl.png"
            file_7_ts = self.output_dir / f"tank_7days_mpl_{timestamp}.png"

            success_7 = create_7day_plot_mpl(self.db_handler, str(file_7))
            if success_7:
                shutil.copy2(file_7, file_7_ts)
                logger.info(f"7-day plot saved: {file_7}")
            else:
                success_all = False

            # 30-day + forecast plot
            file_30f = self.output_dir / "tank_30days_forecast_mpl.png"
            file_30f_ts = self.output_dir / f"tank_30days_forecast_mpl_{timestamp}.png"

            success_30f = create_30day_with_forecast_plot_mpl(self.db_handler, str(file_30f))
            if success_30f:
                shutil.copy2(file_30f, file_30f_ts)
                logger.info(f"30-day + forecast plot saved: {file_30f}")
            else:
                # Forecast is optional, so don't count as error
                logger.warning("30-day + forecast plot could not be created (optional)")

            # Forecast plot (standalone)
            file_fc = self.output_dir / "tank_forecast_mpl.png"
            file_fc_ts = self.output_dir / f"tank_forecast_mpl_{timestamp}.png"

            success_fc = create_forecast_plot_mpl(self.db_handler, str(file_fc), days=30)
            if success_fc:
                shutil.copy2(file_fc, file_fc_ts)
                logger.info(f"Forecast plot saved: {file_fc}")
            else:
                # Forecast is optional, so don't count as error
                logger.warning("Forecast plot could not be created (optional)")

            return success_all  # Only 30 and 7 days are critical

        except Exception as e:
            logger.error(f"Error exporting MPL plots: {e}", exc_info=True)
            return False