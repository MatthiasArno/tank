"""
Plot Generator for Tank Visualizations
Reusable plot creation logic for Dashboard, Export and Telegram Service
"""
import logging
import plotly.graph_objects as go
from plotly.subplots import make_subplots
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


def create_30day_plot(db_handler: DatabaseHandler):
    """
    Creates 30-day view with Min/Max temperatures and tank level
    
    Args:
        db_handler: DatabaseHandler instance

    Returns:
        plotly.graph_objects.Figure
    """
    # Get data
    temp_data = db_handler.get_daily_temp_minmax(days=30)
    level_data = db_handler.get_daily_level_median(days=30)

    logger.info(f"30-day view: {len(temp_data)} temp entries, {len(level_data)} level entries")

    # Create subplots: 2 rows (Temperature top, Tank level bottom)
    fig = make_subplots(
        rows=2, cols=1,
        subplot_titles=('Temperatures (30 Days - Min/Max)', 'Tank Level (30 Days)'),
        vertical_spacing=0.12,
        row_heights=[0.6, 0.4]
    )

    # Process temperature data by sensor
    temp_by_sensor = {}
    for date, sensor, temp_min, temp_max in temp_data:
        if sensor not in temp_by_sensor:
            temp_by_sensor[sensor] = {'dates': [], 'min': [], 'max': []}
        temp_by_sensor[sensor]['dates'].append(date)
        temp_by_sensor[sensor]['min'].append(temp_min / 10.0)  # 1/10 degree -> degree
        temp_by_sensor[sensor]['max'].append(temp_max / 10.0)

    # Add temperature lines
    for sensor, data in sorted(temp_by_sensor.items()):
        color = SENSOR_COLORS.get(sensor, '#808080')

        # Min line (dashed)
        fig.add_trace(
            go.Scatter(
                x=data['dates'],
                y=data['min'],
                name=f'{sensor} Min',
                line=dict(color=color, dash='dot', width=2),
                mode='lines+markers',
                marker=dict(size=6, symbol='circle')
            ),
            row=1, col=1
        )

        # Max line (solid)
        fig.add_trace(
            go.Scatter(
                x=data['dates'],
                y=data['max'],
                name=f'{sensor} Max',
                line=dict(color=color, width=3),
                mode='lines+markers',
                marker=dict(size=6, symbol='circle')
            ),
            row=1, col=1
        )

    # Add tank level
    if level_data:
        dates = [row[0] for row in level_data]
        levels = [row[1] for row in level_data]

        fig.add_trace(
            go.Scatter(
                x=dates,
                y=levels,
                name='Tank Level (Median)',
                line=dict(color='#008000', width=3),
                mode='lines+markers',
                marker=dict(size=6, symbol='circle'),
                fill='tozeroy'
            ),
            row=2, col=1
        )

    # Adjust layout
    fig.update_xaxes(title_text="Date", row=1, col=1)
    fig.update_yaxes(
        title_text="Temperature (°C)",
        row=1, col=1,
        dtick=10,  # Grid lines every 10 degrees
        showgrid=True,
        gridcolor='lightgray',
        gridwidth=1
    )
    fig.update_xaxes(title_text="Date", row=2, col=1)
    fig.update_yaxes(
        title_text="Tank Level (mm)",
        row=2, col=1,
        dtick=100,  # Grid lines every 100 mm
        showgrid=True,
        gridcolor='lightgray',
        gridwidth=1
    )

    fig.update_layout(
        height=800,
        showlegend=True,
        hovermode='x unified',
        plot_bgcolor='white',
        paper_bgcolor='white'
    )

    # Note if few data points
    if len(temp_data) < 5:
        fig.add_annotation(
            text=f"ℹ️ Only {len(temp_data)} temp data point(s) - markers enlarged",
            xref="paper", yref="paper",
            x=0.5, y=1.08,
            showarrow=False,
            font=dict(size=12, color="blue"),
            xanchor='center'
        )

    return fig


def create_7day_plot(db_handler: DatabaseHandler):
    """
    Creates 7-day view with all temperature values and tank level
   

    Args:
        db_handler: DatabaseHandler instance

    Returns:
        plotly.graph_objects.Figure
    """
    # Get data
    temp_data = db_handler.get_hourly_temps(days=7)
    level_data = db_handler.get_hourly_level_median(days=7)

    logger.info(f"7-day view: {len(temp_data)} temp entries, {len(level_data)} level entries")

    # Create subplots
    fig = make_subplots(
        rows=2, cols=1,
        subplot_titles=('Temperatures (7 Days - All Values)', 'Tank Level (7 Days)'),
        vertical_spacing=0.12,
        row_heights=[0.6, 0.4]
    )

    # Process temperature data by sensor
    temp_by_sensor = {}
    for timestamp, sensor, temperature in temp_data:
        if sensor not in temp_by_sensor:
            temp_by_sensor[sensor] = {'timestamps': [], 'temps': []}
        temp_by_sensor[sensor]['timestamps'].append(timestamp)
        temp_by_sensor[sensor]['temps'].append(temperature / 10.0)  # 1/10 degree -> degree

    # Add temperature lines (only solid lines)
    for sensor, data in sorted(temp_by_sensor.items()):
        color = SENSOR_COLORS.get(sensor, '#808080')

        fig.add_trace(
            go.Scatter(
                x=data['timestamps'],
                y=data['temps'],
                name=sensor,
                line=dict(color=color, width=2),
                mode='lines+markers',
                marker=dict(size=10, symbol='circle')
            ),
            row=1, col=1
        )

    # Add tank level
    if level_data:
        timestamps = [row[0] for row in level_data]
        levels = [row[1] for row in level_data]

        fig.add_trace(
            go.Scatter(
                x=timestamps,
                y=levels,
                name='Tank Level (Median)',
                line=dict(color='#008000', width=2),
                mode='lines+markers',
                marker=dict(size=10, symbol='circle'),
                fill='tozeroy'
            ),
            row=2, col=1
        )

    # Adjust layout
    fig.update_xaxes(title_text="Date/Time", row=1, col=1)
    fig.update_yaxes(
        title_text="Temperature (°C)",
        row=1, col=1,
        dtick=10,  # Grid lines every 10 degrees
        showgrid=True,
        gridcolor='lightgray',
        gridwidth=1
    )
    fig.update_xaxes(title_text="Date/Time", row=2, col=1)
    fig.update_yaxes(
        title_text="Tank Level (mm)",
        row=2, col=1,
        dtick=100,  # Grid lines every 100 mm
        showgrid=True,
        gridcolor='lightgray',
        gridwidth=1
    )

    fig.update_layout(
        height=800,
        showlegend=True,
        hovermode='x unified',
        plot_bgcolor='white',
        paper_bgcolor='white'
    )

    # Note if few data points
    if len(temp_data) < 10:
        fig.add_annotation(
            text=f"ℹ️ Only {len(temp_data)} temp data point(s) - markers enlarged",
            xref="paper", yref="paper",
            x=0.5, y=1.08,
            showarrow=False,
            font=dict(size=12, color="blue"),
            xanchor='center'
        )

    return fig


def create_30day_html(db_handler: DatabaseHandler) -> str:
    """
    Creates 30-day view as HTML (for Dashboard)

    Args:
        db_handler: DatabaseHandler instance

    Returns:
        HTML String
    """
    fig = create_30day_plot(db_handler)
    return fig.to_html(full_html=False, include_plotlyjs='cdn')


def create_7day_html(db_handler: DatabaseHandler) -> str:
    """
    Creates 7-day view as HTML (for Dashboard)

    Args:
        db_handler: DatabaseHandler instance

    Returns:
        HTML String
    """
    fig = create_7day_plot(db_handler)
    return fig.to_html(full_html=False, include_plotlyjs='cdn')


def create_forecast_plot(db_handler: DatabaseHandler, days: int = 30):
    """
    F-FORE-160-200: Creates forecast diagram with Plotly
    Forecast view

    Args:
        db_handler: DatabaseHandler instance
        days: Number of forecast days (default: 30, uses what is available)

    Returns:
        plotly.graph_objects.Figure
    """
    # Get current tank level (last value from DB)
    level_data = db_handler.get_hourly_level_median(days=1)
    if not level_data:
        logger.warning("No current tank level available for forecast")
        # Create empty plot with warning
        fig = go.Figure()
        fig.add_annotation(
            text="No current tank level available",
            xref="paper", yref="paper",
            x=0.5, y=0.5,
            showarrow=False,
            font=dict(size=16, color="red")
        )
        return fig

    current_level = level_data[-1][1]
    current_date_str = level_data[-1][0].split(' ')[0]

    logger.info(f"Current tank level: {current_level:.1f}mm on {current_date_str}")

    # Get regression parameters from config
    regression_k = config.REGRESSION_K
    regression_c = config.REGRESSION_C

    if regression_k == 0.0 and regression_c == 0.0:
        logger.warning("No regression parameters available")
        fig = go.Figure()
        fig.add_annotation(
            text="No regression parameters available!<br><br>"
                 "Please run statistic_db.py first<br>"
                 "to generate REGRESSION_K and REGRESSION_C.",
            xref="paper", yref="paper",
            x=0.5, y=0.5,
            showarrow=False,
            font=dict(size=14, color="red")
        )
        fig.update_layout(
            title="Forecast",
            height=400,
            plot_bgcolor='white',
            paper_bgcolor='white'
        )
        return fig

    # F-FORE-110-140: Get forecast data
    forecast_data, metadata = get_forecast_data(
        current_level=current_level,
        days=days,
        regression_k=regression_k,
        regression_c=regression_c
    )

    if not forecast_data:
        logger.warning("Forecast data could not be calculated")
        fig = go.Figure()
        fig.add_annotation(
            text="Weather forecast not available",
            xref="paper", yref="paper",
            x=0.5, y=0.5,
            showarrow=False,
            font=dict(size=16, color="orange")
        )
        return fig

    logger.info(f"Forecast plot: {len(forecast_data)} days")

    # First value is current tank level
    dates = [current_date_str]
    levels = [current_level]
    temps = []

    # New structure: (date_str, level, temp, daily_consumption)
    for item in forecast_data:
        date_str = item[0]
        level = item[1]
        temp = item[2]
        dates.append(date_str)
        levels.append(level)
        temps.append(temp)

    # Create plot with second Y-axis
    fig = make_subplots(specs=[[{"secondary_y": True}]])

    # Tank level line (primary Y-axis)
    fig.add_trace(
        go.Scatter(
            x=dates,
            y=levels,
            name='Tank Level Forecast',
            line=dict(color='#008000', width=3),
            mode='lines+markers',
            marker=dict(size=8, symbol='circle')
        ),
        secondary_y=False
    )

    # Mark current value
    fig.add_trace(
        go.Scatter(
            x=[dates[0]],
            y=[levels[0]],
            name='Current Tank Level',
            mode='markers',
            marker=dict(size=14, color='red', symbol='circle')
        ),
        secondary_y=False
    )

    # Temperature line (secondary Y-axis)
    if temps:
        fig.add_trace(
            go.Scatter(
                x=dates[1:],
                y=temps,
                name='Forecast Temperature',
                line=dict(color='#0000FF', width=2, dash='dash'),
                mode='lines+markers',
                marker=dict(size=6, symbol='square'),
                opacity=0.7
            ),
            secondary_y=True
        )

    # Y-axis tank level
    # Y-axis goes up to 1500mm
    fig.update_yaxes(
        title_text="Tank Level (mm)",
        secondary_y=False,
        range=[0, 1500],
        dtick=100,
        showgrid=True,
        gridcolor='lightgray',
        gridwidth=1
    )

    # Red warning line at WARN_LEVEL_TANK
    warn_level = metadata.get('warn_level', config.WARN_LEVEL_TANK)
    fig.add_hline(
        y=warn_level,        
        line_color="red",
        line_width=2,
        annotation_text=f"Warning level ({warn_level:.0f}mm)",
        annotation_position="right",
        secondary_y=False
    )

    # Y-axis temperature (right)
    fig.update_yaxes(
        title_text="Temperature (°C)",
        secondary_y=True,
        showgrid=False
    )

    # X-axis
    fig.update_xaxes(title_text="Date")

    # Annotation at last data point
    date_warn_best = metadata.get('date_at_warn_best')
    date_warn_worst = metadata.get('date_at_warn_worst')
    dh_min = metadata.get('dh_min', 0)
    dh_max = metadata.get('dh_max', 0)

    # Info text at bottom
    annotation_text = (f"Regression: Consumption = {regression_k:.4f} * T + {regression_c:.4f}<br>"
                      f"Start: {current_level:.1f}mm, End: {levels[-1]:.1f}mm<br>"
                      f"dHMin: {dh_min:.2f}mm/day, dHMax: {dh_max:.2f}mm/day")

    # Annotations list
    annotations_list = [
        # Info at bottom
        dict(
            text=annotation_text,
            xref="paper", yref="paper",
            x=0.5, y=-0.2,
            showarrow=False,
            font=dict(size=9),
            xanchor='center'
        )
    ]

    # Annotation AT THE LAST DATA POINT
    if date_warn_best and date_warn_worst and dates and levels:
        from datetime import datetime as dt
        best_obj = dt.strptime(date_warn_best, '%Y-%m-%d')
        worst_obj = dt.strptime(date_warn_worst, '%Y-%m-%d')

        anno_text = (f"{config.WARN_LEVEL_TANK:.0f}mm reached:<br>"
                    f"Best: {best_obj.strftime('%d.%m.%Y')}<br>"
                    f"Worst: {worst_obj.strftime('%d.%m.%Y')}")

        annotations_list.append(
            dict(
                text=anno_text,
                x=dates[-1],
                y=levels[-1],
                xref="x", yref="y",
                showarrow=True,
                arrowhead=2,
                arrowsize=1,
                arrowwidth=2,
                arrowcolor="black",
                ax=40,
                ay=-40,
                bgcolor="yellow",
                bordercolor="black",
                borderwidth=2,
                borderpad=6,
                font=dict(size=10, color="black")
            )
        )

    # Layout
    fig.update_layout(
        title="Tank Level Forecast",
        height=500,
        showlegend=True,
        hovermode='x unified',
        plot_bgcolor='white',
        paper_bgcolor='white',
        annotations=annotations_list
    )

    return fig


def create_30day_with_forecast_plot(db_handler: DatabaseHandler):
    """
    Creates 30-day view WITH forecast as 3rd diagram

    Combines:
    - Top: Temperatures (30 days Min/Max)
    - Middle: Tank Level (30 days)
    - Bottom: Forecast (30 days, as far as available)

    Args:
        db_handler: DatabaseHandler instance

    Returns:
        plotly.graph_objects.Figure
    """
    # Get data for 30-day view
    temp_data = db_handler.get_daily_temp_minmax(days=30)
    level_data = db_handler.get_daily_level_median(days=30)

    logger.info(f"30-day with forecast: {len(temp_data)} temp, {len(level_data)} level")

    # Create 3 subplots
    fig = make_subplots(
        rows=3, cols=1,
        subplot_titles=('Temperatures (30 Days - Min/Max)',
                       'Tank Level (30 Days)',
                       'Tank Level Forecast (30 Days)'),
        vertical_spacing=0.08,
        row_heights=[0.35, 0.3, 0.35],
        specs=[[{"secondary_y": False}],
               [{"secondary_y": False}],
               [{"secondary_y": True}]]  # Forecast with second Y-axis
    )

    # === 1. Temperatures (top) ===
    temp_by_sensor = {}
    for date, sensor, temp_min, temp_max in temp_data:
        if sensor not in temp_by_sensor:
            temp_by_sensor[sensor] = {'dates': [], 'min': [], 'max': []}
        temp_by_sensor[sensor]['dates'].append(date)
        temp_by_sensor[sensor]['min'].append(temp_min / 10.0)
        temp_by_sensor[sensor]['max'].append(temp_max / 10.0)

    for sensor, data in sorted(temp_by_sensor.items()):
        color = SENSOR_COLORS.get(sensor, '#808080')

        # Min line
        fig.add_trace(
            go.Scatter(
                x=data['dates'],
                y=data['min'],
                name=f'{sensor} Min',
                line=dict(color=color, dash='dot', width=2),
                mode='lines+markers',
                marker=dict(size=8, symbol='circle'),
                legendgroup=sensor
            ),
            row=1, col=1
        )

        # Max line
        fig.add_trace(
            go.Scatter(
                x=data['dates'],
                y=data['max'],
                name=f'{sensor} Max',
                line=dict(color=color, width=3),
                mode='lines+markers',
                marker=dict(size=8, symbol='circle'),
                legendgroup=sensor
            ),
            row=1, col=1
        )

    # === 2. Tank Level (middle) ===
    if level_data:
        dates_level = [row[0] for row in level_data]
        levels = [row[1] for row in level_data]

        fig.add_trace(
            go.Scatter(
                x=dates_level,
                y=levels,
                name='Tank Level (Median)',
                line=dict(color='#008000', width=3),
                mode='lines+markers',
                marker=dict(size=8, symbol='circle'),
                fill='tozeroy'
            ),
            row=2, col=1
        )

    # === 3. Forecast (bottom) ===
    # Get current tank level
    current_level_data = db_handler.get_hourly_level_median(days=1)
    if current_level_data:
        current_level = current_level_data[-1][1]
        current_date_str = current_level_data[-1][0].split(' ')[0]

        regression_k = config.REGRESSION_K
        regression_c = config.REGRESSION_C

        if regression_k != 0.0 or regression_c != 0.0:
            forecast_data, fc_metadata = get_forecast_data(
                current_level=current_level,
                days=30,
                regression_k=regression_k,
                regression_c=regression_c
            )

            if forecast_data:
                f_dates = [current_date_str]
                f_levels = [current_level]
                f_temps = []

                # New structure: (date_str, level, temp, daily_consumption)
                for item in forecast_data:
                    date_str = item[0]
                    level = item[1]
                    temp = item[2]
                    f_dates.append(date_str)
                    f_levels.append(level)
                    f_temps.append(temp)

                # Tank level line
                fig.add_trace(
                    go.Scatter(
                        x=f_dates,
                        y=f_levels,
                        name='Tank Level Forecast',
                        line=dict(color='#008000', width=3),
                        mode='lines+markers',
                        marker=dict(size=7, symbol='circle')
                    ),
                    row=3, col=1,
                    secondary_y=False
                )

                # Current value
                fig.add_trace(
                    go.Scatter(
                        x=[f_dates[0]],
                        y=[f_levels[0]],
                        name='Current',
                        mode='markers',
                        marker=dict(size=6, color='red', symbol='circle')
                    ),
                    row=3, col=1,
                    secondary_y=False
                )

                # Temperature line
                if f_temps:
                    fig.add_trace(
                        go.Scatter(
                            x=f_dates[1:],
                            y=f_temps,
                            name='Forecast Temp',
                            line=dict(color='#0000FF', width=2, dash='dash'),
                            mode='lines+markers',
                            marker=dict(size=5, symbol='square'),
                            opacity=0.7
                        ),
                        row=3, col=1,
                        secondary_y=True
                    )

    # Adjust layout
    fig.update_xaxes(title_text="Date", row=1, col=1)
    fig.update_yaxes(title_text="Temperature (°C)", row=1, col=1,
                    dtick=10, showgrid=True, gridcolor='lightgray', gridwidth=1)

    fig.update_xaxes(title_text="Date", row=2, col=1)
    fig.update_yaxes(title_text="Tank Level (mm)", row=2, col=1,
                    dtick=100, showgrid=True, gridcolor='lightgray', gridwidth=1)

    fig.update_xaxes(title_text="Date", row=3, col=1)
    fig.update_yaxes(title_text="Tank Level (mm)", row=3, col=1,
                    range=[0, 1500], dtick=100,
                    showgrid=True, gridcolor='lightgray', gridwidth=1,
                    secondary_y=False)
    fig.update_yaxes(title_text="Temperature (°C)", row=3, col=1,
                    showgrid=False, secondary_y=True)

    # Red warning line at WARN_LEVEL_TANK in forecast plot
    fig.add_hline(
        y=config.WARN_LEVEL_TANK,
        line_color="red",
        line_width=2,
        row=3, col=1
    )

    # Annotation AT THE LAST DATA POINT (in forecast subplot)
    if 'fc_metadata' in locals() and 'f_dates' in locals() and 'f_levels' in locals():
        date_warn_best = fc_metadata.get('date_at_warn_best')
        date_warn_worst = fc_metadata.get('date_at_warn_worst')

        if date_warn_best and date_warn_worst and f_dates and f_levels:
            from datetime import datetime as dt
            best_obj = dt.strptime(date_warn_best, '%Y-%m-%d')
            worst_obj = dt.strptime(date_warn_worst, '%Y-%m-%d')

            anno_text = (f"{config.WARN_LEVEL_TANK:.0f}mm reached:<br>"
                        f"Best: {best_obj.strftime('%d.%m.%Y')}<br>"
                        f"Worst: {worst_obj.strftime('%d.%m.%Y')}")

            fig.add_annotation(
                text=anno_text,
                x=f_dates[-1],
                y=f_levels[-1],
                xref="x3", yref="y3",
                showarrow=True,
                arrowhead=2,
                arrowsize=1,
                arrowwidth=2,
                arrowcolor="black",
                ax=40,
                ay=-40,
                bgcolor="yellow",
                bordercolor="black",
                borderwidth=2,
                borderpad=6,
                font=dict(size=12, color="black")
            )

    fig.update_layout(
        height=1200,
        showlegend=True,
        hovermode='x unified',
        plot_bgcolor='white',
        paper_bgcolor='white'
    )

    return fig


def create_30day_with_forecast_html(db_handler: DatabaseHandler) -> str:
    """
    Creates 30-day view with forecast as HTML (for Dashboard)

    Args:
        db_handler: DatabaseHandler instance

    Returns:
        HTML String
    """
    fig = create_30day_with_forecast_plot(db_handler)
    return fig.to_html(full_html=False, include_plotlyjs='cdn')


def create_forecast_html(db_handler: DatabaseHandler) -> str:
    """
    Creates forecast view as HTML (for Dashboard)

    Args:
        db_handler: DatabaseHandler instance

    Returns:
        HTML String
    """
    fig = create_forecast_plot(db_handler)
    return fig.to_html(full_html=False, include_plotlyjs='cdn')
