"""
Forecast module for heating oil consumption prediction
F-FORE-100

Uses BrightSky.dev API for weather forecast (default)
Optional Open-Meteo API (switchable via FORECAST_SOURCE in .env)
Calculates expected tank level progression based on regression parameters.
"""
import logging
import requests
from datetime import datetime, timedelta
from typing import List, Tuple, Optional
import config

logger = logging.getLogger(__name__)



def get_weather_forecast_brightsky(days: int = 30) -> List[Tuple[str, float]]:
    """
    Gets weather forecast from BrightSky.dev
    Calculates average temperature per day
    Args:
        days: Number of days for forecast (default: 30)

    Returns:
        List of tuples: (date_str, avg_temp_celsius)
        Example: [('2025-12-13', 5.2), ('2025-12-14', 3.8), ...]
    """
    try:
        # Calculate date range
        # BrightSky delivers forecast from current date
        today = datetime.now().date()
        end_date = today + timedelta(days=days)

        # BrightSky.dev API
        url = "https://api.brightsky.dev/weather"
        params = {
            'lat': config.LOCATION_LAT,
            'lon': config.LOCATION_LON,
            'date': today.isoformat(),
            'last_date': end_date.isoformat()
        }

        logger.info(f"Fetching weather forecast from BrightSky for {config.LOCATION_ZIP} ({days} days)")
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()

        data = response.json()
        weather_data = data.get('weather', [])

        if not weather_data:
            logger.warning("No weather data received from BrightSky")
            return []

        # Calculate average temperature per day
        daily_temps = {}
        for entry in weather_data:
            timestamp = entry.get('timestamp')
            temperature = entry.get('temperature')

            if timestamp and temperature is not None:
                # Extract date (without time)
                date_str = timestamp.split('T')[0]

                if date_str not in daily_temps:
                    daily_temps[date_str] = []
                daily_temps[date_str].append(temperature)

        # Calculate average per day
        forecast = []
        for date_str in sorted(daily_temps.keys()):
            temps = daily_temps[date_str]
            avg_temp = sum(temps) / len(temps)
            forecast.append((date_str, avg_temp))

        logger.info(f"Weather forecast received: {len(forecast)} days")
        return forecast

    except requests.exceptions.RequestException as e:
        logger.error(f"Error fetching weather forecast: {e}")
        return []
    except Exception as e:
        logger.error(f"Unexpected error in weather forecast: {e}", exc_info=True)
        return []


def get_weather_forecast_openmeteo(days: int = 30) -> List[Tuple[str, float]]:
    """
    Gets weather forecast from Open-Meteo API
    
    Args:
        days: Number of days for forecast (default: 30)

    Returns:
        List of tuples: (date_str, avg_temp_celsius)
        Example: [('2025-12-13', 5.2), ('2025-12-14', 3.8), ...]
    """
    try:
        # Open-Meteo API
        # https://open-meteo.com/en/docs
        url = "https://api.open-meteo.com/v1/forecast"
        params = {
            'latitude': config.LOCATION_LAT,
            'longitude': config.LOCATION_LON,
            'daily': 'temperature_2m_mean',  # Mean daily temperature
            'timezone': 'Europe/Berlin',
            'forecast_days': min(days, 16)  # Open-Meteo delivers max 16 days
        }

        logger.info(f"Fetching weather forecast from Open-Meteo for {config.LOCATION_ZIP} ({days} days requested)")
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()

        data = response.json()
        daily_data = data.get('daily', {})
        dates = daily_data.get('time', [])
        temps = daily_data.get('temperature_2m_mean', [])

        if not dates or not temps:
            logger.warning("No weather data received from Open-Meteo")
            return []

        # Data is already as daily averages
        forecast = []
        for date_str, temp in zip(dates, temps):
            if temp is not None:
                forecast.append((date_str, temp))

        logger.info(f"Weather forecast received from Open-Meteo: {len(forecast)} days")
        return forecast

    except requests.exceptions.RequestException as e:
        logger.error(f"Error fetching weather forecast from Open-Meteo: {e}")
        return []
    except Exception as e:
        logger.error(f"Unexpected error in weather forecast (Open-Meteo): {e}", exc_info=True)
        return []


def get_weather_forecast(days: int = 30, source: str = "brightsky") -> List[Tuple[str, float]]:
    """
    Gets weather forecast from configured source

    Args:
        days: Number of days for forecast
        source: "brightsky" or "openmeteo"

    Returns:
        List of tuples: (date_str, avg_temp_celsius)
    """
    if source.lower() == "openmeteo":
        logger.info("Using Open-Meteo for weather forecast")
        return get_weather_forecast_openmeteo(days)
    else:
        logger.info("Using BrightSky.dev for weather forecast")
        return get_weather_forecast_brightsky(days)


def calculate_consumption_forecast(
    current_level: float,
    weather_forecast: List[Tuple[str, float]],
    regression_k: float,
    regression_c: float
) -> Tuple[List[Tuple[str, float, float, float]], dict]:
    """
    Calculates tank level forecast based on weather forecast
    Uses regression parameters from .env
    Determines dHMax and dHMin (max/min daily consumption)

    The regression has the form:
        Consumption [mm/day] = k * Temperature + c

    Args:
        current_level: Current tank level in mm
        weather_forecast: List of (date, avg_temp) tuples
        regression_k: Slope parameter (REGRESSION_K from .env)
        regression_c: Y-intercept (REGRESSION_C from .env)

    Returns:
        Tuple: (forecast_data, statistics)
        - forecast_data: List of tuples: (date_str, forecasted_level_mm, temperature_celsius, daily_consumption_mm)
        - statistics: Dict with dHMax, dHMin, etc.
    """
    if not weather_forecast:
        logger.warning("No weather forecast available for forecast calculation")
        return [], {}

    forecast = []
    level = current_level
    daily_consumptions = []

    for date_str, temp in weather_forecast:
        # Calculate expected consumption per day
        # Consumption [mm/day] = k * Temperature + c
        daily_consumption = regression_k * temp + regression_c
        daily_consumptions.append(daily_consumption)

        # Update tank level (consumption reduces tank level)
        level = level + daily_consumption  # daily_consumption is typically negative

        # Prevent negative tank level
        if level < 0:
            level = 0

        forecast.append((date_str, level, temp, daily_consumption))

    # Find max and min daily consumption
    dh_max = max(daily_consumptions) if daily_consumptions else 0  # Maximum increase (warmest day)
    dh_min = min(daily_consumptions) if daily_consumptions else 0  # Minimum increase (coldest day)

    statistics = {
        'dh_max': dh_max,
        'dh_min': dh_min,
        'start_level': current_level,
        'end_level': level
    }

    logger.info(f"Forecast calculated: {len(forecast)} days, "
                f"Start level: {current_level:.1f}mm, "
                f"End level: {level:.1f}mm, "
                f"dHMin: {dh_min:.2f}mm/day, dHMax: {dh_max:.2f}mm/day")

    return forecast, statistics


def get_forecast_data(
    current_level: float,
    days: int = 30,
    regression_k: Optional[float] = None,
    regression_c: Optional[float] = None
) -> Tuple[List[Tuple[str, float, float]], dict]:
    """
    F-FORE-100 Complete forecast pipeline

    Gets weather forecast and calculates tank level forecast.

    Args:
        current_level: Current tank level in mm
        days: Number of forecast days (default: 30)
        regression_k: Slope parameter (if None, read from .env)
        regression_c: Y-intercept (if None, read from .env)

    Returns:
        Tuple: (forecast_data, metadata)
        - forecast_data: List of (date_str, level_mm, temp_celsius)
        - metadata: Dict with additional information
    """
    # Load regression parameters from config if not passed
    if regression_k is None:
        regression_k = config.REGRESSION_K
    if regression_c is None:
        regression_c = config.REGRESSION_C

    # Get weather source from config
    forecast_source = config.FORECAST_SOURCE

    logger.info(f"Starting forecast calculation: current_level={current_level:.1f}mm, "
                f"days={days}, k={regression_k:.4f}, c={regression_c:.4f}, source={forecast_source}")

    # F-FORE-110/111: Get weather forecast
    weather_forecast = get_weather_forecast(days=days, source=forecast_source)

    if not weather_forecast:
        logger.warning("No weather forecast available, forecast not possible")
        return [], {
            'status': 'error',
            'message': 'Weather forecast not available'
        }

    # Calculate consumption forecast
    forecast_data, statistics = calculate_consumption_forecast(
        current_level=current_level,
        weather_forecast=weather_forecast,
        regression_k=regression_k,
        regression_c=regression_c
    )

    # Calculate when WARN_LEVEL_TANK is reached (best/worst case)
    # FROM THE LAST FORECAST POINT!
    warn_level = config.WARN_LEVEL_TANK
    date_at_warn_best = None
    date_at_warn_worst = None

    if forecast_data and statistics:
        end_level = statistics['end_level']
        end_date_str = forecast_data[-1][0]
        end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()

        dh_min = statistics['dh_min']  # Minimum consumption = Best Case
        dh_max = statistics['dh_max']  # Maximum consumption = Worst Case

        # Best Case: with minimum consumption FROM THE END OF THE FORECAST
        if end_level < warn_level and dh_min > 0:
            days_to_warn_best = (warn_level - end_level) / dh_min
            if days_to_warn_best > 0:
                date_at_warn_best = (end_date + timedelta(days=int(days_to_warn_best))).isoformat()

        # Worst Case: with maximum consumption FROM THE END OF THE FORECAST
        if end_level < warn_level and dh_max > 0:
            days_to_warn_worst = (warn_level - end_level) / dh_max
            if days_to_warn_worst > 0:
                date_at_warn_worst = (end_date + timedelta(days=int(days_to_warn_worst))).isoformat()

    metadata = {
        'status': 'success',
        'forecast_days': len(forecast_data),
        'current_level': current_level,
        'regression_k': regression_k,
        'regression_c': regression_c,
        'forecast_source': forecast_source,
        'start_date': forecast_data[0][0] if forecast_data else None,
        'end_date': forecast_data[-1][0] if forecast_data else None,
        'dh_min': statistics.get('dh_min', 0),
        'dh_max': statistics.get('dh_max', 0),
        'warn_level': warn_level,
        'date_at_warn_best': date_at_warn_best,
        'date_at_warn_worst': date_at_warn_worst,
    }

    return forecast_data, metadata
