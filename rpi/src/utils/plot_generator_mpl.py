"""
Matplotlib Plot Generator for tank visualizations
Lightweight alternative to Plotly for RPi without Chrome/Kaleido
Specially optimized for Telegram Bot PNG export
"""
import logging
import matplotlib
matplotlib.use('Agg')  # Non-GUI backend for headless
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from datetime import datetime
from database.db_handler import DatabaseHandler
from utils.forecast import get_forecast_data
import config

logger = logging.getLogger(__name__)

# Sensor colors
SENSOR_COLORS = {
    '2-ABV': '#FF0000',  # Red (Old Building Flow)
    '3-ABR': '#FFA500',  # Orange (Old Building Return)
    '4-NBV': '#0000FF',  # Blue (New Building Flow)
    '5-NBR': '#ADD8E6',  # Light Blue (New Building Return)
    '1-AUS': '#808080',  # Gray (Outside Temperature)
}


def create_30day_plot_mpl(db_handler: DatabaseHandler, output_path: str) -> bool:
    """
    Creates 30-day view with matplotlib
   
    Args:
        db_handler: DatabaseHandler instance
        output_path: Path for PNG file

    Returns:
        bool: True if successful
    """
    try:
        # Get data
        temp_data = db_handler.get_daily_temp_minmax(days=30)
        level_data = db_handler.get_daily_level_median(days=30)

        logger.info(f"MPL 30-day: {len(temp_data)} Temp, {len(level_data)} Level")

        # Figure with 2 subplots
        fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 8))
        fig.suptitle('Tank Monitoring - 30 Days', fontsize=14, fontweight='bold')

        # === Temperatures (top) ===
        ax1.set_title('Temperatures (Min/Max)', fontsize=11)
        ax1.set_ylabel('Temperature (°C)')
        ax1.grid(True, axis='y', linestyle='-', linewidth=0.5, color='lightgray', alpha=0.7)
        ax1.yaxis.set_major_locator(plt.MultipleLocator(10))  # Grid every 10 degrees

        # Process temperature data by sensor
        temp_by_sensor = {}
        for date, sensor, temp_min, temp_max in temp_data:
            if sensor not in temp_by_sensor:
                temp_by_sensor[sensor] = {'dates': [], 'min': [], 'max': []}
            # Convert date string to datetime
            dt = datetime.strptime(date, '%Y-%m-%d')
            temp_by_sensor[sensor]['dates'].append(dt)
            temp_by_sensor[sensor]['min'].append(temp_min / 10.0)
            temp_by_sensor[sensor]['max'].append(temp_max / 10.0)

        # Plot temperatures
        for sensor, data in sorted(temp_by_sensor.items()):
            color = SENSOR_COLORS.get(sensor, '#808080')

            # Min line (dashed)
            ax1.plot(data['dates'], data['min'],
                    label=f'{sensor} Min',
                    color=color,
                    linestyle='--',
                    linewidth=1.5,
                    marker='o',
                    markersize=4,
                    alpha=0.7)

            # Max line (solid)
            ax1.plot(data['dates'], data['max'],
                    label=f'{sensor} Max',
                    color=color,
                    linestyle='-',
                    linewidth=2,
                    marker='o',
                    markersize=4)

        ax1.legend(loc='upper left', fontsize=8, ncol=2)
        ax1.xaxis.set_major_formatter(mdates.DateFormatter('%d.%m'))
        ax1.xaxis.set_major_locator(mdates.DayLocator(interval=3))
        plt.setp(ax1.xaxis.get_majorticklabels(), rotation=45, ha='right')

        # === Tank Level (bottom) ===
        ax2.set_title('Tank Level (Median)', fontsize=11)
        ax2.set_xlabel('Date')
        ax2.set_ylabel('Tank Level (mm)')
        ax2.grid(True, axis='y', linestyle='-', linewidth=0.5, color='lightgray', alpha=0.7)
        ax2.yaxis.set_major_locator(plt.MultipleLocator(100))  # Grid every 100 mm

        if level_data:
            dates = [datetime.strptime(row[0], '%Y-%m-%d') for row in level_data]
            levels = [row[1] for row in level_data]

            ax2.plot(dates, levels,
                    label='Tank Level (Median)',
                    color='#008000',
                    linewidth=2,
                    marker='o',
                    markersize=4)
            ax2.fill_between(dates, 0, levels, color='#008000', alpha=0.2)
            ax2.legend(loc='upper left', fontsize=8)

        ax2.xaxis.set_major_formatter(mdates.DateFormatter('%d.%m'))
        ax2.xaxis.set_major_locator(mdates.DayLocator(interval=3))
        plt.setp(ax2.xaxis.get_majorticklabels(), rotation=45, ha='right')

        # Optimize layout
        plt.tight_layout()

        # Save
        plt.savefig(output_path, dpi=150, bbox_inches='tight')
        plt.close(fig)

        logger.info(f"MPL 30-day plot saved: {output_path}")
        return True

    except Exception as e:
        logger.error(f"Error creating MPL 30-day plot: {e}", exc_info=True)
        return False


def create_7day_plot_mpl(db_handler: DatabaseHandler, output_path: str) -> bool:
    """
    Creates 7-day view with matplotlib
    

    Args:
        db_handler: DatabaseHandler instance
        output_path: Path for PNG file

    Returns:
        bool: True if successful
    """
    try:
        # Get data
        temp_data = db_handler.get_hourly_temps(days=7)
        level_data = db_handler.get_hourly_level_median(days=7)

        logger.info(f"MPL 7-day: {len(temp_data)} Temp, {len(level_data)} Level")

        # Figure with 2 subplots
        fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 8))
        fig.suptitle('Tank Monitoring - 7 Days', fontsize=14, fontweight='bold')

        # === Temperatures (top) ===
        ax1.set_title('Temperatures (All Values)', fontsize=11)
        ax1.set_ylabel('Temperature (°C)')
        ax1.grid(True, axis='y', linestyle='-', linewidth=0.5, color='lightgray', alpha=0.7)
        ax1.yaxis.set_major_locator(plt.MultipleLocator(10))  # Grid every 10 degrees

        # Process temperature data by sensor
        temp_by_sensor = {}
        for timestamp, sensor, temperature in temp_data:
            if sensor not in temp_by_sensor:
                temp_by_sensor[sensor] = {'timestamps': [], 'temps': []}
            # Convert timestamp string to datetime
            dt = datetime.strptime(timestamp, '%Y-%m-%d %H:%M:%S')
            temp_by_sensor[sensor]['timestamps'].append(dt)
            temp_by_sensor[sensor]['temps'].append(temperature / 10.0)

        # Plot temperatures
        for sensor, data in sorted(temp_by_sensor.items()):
            color = SENSOR_COLORS.get(sensor, '#808080')

            ax1.plot(data['timestamps'], data['temps'],
                    label=sensor,
                    color=color,
                    linestyle='-',
                    linewidth=1.5,
                    marker='o',
                    markersize=4)

        ax1.legend(loc='upper left', fontsize=8, ncol=3)
        ax1.xaxis.set_major_formatter(mdates.DateFormatter('%d.%m %H:%M'))
        ax1.xaxis.set_major_locator(mdates.DayLocator())
        plt.setp(ax1.xaxis.get_majorticklabels(), rotation=45, ha='right')

        # === Tank Level (bottom) ===
        ax2.set_title('Tank Level (Median)', fontsize=11)
        ax2.set_xlabel('Date/Time')
        ax2.set_ylabel('Tank Level (mm)')
        ax2.grid(True, axis='y', linestyle='-', linewidth=0.5, color='lightgray', alpha=0.7)
        ax2.yaxis.set_major_locator(plt.MultipleLocator(100))  # Grid every 100 mm

        if level_data:
            timestamps = [datetime.strptime(row[0], '%Y-%m-%d %H:%M:%S') for row in level_data]
            levels = [row[1] for row in level_data]

            ax2.plot(timestamps, levels,
                    label='Tank Level (Median)',
                    color='#008000',
                    linewidth=1.5,
                    marker='o',
                    markersize=4)
            ax2.fill_between(timestamps, 0, levels, color='#008000', alpha=0.2)
            ax2.legend(loc='upper left', fontsize=8)

        ax2.xaxis.set_major_formatter(mdates.DateFormatter('%d.%m %H:%M'))
        ax2.xaxis.set_major_locator(mdates.DayLocator())
        plt.setp(ax2.xaxis.get_majorticklabels(), rotation=45, ha='right')

        # Optimize layout
        plt.tight_layout()

        # Save
        plt.savefig(output_path, dpi=150, bbox_inches='tight')
        plt.close(fig)

        logger.info(f"MPL 7-day plot saved: {output_path}")
        return True

    except Exception as e:
        logger.error(f"Error creating MPL 7-day plot: {e}", exc_info=True)
        return False


def create_forecast_plot_mpl(db_handler: DatabaseHandler, output_path: str, days: int = 30) -> bool:
    """
    Creates forecast diagram with matplotlib
    30-day forecast in 30-day view

    Args:
        db_handler: DatabaseHandler instance
        output_path: Path for PNG file
        days: Number of forecast days (default: 30, uses what is available)

    Returns:
        bool: True if successful
    """
    try:
        # Get current tank level (last value from DB)
        level_data = db_handler.get_hourly_level_median(days=1)
        if not level_data:
            logger.warning("No current tank level available for forecast")
            return False

        current_level = level_data[-1][1]  # Last level value
        current_date_str = level_data[-1][0].split(' ')[0]  # Date without time

        logger.info(f"Current tank level: {current_level:.1f}mm on {current_date_str}")

        # Get regression parameters from config (loaded from .env)
        regression_k = config.REGRESSION_K
        regression_c = config.REGRESSION_C

        if regression_k == 0.0 and regression_c == 0.0:
            logger.warning("No regression parameters available. Please run statistic_db.py first!")
            # Create plot with warning
            fig, ax = plt.subplots(figsize=(12, 6))
            ax.text(0.5, 0.5,
                   'No regression parameters available!\n\n'
                   'Please run statistic_db.py first\n'
                   'to generate REGRESSION_K and REGRESSION_C.',
                   ha='center', va='center',
                   fontsize=14, color='red',
                   transform=ax.transAxes)
            ax.set_title('Forecast', fontsize=14, fontweight='bold')
            ax.axis('off')
            plt.tight_layout()
            plt.savefig(output_path, dpi=150, bbox_inches='tight')
            plt.close(fig)
            return True

        # F-FORE-110-140: Get forecast data
        forecast_data, metadata = get_forecast_data(
            current_level=current_level,
            days=days,
            regression_k=regression_k,
            regression_c=regression_c
        )

        if not forecast_data:
            logger.warning("Forecast data could not be calculated")
            return False

        logger.info(f"Forecast plot: {len(forecast_data)} days")

        # F-FORE-160-200: Create plot with dual axis
        fig, ax1 = plt.subplots(figsize=(12, 6))
        fig.suptitle('Tank Level Forecast', fontsize=14, fontweight='bold')

        # First value is current tank level
        # Add current point
        dates = [datetime.strptime(current_date_str, '%Y-%m-%d')]
        levels = [current_level]
        temps = []

        # Add forecast data
        # New structure: (date_str, level, temp, daily_consumption)
        for item in forecast_data:
            date_str = item[0]
            level = item[1]
            temp = item[2]
            dates.append(datetime.strptime(date_str, '%Y-%m-%d'))
            levels.append(level)
            temps.append(temp)

        # Y-axis tank level in mm
        ax1.set_xlabel('Date', fontsize=11)
        ax1.set_ylabel('Tank Level (mm)', fontsize=11, color='green')
        ax1.plot(dates, levels,
                color='#008000',
                linewidth=2,
                marker='o',
                markersize=6,
                label='Tank Level Forecast')

        # Mark current value specially
        ax1.plot(dates[0], levels[0],
                color='red',
                marker='o',
                markersize=10,
                label='Current Tank Level',
                zorder=10)

        # Y-axis goes up to 1500mm
        ax1.set_ylim(0, 1500)
        ax1.tick_params(axis='y', labelcolor='green')
        ax1.grid(True, axis='y', linestyle='-', linewidth=0.5, color='lightgray', alpha=0.7)
        ax1.yaxis.set_major_locator(plt.MultipleLocator(100))

        # Red warning line at WARN_LEVEL_TANK
        warn_level = metadata.get('warn_level', config.WARN_LEVEL_TANK)
        ax1.axhline(y=warn_level, color='red', linestyle='--', linewidth=2,
                   label=f'Warning level ({warn_level:.0f}mm)', zorder=5)

        # Second Y-axis on right for temperature
        ax2 = ax1.twinx()
        ax2.set_ylabel('Temperature (°C)', fontsize=11, color='blue')

        # Temperature line (only for forecast data, not for current point)
        if temps:
            ax2.plot(dates[1:], temps,
                    color='#0000FF',
                    linewidth=2,
                    linestyle='--',
                    marker='s',
                    markersize=4,
                    label='Forecast Temperature',
                    alpha=0.7)

        ax2.tick_params(axis='y', labelcolor='blue')
        ax2.grid(False)

        # Format X-axis
        ax1.xaxis.set_major_formatter(mdates.DateFormatter('%d.%m'))
        ax1.xaxis.set_major_locator(mdates.DayLocator(interval=2))
        plt.setp(ax1.xaxis.get_majorticklabels(), rotation=45, ha='right')

        # Combine legends
        lines1, labels1 = ax1.get_legend_handles_labels()
        lines2, labels2 = ax2.get_legend_handles_labels()
        ax1.legend(lines1 + lines2, labels1 + labels2, loc='upper right', fontsize=9)

        # Annotation AT THE LAST DATA POINT with best/worst case
        date_warn_best = metadata.get('date_at_warn_best')
        date_warn_worst = metadata.get('date_at_warn_worst')
        dh_min = metadata.get('dh_min', 0)
        dh_max = metadata.get('dh_max', 0)

        if date_warn_best and date_warn_worst and dates and levels:
            # Position at last forecast data point
            last_date = dates[-1]
            last_level = levels[-1]

            # Format dates
            best_obj = datetime.strptime(date_warn_best, '%Y-%m-%d')
            worst_obj = datetime.strptime(date_warn_worst, '%Y-%m-%d')

            anno_text = f"{config.WARN_LEVEL_TANK:.0f}mm reached:\nBest: {best_obj.strftime('%d.%m.%Y')}\nWorst: {worst_obj.strftime('%d.%m.%Y')}"

            # Annotation with arrow at last point
            ax1.annotate(anno_text,
                        xy=(last_date, last_level),
                        xytext=(15, 25),
                        textcoords='offset points',
                        fontsize=12,
                        bbox=dict(boxstyle='round,pad=0.5', facecolor='yellow', alpha=0.8, edgecolor='black', linewidth=1.5),
                        arrowprops=dict(arrowstyle='->', color='black', lw=2),
                        zorder=20)

        # Info text at bottom
        annotation_text = (f"Regression: Consumption = {regression_k:.4f} * T + {regression_c:.4f}\n"
                          f"Start: {current_level:.1f}mm, End: {levels[-1]:.1f}mm\n"
                          f"dHMin: {dh_min:.2f}mm/day, dHMax: {dh_max:.2f}mm/day")
        fig.text(0.5, 0.02, annotation_text, ha='center', fontsize=8, style='italic')

        # Optimize layout
        plt.tight_layout()

        # Save as PNG (no PDF!)
        plt.savefig(output_path, dpi=150, bbox_inches='tight')
        plt.close(fig)

        logger.info(f"Forecast plot saved: {output_path}")
        return True

    except Exception as e:
        logger.error(f"Error creating forecast plot: {e}", exc_info=True)
        return False


def create_30day_with_forecast_plot_mpl(db_handler: DatabaseHandler, output_path: str) -> bool:
    """
    Creates 30-day view WITH forecast as 3rd diagram

    Combines:
    - Top: Temperatures (30-day Min/Max)
    - Middle: Tank Level (30 days)
    - Bottom: Forecast (30 days, as far as available)

    Args:
        db_handler: DatabaseHandler instance
        output_path: Path for PNG file

    Returns:
        bool: True if successful
    """
    try:
        # Get data for 30-day view
        temp_data = db_handler.get_daily_temp_minmax(days=30)
        level_data = db_handler.get_daily_level_median(days=30)

        logger.info(f"30-day with forecast: {len(temp_data)} Temp, {len(level_data)} Level")

        # Figure with 3 subplots (Temp, Level, Forecast)
        fig, (ax1, ax2, ax3) = plt.subplots(3, 1, figsize=(14, 12))
        fig.suptitle('Tank Monitoring - 30 Days + Forecast', fontsize=14, fontweight='bold')

        # === 1. Temperatures (top) ===
        ax1.set_title('Temperatures (Min/Max)', fontsize=11)
        ax1.set_ylabel('Temperature (°C)')
        ax1.grid(True, axis='y', linestyle='-', linewidth=0.5, color='lightgray', alpha=0.7)
        ax1.yaxis.set_major_locator(plt.MultipleLocator(10))

        temp_by_sensor = {}
        for date, sensor, temp_min, temp_max in temp_data:
            if sensor not in temp_by_sensor:
                temp_by_sensor[sensor] = {'dates': [], 'min': [], 'max': []}
            dt = datetime.strptime(date, '%Y-%m-%d')
            temp_by_sensor[sensor]['dates'].append(dt)
            temp_by_sensor[sensor]['min'].append(temp_min / 10.0)
            temp_by_sensor[sensor]['max'].append(temp_max / 10.0)

        for sensor, data in sorted(temp_by_sensor.items()):
            color = SENSOR_COLORS.get(sensor, '#808080')
            ax1.plot(data['dates'], data['min'],
                    label=f'{sensor} Min', color=color, linestyle='--',
                    linewidth=1.5, marker='o', markersize=6, alpha=0.7)
            ax1.plot(data['dates'], data['max'],
                    label=f'{sensor} Max', color=color, linestyle='-',
                    linewidth=2, marker='o', markersize=6)

        ax1.legend(loc='upper left', fontsize=8, ncol=2)
        ax1.xaxis.set_major_formatter(mdates.DateFormatter('%d.%m'))
        ax1.xaxis.set_major_locator(mdates.DayLocator(interval=3))
        plt.setp(ax1.xaxis.get_majorticklabels(), rotation=45, ha='right')

        # === 2. Tank Level (middle) ===
        ax2.set_title('Tank Level (Median)', fontsize=11)
        ax2.set_ylabel('Tank Level (mm)')
        ax2.grid(True, axis='y', linestyle='-', linewidth=0.5, color='lightgray', alpha=0.7)
        ax2.yaxis.set_major_locator(plt.MultipleLocator(100))

        if level_data:
            dates = [datetime.strptime(row[0], '%Y-%m-%d') for row in level_data]
            levels = [row[1] for row in level_data]
            ax2.plot(dates, levels,
                    label='Tank Level (Median)', color='#008000',
                    linewidth=2, marker='o', markersize=6)
            ax2.fill_between(dates, 0, levels, color='#008000', alpha=0.2)
            ax2.legend(loc='upper left', fontsize=8)

        ax2.xaxis.set_major_formatter(mdates.DateFormatter('%d.%m'))
        ax2.xaxis.set_major_locator(mdates.DayLocator(interval=3))
        plt.setp(ax2.xaxis.get_majorticklabels(), rotation=45, ha='right')

        # === 3. Forecast (bottom) ===
        ax3.set_title('Tank Level Forecast', fontsize=11)
        ax3.set_xlabel('Date')
        ax3.set_ylabel('Tank Level (mm)', fontsize=10, color='green')

        # Get current tank level
        current_level_data = db_handler.get_hourly_level_median(days=1)
        if current_level_data:
            current_level = current_level_data[-1][1]
            current_date_str = current_level_data[-1][0].split(' ')[0]

            # Get regression parameters
            regression_k = config.REGRESSION_K
            regression_c = config.REGRESSION_C

            if regression_k != 0.0 or regression_c != 0.0:
                # Get forecast data (30 days, use what is available)
                forecast_data, fc_metadata = get_forecast_data(
                    current_level=current_level,
                    days=30,
                    regression_k=regression_k,
                    regression_c=regression_c
                )

                if forecast_data:
                    # Add current point
                    f_dates = [datetime.strptime(current_date_str, '%Y-%m-%d')]
                    f_levels = [current_level]
                    f_temps = []

                    # New structure: (date_str, level, temp, daily_consumption)
                    for item in forecast_data:
                        date_str = item[0]
                        level = item[1]
                        temp = item[2]
                        f_dates.append(datetime.strptime(date_str, '%Y-%m-%d'))
                        f_levels.append(level)
                        f_temps.append(temp)

                    # Tank level line
                    ax3.plot(f_dates, f_levels,
                            color='#008000', linewidth=2,
                            marker='o', markersize=5,
                            label='Tank Level Forecast')
                    ax3.plot(f_dates[0], f_levels[0],
                            color='red', marker='o', markersize=4,
                            label='Current', zorder=10)

                    ax3.set_ylim(0, 1500)
                    ax3.tick_params(axis='y', labelcolor='green')
                    ax3.grid(True, axis='y', linestyle='-', linewidth=0.5,
                            color='lightgray', alpha=0.7)
                    ax3.yaxis.set_major_locator(plt.MultipleLocator(100))

                    # Red warning line at WARN_LEVEL_TANK
                    warn_level = fc_metadata.get('warn_level', config.WARN_LEVEL_TANK)
                    ax3.axhline(y=warn_level, color='red', linestyle='--', linewidth=2,
                               label=f'Warning level ({warn_level:.0f}mm)', zorder=5)

                    # Second Y-axis for temperature
                    ax3_temp = ax3.twinx()
                    ax3_temp.set_ylabel('Temperature (°C)', fontsize=10, color='blue')
                    if f_temps:
                        ax3_temp.plot(f_dates[1:], f_temps,
                                    color='#0000FF', linewidth=2,
                                    linestyle='--', marker='s',
                                    markersize=4,
                                    label='Forecast Temperature',
                                    alpha=0.7)
                    ax3_temp.tick_params(axis='y', labelcolor='blue')
                    ax3_temp.grid(False)

                    # Combined legend
                    lines1, labels1 = ax3.get_legend_handles_labels()
                    lines2, labels2 = ax3_temp.get_legend_handles_labels()
                    ax3.legend(lines1 + lines2, labels1 + labels2,
                             loc='upper right', fontsize=8)

                    # Annotation AT THE LAST DATA POINT
                    date_warn_best = fc_metadata.get('date_at_warn_best')
                    date_warn_worst = fc_metadata.get('date_at_warn_worst')
                    if date_warn_best and date_warn_worst and f_dates and f_levels:
                        # Last forecast point
                        last_date = f_dates[-1]
                        last_level = f_levels[-1]

                        # Format dates
                        best_obj = datetime.strptime(date_warn_best, '%Y-%m-%d')
                        worst_obj = datetime.strptime(date_warn_worst, '%Y-%m-%d')

                        anno_text = f"{config.WARN_LEVEL_TANK:.0f}mm reached:\nBest: {best_obj.strftime('%d.%m.%Y')}\nWorst: {worst_obj.strftime('%d.%m.%Y')}"

                        # Annotation at last point
                        ax3.annotate(anno_text,
                                    xy=(last_date, last_level),
                                    xytext=(15, 25),
                                    textcoords='offset points',
                                    fontsize=8,
                                    bbox=dict(boxstyle='round,pad=0.5', facecolor='yellow', alpha=0.8, edgecolor='black', linewidth=1.5),
                                    arrowprops=dict(arrowstyle='->', color='black', lw=2),
                                    zorder=20)
                else:
                    ax3.text(0.5, 0.5, 'Forecast data not available',
                           ha='center', va='center',
                           transform=ax3.transAxes)
            else:
                ax3.text(0.5, 0.5,
                       'No regression parameters\nPlease run statistic_db.py',
                       ha='center', va='center',
                       transform=ax3.transAxes, color='red')
        else:
            ax3.text(0.5, 0.5, 'No current tank level available',
                   ha='center', va='center',
                   transform=ax3.transAxes)

        ax3.xaxis.set_major_formatter(mdates.DateFormatter('%d.%m'))
        ax3.xaxis.set_major_locator(mdates.DayLocator(interval=2))
        plt.setp(ax3.xaxis.get_majorticklabels(), rotation=45, ha='right')

        # Optimize layout
        plt.tight_layout()

        # Save
        plt.savefig(output_path, dpi=150, bbox_inches='tight')
        plt.close(fig)

        logger.info(f"30-day + forecast plot saved: {output_path}")
        return True

    except Exception as e:
        logger.error(f"Error creating 30-day + forecast plot: {e}", exc_info=True)
        return False
    