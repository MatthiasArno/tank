"""
Plot Exporter for automatic saving of visualizations
Saves 30-day and 7-day views after each DB update
Uses plot_generator for plot creation (reusable logic)
"""
import logging
from pathlib import Path
from datetime import datetime
from database.db_handler import DatabaseHandler
from utils.plot_generator import create_30day_plot, create_7day_plot

logger = logging.getLogger(__name__)


class PlotExporter:
    """
    Exports plots as PNG files for messenger delivery
    Uses plot_generator for plot creation (DRY principle)
    """

    def __init__(self, db_handler: DatabaseHandler, output_dir: str):
        self.db_handler = db_handler
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

        logger.info(f"PlotExporter initialized. Output: {self.output_dir}")

    def export_all_plots(self):
        """
        Exports both views (30 and 7 days) as PNG
        Call after each DB update

        Returns:
            bool: True if successful, False on error
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        try:
            # Export 30-day plot
            fig_30 = create_30day_plot(self.db_handler)
            # Optimize layout for PNG export
            fig_30.update_layout(width=1200, height=800)

            file_30 = self.output_dir / "tank_30days.png"
            file_30_timestamped = self.output_dir / f"tank_30days_{timestamp}.png"

            fig_30.write_image(str(file_30))
            fig_30.write_image(str(file_30_timestamped))
            logger.info(f"30-day plot saved: {file_30}")

            # Export 7-day plot
            fig_7 = create_7day_plot(self.db_handler)
            # Optimize layout for PNG export
            fig_7.update_layout(width=1200, height=800)

            file_7 = self.output_dir / "tank_7days.png"
            file_7_timestamped = self.output_dir / f"tank_7days_{timestamp}.png"

            fig_7.write_image(str(file_7))
            fig_7.write_image(str(file_7_timestamped))
            logger.info(f"7-day plot saved: {file_7}")

            return True

        except Exception as e:
            logger.error(f"Error exporting plots: {e}")
            return False

    def export_30day_plot(self, file_path: str = None):
        """
        Exports only the 30-day view
        For Telegram service or manual use

        Args:
            file_path: Optional path for the PNG file

        Returns:
            str: Path to saved file or None on error
        """
        try:
            fig = create_30day_plot(self.db_handler)
            fig.update_layout(width=1200, height=800)

            if not file_path:
                file_path = str(self.output_dir / "tank_30days.png")

            fig.write_image(file_path)
            logger.info(f"30-day plot exported: {file_path}")
            return file_path

        except Exception as e:
            logger.error(f"Error exporting 30-day plot: {e}")
            return None

    def export_7day_plot(self, file_path: str = None):
        """
        Exports only the 7-day view
        For Telegram service or manual use

        Args:
            file_path: Optional path for the PNG file

        Returns:
            str: Path to saved file or None on error
        """
        try:
            fig = create_7day_plot(self.db_handler)
            fig.update_layout(width=1200, height=800)

            if not file_path:
                file_path = str(self.output_dir / "tank_7days.png")

            fig.write_image(file_path)
            logger.info(f"7-day plot exported: {file_path}")
            return file_path

        except Exception as e:
            logger.error(f"Error exporting 7-day plot: {e}")
            return None
        