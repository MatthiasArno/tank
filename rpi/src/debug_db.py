#!/usr/bin/env python3
"""
Debug tool for the database
Shows statistics and last entries
"""
import sys
import sqlite3
import argparse
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).resolve().parent))

import config


def debug_database():
    """Outputs debug information about the database"""
    db_path = config.DATABASE_PATH

    if not Path(db_path).exists():
        print(f"❌ Database not found: {db_path}")
        return

    print("=" * 80)
    print("🔍 DATABASE DEBUG INFORMATION")
    print("=" * 80)
    print(f"Database: {db_path}")
    print()

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Check if tables exist
    cursor.execute("""
        SELECT name FROM sqlite_master
        WHERE type='table' AND name IN ('level_measurements', 'temp_measurements')
    """)
    tables = cursor.fetchall()
    print(f"Found tables: {', '.join([t[0] for t in tables])}")
    print()

    # Level Measurements
    print("📊 LEVEL MEASUREMENTS")
    print("-" * 80)

    cursor.execute("SELECT COUNT(*) FROM level_measurements")
    count = cursor.fetchone()[0]
    print(f"Total count: {count}")

    if count > 0:
        cursor.execute("""
            SELECT MIN(timestamp), MAX(timestamp)
            FROM level_measurements
        """)
        min_ts, max_ts = cursor.fetchone()
        print(f"Time period: {min_ts} to {max_ts}")

        # Calculate how old the data is
        try:
            max_dt = datetime.fromisoformat(max_ts)
            now = datetime.now()
            age_days = (now - max_dt).days
            print(f"Last measurement {age_days} days ago")
            if age_days > 30:
                print(f"⚠️  WARNING: Data is older than 30 days!")
        except:
            pass

        print("\nLast 5 measurements:")
        cursor.execute("""
            SELECT timestamp, tank_id, level_1, level_2, level_3
            FROM level_measurements
            ORDER BY timestamp DESC
            LIMIT 5
        """)
        for row in cursor.fetchall():
            ts, tank, l1, l2, l3 = row
            median = (l1 + l2 + l3) / 3.0
            print(f"  {ts} | Tank {tank} | {l1}, {l2}, {l3} mm → Median: {median:.1f} mm")

    print()

    # Temperature Measurements
    print("🌡️  TEMPERATURE MEASUREMENTS")
    print("-" * 80)

    cursor.execute("SELECT COUNT(*) FROM temp_measurements")
    count = cursor.fetchone()[0]
    print(f"Total count: {count}")

    if count > 0:
        cursor.execute("""
            SELECT MIN(timestamp), MAX(timestamp)
            FROM temp_measurements
        """)
        min_ts, max_ts = cursor.fetchone()
        print(f"Time period: {min_ts} to {max_ts}")

        # Calculate how old the data is
        try:
            max_dt = datetime.fromisoformat(max_ts)
            now = datetime.now()
            age_days = (now - max_dt).days
            print(f"Last measurement {age_days} days ago")
            if age_days > 30:
                print(f"⚠️  WARNING: Data is older than 30 days!")
        except:
            pass

        # Sensors
        cursor.execute("""
            SELECT sensor_name, COUNT(*) as count
            FROM temp_measurements
            GROUP BY sensor_name
            ORDER BY sensor_name
        """)
        print("\nMeasurements per sensor:")
        for sensor, cnt in cursor.fetchall():
            print(f"  {sensor}: {cnt}")

        print("\nLast 10 measurements:")
        cursor.execute("""
            SELECT timestamp, sensor_name, temperature
            FROM temp_measurements
            ORDER BY timestamp DESC
            LIMIT 10
        """)
        for row in cursor.fetchall():
            ts, sensor, temp = row
            temp_c = temp / 10.0
            print(f"  {ts} | {sensor:<10} | {temp_c:6.1f}°C")

    print()
    print("=" * 80)

    # Test query for dashboard
    print("🧪 TEST: Dashboard queries (last 30 days)")
    print("-" * 80)

    cursor.execute("""
        SELECT COUNT(*) FROM temp_measurements
        WHERE timestamp >= datetime('now', 'localtime', '-30 days')
    """)
    count = cursor.fetchone()[0]
    print(f"Temperature measurements (last 30 days): {count}")

    cursor.execute("""
        SELECT COUNT(*) FROM level_measurements
        WHERE timestamp >= datetime('now', 'localtime', '-30 days')
    """)
    count = cursor.fetchone()[0]
    print(f"Tank level measurements (last 30 days): {count}")

    # Show UTC comparison for debugging
    cursor.execute("""
        SELECT datetime('now'), datetime('now', 'localtime')
    """)
    utc, local = cursor.fetchone()
    print(f"\nTime comparison:")
    print(f"  UTC:       {utc}")
    print(f"  Local time: {local}")

    if count == 0:
        print("\n⚠️  Dashboard shows nothing because no data in last 30 days!")
        print("   Solution: The app was updated and now also shows older data.")

    print("=" * 80)

    conn.close()


def remove_data_by_date(date_from=None, date_to=None, dry_run=False):
    """
    Remove datasets by date range

    Args:
        date_from: Start date (YYYY-MM-DD format), None means no lower bound
        date_to: End date (YYYY-MM-DD format), None means no upper bound
        dry_run: If True, only show what would be deleted without actually deleting
    """
    db_path = config.DATABASE_PATH

    if not Path(db_path).exists():
        print(f"❌ Database not found: {db_path}")
        return

    if date_from is None and date_to is None:
        print("❌ Error: At least one date (from or to) must be specified")
        return

    # Validate dates
    try:
        if date_from:
            datetime.strptime(date_from, '%Y-%m-%d')
        if date_to:
            datetime.strptime(date_to, '%Y-%m-%d')
    except ValueError as e:
        print(f"❌ Invalid date format: {e}")
        print("   Use YYYY-MM-DD format (e.g., 2024-01-15)")
        return

    print("=" * 80)
    print("🗑️  REMOVE DATA BY DATE")
    print("=" * 80)
    print(f"Database: {db_path}")

    if date_from and date_to:
        print(f"Date range: {date_from} to {date_to}")
        where_clause = "timestamp >= ? AND timestamp < datetime(?, '+1 day')"
        params = (date_from, date_to)
    elif date_from:
        print(f"Date range: from {date_from} onwards")
        where_clause = "timestamp >= ?"
        params = (date_from,)
    else:  # date_to only
        print(f"Date range: up to {date_to}")
        where_clause = "timestamp < datetime(?, '+1 day')"
        params = (date_to,)

    if dry_run:
        print("🔍 DRY RUN MODE - No data will be deleted")
    print()

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Check what will be deleted
    print("📊 Data to be removed:")
    print("-" * 80)

    # Level measurements
    cursor.execute(f"SELECT COUNT(*) FROM level_measurements WHERE {where_clause}", params)
    level_count = cursor.fetchone()[0]
    print(f"Level measurements: {level_count}")

    if level_count > 0:
        cursor.execute(f"""
            SELECT MIN(timestamp), MAX(timestamp)
            FROM level_measurements WHERE {where_clause}
        """, params)
        min_ts, max_ts = cursor.fetchone()
        print(f"  Time period: {min_ts} to {max_ts}")

    # Temperature measurements
    cursor.execute(f"SELECT COUNT(*) FROM temp_measurements WHERE {where_clause}", params)
    temp_count = cursor.fetchone()[0]
    print(f"Temperature measurements: {temp_count}")

    if temp_count > 0:
        cursor.execute(f"""
            SELECT MIN(timestamp), MAX(timestamp)
            FROM temp_measurements WHERE {where_clause}
        """, params)
        min_ts, max_ts = cursor.fetchone()
        print(f"  Time period: {min_ts} to {max_ts}")

    print()

    total_count = level_count + temp_count

    if total_count == 0:
        print("✅ No data found in the specified date range")
        conn.close()
        return

    if dry_run:
        print(f"🔍 Would delete {total_count} total records")
        print("   Run without --dry-run to actually delete the data")
    else:
        # Ask for confirmation
        print(f"⚠️  WARNING: About to delete {total_count} records!")
        response = input("Type 'yes' to confirm deletion: ")

        if response.lower() != 'yes':
            print("❌ Deletion cancelled")
            conn.close()
            return

        # Delete the data
        cursor.execute(f"DELETE FROM level_measurements WHERE {where_clause}", params)
        level_deleted = cursor.rowcount

        cursor.execute(f"DELETE FROM temp_measurements WHERE {where_clause}", params)
        temp_deleted = cursor.rowcount

        conn.commit()

        print()
        print("✅ Deletion completed:")
        print(f"   Level measurements deleted: {level_deleted}")
        print(f"   Temperature measurements deleted: {temp_deleted}")
        print(f"   Total deleted: {level_deleted + temp_deleted}")

    print("=" * 80)
    conn.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description='Debug tool for the database',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s                           Show database statistics
  %(prog)s --remove 2024-01-01-2024-01-31   Remove data from Jan 1-31, 2024
  %(prog)s --remove 2024-01-01-             Remove data from Jan 1, 2024 onwards
  %(prog)s --remove -2024-01-31             Remove data up to Jan 31, 2024
  %(prog)s --remove 2024-01-01- --dry-run   Preview deletion without removing
        """
    )

    parser.add_argument(
        '--remove',
        metavar='DATE_RANGE',
        help='Remove data by date range (format: YYYY-MM-DD-YYYY-MM-DD or YYYY-MM-DD- or -YYYY-MM-DD)'
    )

    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Preview what would be deleted without actually deleting'
    )

    args = parser.parse_args()

    if args.remove:
        # Parse date range
        date_range = args.remove

        if '-' not in date_range:
            print("❌ Error: Invalid date range format")
            print("   Use: YYYY-MM-DD-YYYY-MM-DD or YYYY-MM-DD- or -YYYY-MM-DD")
            sys.exit(1)

        # Split by '-' but handle dates properly
        # Format can be: 2024-01-01-2024-12-31 or 2024-01-01- or -2024-12-31
        if date_range.startswith('-'):
            # Format: -YYYY-MM-DD
            date_from = None
            date_to = date_range[1:]
        elif date_range.endswith('-'):
            # Format: YYYY-MM-DD-
            date_from = date_range[:-1]
            date_to = None
        else:
            # Format: YYYY-MM-DD-YYYY-MM-DD
            # Need to split carefully to handle dates with dashes
            parts = date_range.split('-')
            if len(parts) == 6:  # YYYY-MM-DD-YYYY-MM-DD
                date_from = '-'.join(parts[:3])
                date_to = '-'.join(parts[3:])
            else:
                print("❌ Error: Invalid date range format")
                print("   Use: YYYY-MM-DD-YYYY-MM-DD or YYYY-MM-DD- or -YYYY-MM-DD")
                sys.exit(1)

        remove_data_by_date(date_from, date_to, args.dry_run)
    else:
        debug_database()
    