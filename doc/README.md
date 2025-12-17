# Tank Monitoring System

Server applications for visualization, messaging and analysis of heating data.

## Structure

```
rpi/
├── db/                     # Database directory
│   └── tank_data.db       # SQLite database (created automatically)
└── src/                    # Source Code
    ├── api/                    # FastAPI Dashboard
    │   ├── dashboard.py       # Main application with Plotly
    │   └── templates/         # HTML Templates
    │       ├── index.html     # Home page
    │       └── view.html      # Chart view
    ├── database/              # Database modules
    │   └── db_handler.py     # Database handler
    ├── mqtt/                  # MQTT Client
    │   └── subscriber.py     # MQTT Subscriber
    ├── utils/                 # Utility functions
    ├── config.py             # Configuration
    ├── run_subscriber.py     # Starts MQTT Subscriber
    ├── run_dashboard.py      # Starts Dashboard
    ├── export_db.py          # DB Export Tool (R-FUN-700)
    ├── statistic_db.py       # Statistics Analysis Tool (F-STAT-800)
    ├── debug_db.py           # Database debug tool
    └── requirements.txt      # Python Dependencies
```

## Installation

### 1. Create Virtual Environment (recommended)

```bash
cd rpi/src
python3 -m venv .venv
source .venv/bin/activate
```

### 2. Install Python Dependencies

```bash
# In the activated venv:
pip install -r requirements.txt
```

**Important**: If you use a venv, you must activate it before each manual start:
```bash
source .venv/bin/activate
```

For systemd services, the absolute path to venv Python is used (see below).

### 3. Create Configuration

```bash
# Copy env.example to .env
cp env.example .env

# Edit .env and add your values
nano .env
```
### 4. Install Mosquitto MQTT Broker (if not already installed)

```bash
sudo apt update
sudo apt install mosquitto mosquitto-clients
sudo systemctl enable mosquitto
sudo systemctl start mosquitto
```
# Database (optional, default: ../db/tank_data.db)
# DATABASE_PATH=/custom/path/to/tank_data.db

### Start MQTT Subscriber

The subscriber receives MQTT messages and writes them to the database:

```bash
python3 run_subscriber.py
```

### Start Dashboard

The dashboard displays the data graphically:

```bash
python3 run_dashboard.py
```

Open dashboard: http://localhost:8000

### Start Messenger

```bash
python3 run_telegram_bot.py
```

Using a loud alarm tone:
* Download a loud sound, e.g. copy alarm.mp3 to /Notifications/alarm.mp3
* Telegram: Settings/Notifications
  * Private Chats: Sound+Vibration. A default must be enabled
  * Settings for system notifications (at the bottom): All customized channels at a glance
  * Customize channel directly: click on the icon in the channel, Notifications/Customize, then select your own alarm tone
* Phone:
  * Settings/Device maintenance/Battery/App power management/Apps that won't be put to sleep => Add Telegram
  * Settings/Apps/Telegram/Mobile data connection => Allow background data


### DB Export Tool

Exports database contents with optional date filters:

```bash
# Export all data
python3 export_db.py

# From start date
python3 export_db.py 2025-12-01

# Date range
python3 export_db.py 2025-12-01 2025-12-31
```

### Statistics Tool

Analyzes heating oil consumption depending on outside temperature:

```bash
# Analyze all data
python3 statistic_db.py

# From start date
python3 statistic_db.py 2025-12-01

# Date range
python3 statistic_db.py 2025-12-01 2025-12-31
```

The tool:
- Calculates daily consumption (dH/dT) normalized to outside temperature
- Performs linear regression and evaluates suitability
- Creates graphs PNG with actual data and regression line
- Saves graphs in the `output/` directory

### Debug Tool

Shows database statistics and diagnoses problems:

```bash
python3 debug_db.py
```

## Features

### MQTT Topics

The subscriber subscribes to the following topics:
- `tank/1/level` - Level measurements (3 values + ignored value)
- `tank/1/temp/1-AUS` - Outside temperature
- `tank/1/temp/2-ABV` - Old building supply (R-FUN-110)
- `tank/1/temp/3-ABR` - Old building return (R-FUN-110)
- `tank/1/temp/4-NBV` - New building supply (R-FUN-110)
- `tank/1/temp/5-NBR` - New building return (R-FUN-110)
- `tank/1/temp/device` - Ignored

### Dashboard

FastAPI-based dashboard with two main views:

### R-FUN-510/520/530: 30-Day View

- Shows min/max values of all temperature sensors over 30 days
- Dotted lines for min values, solid lines for max values
- Color coding (R-FUN-530):
  - ABV (Old building supply): Red
  - ABR (Old building return): Orange
  - NBV (New building supply): Blue
  - NBR (New building return): Light blue
  - Level: Green
- Level: Last value of the day (median of 3 sensors)

### 7-Day View

- Shows all values (hourly aggregated) over 7 days
- Solid lines for all sensors
- Level: Median of 3 sensors
- Same color coding as 30-day view

### DB Export Tool

Command-line tool for exporting database data:

```bash
python3 export_db.py [STARTDATE] [ENDDATE]
```

- No parameters: All data
- One parameter: From start date
- Two parameters: Date range
- Date format: YYYY-MM-DD

### Statistical Analysis

Analyzes the relationship between heating oil consumption and outside temperature:

```bash
python3 statistic_db.py [STARTDATE] [ENDDATE]
```

Functions:
- Calculates daily consumption rate normalized to temperature difference to 20°C: `dH/dT = (H_end - H_start) / (T_mean - 20)` [mm/Kelvin]
- Optional date filters (analogous to export_db.py)
- Linear regression with statistical evaluation (R², p-value)
- Graphical representation:
  - X-axis: Outside temperature [°C]
  - Y-axis: Daily consumption [mm]
  - Shows measurement data as points and regression line
  - Saves as PNG and PDF in `output/` directory

## Important Note: Dashboard Display

The dashboard shows data from the last 7/30 days by default. If no data is available in this time period (e.g., with older test data), the logic has been improved:

- **Automatic fallback display**: If no current data is available, the last available data is automatically displayed
- **Debug tool**: With `python3 debug_db.py` you can check what data is in the DB and how old it is

## Database

The SQLite database is stored by default in `rpi/db/tank_data.db` and contains two tables:

- `level_measurements`: Level measurements
- `temp_measurements`: Temperature measurements

Both tables contain timestamp, tank ID, and the respective measurement values.

**Database location**:
- Default: `rpi/db/tank_data.db`
- Automatically created on first start
- Can be changed via `DATABASE_PATH` environment variable

## Debian Package Installation

A Debian package is available for easy installation on the Raspberry Pi. See the *build-deb-fpm.sh* for systemd configuration and what gets packed.

### Create Package (on development computer)

Prerequisites:
```bash
sudo apt-get install -y ruby ruby-dev rubygems build-essential
sudo gem install --no-document fpm
```

Build package:
```bash
cd /path/to/project
./build-deb-fpm.sh
```

Creates: `tank-monitoring_0.1.0_armhf.deb`

### Install Package on RPI

```bash

# Install Mosquitto
sudo apt-get install mosquitto
# Create file
# etc/mosquitto/conf.d/rpiserver.conf
# listener 1883 0.0.0.0
# allow_anonymous true
sudo systemctl enable mosquitto
sudo systemctl start mosquitto


# Copy package to RPI
scp tank-monitoring_0.1.0_armhf.deb myuser@myrpi:~

# Install on RPI
ssh myuser@myrpi
sudo dpkg -i tank-monitoring_0.1.0_armhf.deb
sudo apt-get install -f  # If dependencies are missing
```

### Configuration After Installation

```bash
# 1. Create bot configuration
sudo cp /etc/tank/bot.conf.example /etc/tank/bot.conf
sudo nano /etc/tank/bot.conf
```

Add:
```bash
TELEGRAM_BOT_TOKEN=your-bot-token-here
TELEGRAM_MY_ID=your-telegram-user-id
```

```bash
# 2. Enable and start services
sudo systemctl enable tank-subscriber tank-telegram
sudo systemctl start tank-subscriber tank-telegram

# Optional: Enable dashboard
sudo systemctl enable tank-dashboard
sudo systemctl start tank-dashboard
```

### Service Management with tank-ctl

The package installs a helper script for easy service management:

```bash
# Start services
tank-ctl start

# Stop services
tank-ctl stop

# Restart services
tank-ctl restart

# Show status of all services
tank-ctl status

# View logs
tank-ctl logs mqtt        # MQTT Subscriber logs
tank-ctl logs bot         # Telegram Bot logs
tank-ctl logs dashboard   # Dashboard logs

# Enable/disable autostart
tank-ctl enable
tank-ctl disable
```

### Control Individual Services

```bash
# MQTT Subscriber only
sudo systemctl start tank-subscriber
sudo systemctl stop tank-subscriber
sudo systemctl status tank-subscriber

# Telegram Bot only
sudo systemctl start tank-telegram
sudo systemctl stop tank-telegram
sudo systemctl status tank-telegram

# Dashboard only
sudo systemctl start tank-dashboard
sudo systemctl stop tank-dashboard
sudo systemctl status tank-dashboard
```

### Installation Paths

The Debian package installs to:
- Application: `/opt/tank/rpi/`
- Python venv: `/opt/tank/rpi/.venv/`
- Database: `/opt/tank/rpi/db/tank_data.db`
- Configuration: `.env' : provide your personal configuration file
- Systemd services: `/etc/systemd/system/tank-*.service`
- Helper script: `/usr/bin/tank-ctl`

### Uninstallation

```bash
# Services are automatically stopped and disabled
sudo dpkg -r tank-monitoring

# Complete removal including database and configuration
sudo dpkg --purge tank-monitoring
sudo rm -rf /opt/tank
```

### Logs After Installation

```bash
# Real-time logs
sudo journalctl -u tank-subscriber -f
sudo journalctl -u tank-telegram -f
sudo journalctl -u tank-dashboard -f

# Or with tank-ctl
tank-ctl logs mqtt
tank-ctl logs bot
tank-ctl logs dashboard
```
