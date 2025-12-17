#!/usr/bin/env python3
"""
DB Export Tool
Exports database contents with optional date filters

Usage:
  python3 export_db.py                    # All data
  python3 export_db.py 2025-12-01         # From start date
  python3 export_db.py 2025-12-01 2025-12-31  # From-To
"""
import sys
import sqlite3
from pathlib import Path
from datetime import datetime
from typing import Optional

# Add src to Python path
sys.path.insert(0, str(Path(__file__).resolve().parent))

import config


def format_timestamp(ts_str: str) -> str:
    """Formats timestamp for better readability"""
    try:
        dt = datetime.fromisoformat(ts_str)
        return dt.strftime("%d.%m.%Y %H:%M:%S")
    except:
        return ts_str


def export_data(start_date: Optional[str] = None, end_date: Optional[str] = None):
    """
    Exports data from the database

    Args:
        start_date: Start date in format YYYY-MM-DD (optional)
        end_date: End date in format YYYY-MM-DD (optional)
    """
    db_path = config.DATABASE_PATH

    if not Path(db_path).exists():
        print(f"Error: Database not found: {db_path}")
        sys.exit(1)

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Create WHERE clause based on date parameters
    where_clause = ""
    params = []

    if start_date:
        where_clause = "WHERE timestamp >= ?"
        params.append(start_date)

        if end_date:
            where_clause += " AND timestamp <= ?"
            params.append(end_date + " 23:59:59")

    # Output header
    print("=" * 80)
    print("TANK DATABASE EXPORT")
    print("=" * 80)

    if start_date and end_date:
        print(f"Time period: {start_date} to {end_date}")
    elif start_date:
        print(f"From: {start_date}")
    else:
        print("Time period: All data")

    print("=" * 80)
    print()

    # Export tank level measurements
    print("LEVEL MEASUREMENTS")
    print("-" * 80)
    print(f"{'Timestamp':<22} {'Tank':<6} {'Level 1':<8} {'Level 2':<8} {'Level 3':<8} {'Median':<8}")
    print("-" * 80)

    query = f"""
        SELECT timestamp, tank_id, level_1, level_2, level_3
        FROM level_measurements
        {where_clause}
        ORDER BY timestamp
    """

    cursor.execute(query, params)
    level_rows = cursor.fetchall()

    if level_rows:
        for row in level_rows:
            ts, tank_id, l1, l2, l3 = row
            median = (l1 + l2 + l3) / 3.0
            ts_formatted = format_timestamp(ts)
            print(f"{ts_formatted:<22} {tank_id:<6} {l1:<8} {l2:<8} {l3:<8} {median:<8.1f}")
        print(f"\nTotal: {len(level_rows)} measurements")
    else:
        print("No data found")

    print()
    print()

    # Export temperature measurements
    print("TEMPERATURE MEASUREMENTS")
    print("-" * 80)
    print(f"{'Timestamp':<22} {'Tank':<6} {'Sensor':<10} {'Temp (°C)':<10}")
    print("-" * 80)

    query = f"""
        SELECT timestamp, tank_id, sensor_name, temperature
        FROM temp_measurements
        {where_clause}
        ORDER BY timestamp, sensor_name
    """

    cursor.execute(query, params)
    temp_rows = cursor.fetchall()

    if temp_rows:
        for row in temp_rows:
            ts, tank_id, sensor, temp = row
            temp_celsius = temp / 10.0
            ts_formatted = format_timestamp(ts)
            print(f"{ts_formatted:<22} {tank_id:<6} {sensor:<10} {temp_celsius:<10.1f}")
        print(f"\nTotal: {len(temp_rows)} measurements")
    else:
        print("No data found")

    print()
    print("=" * 80)

    # Statistics
    print("STATISTICS")
    print("-" * 80)

    # Date range in DB
    cursor.execute("SELECT MIN(timestamp), MAX(timestamp) FROM level_measurements")
    level_range = cursor.fetchone()

    cursor.execute("SELECT MIN(timestamp), MAX(timestamp) FROM temp_measurements")
    temp_range = cursor.fetchone()

    if level_range[0]:
        print(f"Tank level measurements: {format_timestamp(level_range[0])} to {format_timestamp(level_range[1])}")

    if temp_range[0]:
        print(f"Temperature measurements: {format_timestamp(temp_range[0])} to {format_timestamp(temp_range[1])}")

    # Number of measurements per sensor
    cursor.execute("""
        SELECT sensor_name, COUNT(*) as count
        FROM temp_measurements
        GROUP BY sensor_name
        ORDER BY sensor_name
    """)

    sensor_counts = cursor.fetchall()
    if sensor_counts:
        print("\nMeasurements per sensor:")
        for sensor, count in sensor_counts:
            print(f"  {sensor}: {count}")

    print("=" * 80)

    conn.close()


def print_usage():
    """Outputs usage instructions"""
    print("DB Export Tool")
    print()
    print("Usage:")
    print("  python3 export_db.py                      # All data")
    print("  python3 export_db.py YYYY-MM-DD           # From start date")
    print("  python3 export_db.py YYYY-MM-DD YYYY-MM-DD  # From-To")
    print()
    print("Examples:")
    print("  python3 export_db.py")
    print("  python3 export_db.py 2025-12-01")
    print("  python3 export_db.py 2025-12-01 2025-12-31")


def validate_date(date_str: str) -> bool:
    """Validates date format YYYY-MM-DD"""
    try:
        datetime.strptime(date_str, "%Y-%m-%d")
        return True
    except ValueError:
        return False


def main():
    """Main function"""

    # Parse arguments
    if len(sys.argv) == 1:
        # No parameters: All data
        export_data()

    elif len(sys.argv) == 2:
        if sys.argv[1] in ["-h", "--help", "help"]:
            print_usage()
            sys.exit(0)

        # One parameter: Start date
        start_date = sys.argv[1]
        if not validate_date(start_date):
            print(f"Error: Invalid date format: {start_date}")
            print("Expected format: YYYY-MM-DD")
            sys.exit(1)

        export_data(start_date=start_date)

    elif len(sys.argv) == 3:
        # Two parameters: Start and end date
        start_date = sys.argv[1]
        end_date = sys.argv[2]

        if not validate_date(start_date):
            print(f"Error: Invalid start date: {start_date}")
            print("Expected format: YYYY-MM-DD")
            sys.exit(1)

        if not validate_date(end_date):
            print(f"Error: Invalid end date: {end_date}")
            print("Expected format: YYYY-MM-DD")
            sys.exit(1)

        # Check if start is before end
        if start_date > end_date:
            print("Error: Start date must be before end date")
            sys.exit(1)

        export_data(start_date=start_date, end_date=end_date)

    else:
        print("Error: Too many parameters")
        print()
        print_usage()
        sys.exit(1)


if __name__ == "__main__":
    main()
    