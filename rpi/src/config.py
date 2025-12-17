"""
Main configuration file for Tank Monitoring System
"""
import os
from pathlib import Path
from dotenv import load_dotenv

# Base directory (rpi/src)
BASE_DIR = Path(__file__).resolve().parent

# Load .env file if available (for development)
# In production (systemd) environment variables are set directly
dotenv_path = BASE_DIR / ".env"
if dotenv_path.exists():
    load_dotenv(dotenv_path)
    print(f"✓ Loaded configuration from {dotenv_path}")
else:
    print(f"ℹ No .env file found at {dotenv_path}, using environment variables only")

# Database directory (rpi/db)
DB_DIR = BASE_DIR.parent / "db"

# Output directory for plot exports (rpi/output)
OUTPUT_DIR = BASE_DIR.parent / "output"

# MQTT Configuration
MQTT_BROKER_HOST = os.getenv("MQTT_BROKER_HOST", "localhost")
MQTT_BROKER_PORT = int(os.getenv("MQTT_BROKER_PORT", "1883"))
MQTT_USERNAME = os.getenv("MQTT_USERNAME", None)
MQTT_PASSWORD = os.getenv("MQTT_PASSWORD", None)

# Database Configuration
# Default: rpi/db/tank_data.db
DATABASE_PATH = os.getenv("DATABASE_PATH", str(DB_DIR / "tank_data.db"))

# Output Configuration
# Default: rpi/output
PLOT_OUTPUT_DIR = os.getenv("PLOT_OUTPUT_DIR", str(OUTPUT_DIR))

# Telegram Bot Configuration
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_MY_ID = os.getenv("TELEGRAM_MY_ID", "")  # Authorized User ID
TELEGRAM_OUTPUT_DIR = os.getenv("TELEGRAM_OUTPUT_DIR", str(OUTPUT_DIR / "telegram"))

# Web Server Configuration
WEB_HOST = os.getenv("WEB_HOST", "0.0.0.0")
WEB_PORT = int(os.getenv("WEB_PORT", "8000"))

# Logging Configuration
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

# Alarm Configuration
# Threshold 15°C (Temperatures are in degrees Celsius, not tenths of a degree)
ALARM_TEMP_THRESHOLD_HIGH = float(os.getenv("ALARM_TEMP_THRESHOLD_HIGH", "25.0"))
ALARM_TEMP_THRESHOLD_LOW = float(os.getenv("ALARM_TEMP_THRESHOLD_LOW", "17.0"))
ALARM_TEMP_THRESHOLD_AUS = float(os.getenv("ALARM_TEMP_AUS_THRESHOLD_AUS", "4.0"))

# Forecast Configuration
# Regression coefficients for consumption forecast
# Consumption [mm/day] = REGRESSION_K * Temperature[°C] + REGRESSION_C
REGRESSION_K = float(os.getenv("REGRESSION_K", "0.0"))
REGRESSION_C = float(os.getenv("REGRESSION_C", "0.0"))

# Choose weather forecast source
# "brightsky" = BrightSky.dev (Default, F-FORE-110)
# "openmeteo" = Open-Meteo (Alternative with often more forecast days)
FORECAST_SOURCE = os.getenv("FORECAST_SOURCE", "openmeteo")

# Warning level for tank fill level
WARN_LEVEL_TANK = float(os.getenv("WARN_LEVEL_TANK", "1300"))


# Location in LAT/LON for weather forecast
LOCATION_LAT = float(os.getenv("LOCATION_LAT", "0.0"))
LOCATION_LON = float(os.getenv("LOCATION_LON", "0.0"))
LOCATION_ZIP = float(os.getenv("LOCATION_ZIP", "12345"))


def evaluate_alarm(data: dict, repetition: int) -> tuple[str, int, int] | None:
    """
    Evaluates alarm conditions for sensor temperatures, depending on the outside temperature level.

    Args:
        data: Dictionary in °C (already converted)
              Format: {'2-ABV': 45.0, '3-ABR': 35.0, '4-NBV': 50.0, '5-NBR': 40.0}
        repetition: current run 0,1... Could be used to adapt timeouts based on the run.

    Returns:
        tuple (text, timeout, repetitions)
        None if no alarm   
    """    
    send_alarm=False    
    critical_sensors = ['2-ABV', '3-ABR', '4-NBV', '5-NBR']    
    crit_temp=[data[k] for k in critical_sensors if k in data]
    aus_temp=data.get('1-AUS')
    if aus_temp and crit_temp:
        min_temp=min(crit_temp)
        if aus_temp < ALARM_TEMP_THRESHOLD_AUS:
            if min_temp < ALARM_TEMP_THRESHOLD_HIGH:
                send_alarm=True
        else:
            if min_temp <  ALARM_TEMP_THRESHOLD_LOW:
                send_alarm=True
                
    if send_alarm:        
        alarm_text=f"🚨 Alarm, temperatures: {data}\n"
        print(alarm_text)
        return (alarm_text, 60, 10)

    return None
