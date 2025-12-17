#!/usr/bin/env python3
"""
Statistics Tool
Calculates heating oil consumption as a function of outside temperature

Arguments like debug_db.py (start date, end date optional)
Calculates tank level change per day vs. average outside temperature
Htag = (H2-H1)/(T2-T1)*24, only days with ≥18 measurement points
Output device temperature in table
Htag_sk = Htag * (319 + 0.6*T_device) / 343 (sound velocity correction)
Linear regression Htag vs. 1-AUS
Linear regression Htag_sk vs. 1-AUS
Pyplot PNG graphic (no PDF!)
X-axis scaled from -10°C to 20°C

Usage:
  python3 statistic_db.py                    # All data
  python3 statistic_db.py 2025-12-01         # From start date
  python3 statistic_db.py 2025-12-01 2025-12-31  # From-To
"""
import sys
import sqlite3
import numpy as np
import matplotlib.pyplot as plt
from pathlib import Path
from datetime import datetime
from typing import Optional, List, Tuple
from scipy import stats

# Add src to Python path
sys.path.insert(0, str(Path(__file__).resolve().parent))

import config


def get_daily_statistics(conn: sqlite3.Connection,
                         start_date: Optional[str] = None,
                         end_date: Optional[str] = None) -> List[Tuple]:
    """
    Gets daily statistics for tank level and outside temperature
    Only days with ≥18 measurement points
    Gets device temperature

    Returns:
        List of tuples: (date, H1, H2, T1, T2, mean_temp_aus, mean_temp_device,
                         measurement_count, htag, htag_sk)
        where H1/H2 = first/last tank level, T1/T2 = first/last timestamp
    """
    cursor = conn.cursor()

    # WHERE clause for date filter
    where_clause = ""
    params = []

    if start_date:
        where_clause = "AND DATE(timestamp) >= ?"
        params.append(start_date)

        if end_date:
            where_clause += " AND DATE(timestamp) <= ?"
            params.append(end_date)

    # Query for first/last measurement points per day
    # Includes device temperature
    query = f"""
        WITH daily_levels AS (
            SELECT
                DATE(timestamp) as date,
                timestamp,
                (level_1 + level_2 + level_3) / 3.0 as level_median,
                ROW_NUMBER() OVER (PARTITION BY DATE(timestamp) ORDER BY timestamp ASC) as rn_first,
                ROW_NUMBER() OVER (PARTITION BY DATE(timestamp) ORDER BY timestamp DESC) as rn_last
            FROM level_measurements
            WHERE 1=1 {where_clause}
        ),
        daily_temps AS (
            SELECT
                DATE(timestamp) as date,
                AVG(temperature / 10.0) as mean_temp
            FROM temp_measurements
            WHERE sensor_name = '1-AUS' {where_clause}
            GROUP BY DATE(timestamp)
        ),
        daily_device_temps AS (
            SELECT
                DATE(timestamp) as date,
                AVG(temperature / 10.0) as mean_temp_device
            FROM temp_measurements
            WHERE sensor_name = 'device' {where_clause}
            GROUP BY DATE(timestamp)
        ),
        daily_counts AS (
            SELECT
                DATE(timestamp) as date,
                COUNT(*) as measurement_count
            FROM level_measurements
            WHERE 1=1 {where_clause}
            GROUP BY DATE(timestamp)
        ),
        first_levels AS (
            SELECT date, timestamp as ts_first, level_median as h1
            FROM daily_levels
            WHERE rn_first = 1
        ),
        last_levels AS (
            SELECT date, timestamp as ts_last, level_median as h2
            FROM daily_levels
            WHERE rn_last = 1
        )
        SELECT
            fl.date,
            fl.h1,
            ll.h2,
            fl.ts_first,
            ll.ts_last,
            dt.mean_temp,
            dc.measurement_count
        FROM first_levels fl
        JOIN last_levels ll ON fl.date = ll.date
        JOIN daily_temps dt ON fl.date = dt.date
        JOIN daily_counts dc ON fl.date = dc.date
        WHERE dt.mean_temp IS NOT NULL
          AND dc.measurement_count >= 18
        ORDER BY fl.date
    """

    cursor.execute(query, params + params + params)  # params three times due to three WHERE clauses

    results = []
    for row in cursor.fetchall():
        date, h1, h2, ts_first, ts_last, mean_temp, measurement_count = row

        # Calculate Htag = (H2-H1)/(T2-T1)*24
        dt_first = datetime.fromisoformat(ts_first)
        dt_last = datetime.fromisoformat(ts_last)
        hours_diff = (dt_last - dt_first).total_seconds() / 3600.0

        if hours_diff > 0:
            htag = (h2 - h1) / hours_diff * 24.0
        else:
            htag = 0.0

        results.append((date, h1, h2, ts_first, ts_last, mean_temp, measurement_count, htag))

    return results


def perform_regression(temps: np.ndarray, htags: np.ndarray, fixed_point_temp: float = 20.0) -> Tuple:
    """
    Calculates linear regression Htag vs. 1-AUS

    With fixed point: dH = 0 at T = fixed_point_temp (default: 20°C)
    Formula: dH = k * (T - fixed_point_temp)

    Args:
        temps: Average outside temperatures [°C]
        htags: Daily consumption rates [mm/24h]
        fixed_point_temp: Temperature where dH=0 (default: 20°C)

    Returns:
        (slope, intercept, r_value, p_value, std_err, r_squared)
        intercept is calculated as: intercept = -slope * fixed_point_temp
    """
    # Transform data: T' = T - fixed_point_temp
    temps_transformed = temps - fixed_point_temp

    # Regression through origin: dH = k * T'
    # k = sum(T' * dH) / sum(T'^2)
    slope = np.sum(temps_transformed * htags) / np.sum(temps_transformed ** 2)

    # Calculate intercept for original formula: dH = k * T + c
    # With c = -k * fixed_point_temp
    intercept = -slope * fixed_point_temp

    # Calculate R² and correlation for goodness of fit
    htags_pred = slope * temps_transformed
    ss_res = np.sum((htags - htags_pred) ** 2)
    ss_tot = np.sum((htags - np.mean(htags)) ** 2)
    r_squared = 1 - (ss_res / ss_tot)
    r_value = np.sqrt(r_squared) if r_squared > 0 else 0

    # Standard error
    n = len(temps)
    std_err = np.sqrt(ss_res / (n - 1) / np.sum(temps_transformed ** 2))

    # p-value (t-test for slope)
    t_stat = slope / std_err if std_err > 0 else 0
    from scipy.stats import t as t_dist
    p_value = 2 * (1 - t_dist.cdf(abs(t_stat), n - 1))

    return slope, intercept, r_value, p_value, std_err, r_squared


def plot_statistics(temps: np.ndarray,
                    htags: np.ndarray,
                    measurement_counts: np.ndarray,
                    slope: float,
                    intercept: float,
                    r_squared: float,
                    start_date: Optional[str] = None,
                    end_date: Optional[str] = None):
    """
    Creates pyplot PNG graphic (no PDF!)
    Scales X-axis to 22°C

    Y-axis: Consumption [mm]
    X-axis: Outside temperature [°C]
    Shows actual data and regression line
    """
    plt.figure(figsize=(12, 8))

    # Actual data as points
    plt.scatter(temps, htags, alpha=0.6, s=50, label='Measurement data')

    # Annotate each point with number of measurement points
    for i, (temp, htag, count) in enumerate(zip(temps, htags, measurement_counts)):
        plt.annotate(f'{int(count)}',
                    xy=(temp, htag),
                    xytext=(0, -12),
                    textcoords='offset points',
                    ha='center',
                    fontsize=8,
                    alpha=0.7)

    # Regression line
    # X-axis from -10°C to 20°C
    x_range = np.linspace(-10, 20, 100)
    y_pred = slope * x_range + intercept
    plt.plot(x_range, y_pred, 'r-', linewidth=2,
             label=f'Regression: y = {slope:.2f}x + {intercept:.2f}\nR² = {r_squared:.3f}')

    # Axis labels
    plt.xlabel('Outside Temperature [°C]', fontsize=12)
    plt.ylabel('Daily Consumption [mm/24h]', fontsize=12)

    # Set X-axis limits from -10°C to 20°C
    plt.xlim(-10, 20)

    # Title
    if start_date and end_date:
        title = f'Heating Oil Consumption vs. Outside Temperature\n{start_date} to {end_date}'
    elif start_date:
        title = f'Heating Oil Consumption vs. Outside Temperature\nFrom {start_date}'
    else:
        title = 'Heating Oil Consumption vs. Outside Temperature\nAll Data'
    plt.title(title, fontsize=14, fontweight='bold')

    # Grid and legend
    plt.grid(True, alpha=0.3)
    plt.legend(fontsize=10, loc='best')

    # Optimize layout
    plt.tight_layout()

    # Save as PNG (no PDF!)
    output_dir = Path(config.PLOT_OUTPUT_DIR)
    output_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_path = output_dir / f"statistics_{timestamp}.png"
    plt.savefig(output_path, dpi=150, bbox_inches='tight')
    print(f"\nGraphic saved: {output_path}")

    # Close figure to free memory
    plt.close()


def analyze_data(start_date: Optional[str] = None, end_date: Optional[str] = None):
    """
    Main function for statistical analysis

    Calculates tank level change per day
    Htag = (H2-H1)/(T2-T1)*24, only days with ≥18 measurement points
    Performs linear regression
    Creates PNG plot (no PDF!)
    X-axis scaled from -10°C to 20°C
    """
    db_path = config.DATABASE_PATH

    if not Path(db_path).exists():
        print(f"Error: Database not found: {db_path}")
        sys.exit(1)

    conn = sqlite3.connect(db_path)

    # Header
    print("=" * 80)
    print("STATISTICS: HEATING OIL CONSUMPTION vs. OUTSIDE TEMPERATURE")
    print("=" * 80)

    if start_date and end_date:
        print(f"Time period: {start_date} to {end_date}")
    elif start_date:
        print(f"From: {start_date}")
    else:
        print("Time period: All data")
    print()

    # Get data
    print("Loading data...")
    daily_stats = get_daily_statistics(conn, start_date, end_date)

    if not daily_stats:
        print("Error: No data found for the specified time period")
        print("Note: Only days with at least 18 measurement points considered (F-STAT-830)")
        conn.close()
        sys.exit(1)

    print(f"Found: {len(daily_stats)} days with complete data (≥18 measurement points)")
    print(f"Htag = (H2-H1)/(T2-T1)*24")
    print()

    # Output daily values
    print("-" * 120)
    print(f"{'Date':<12} {'Meas.':<6} {'H1':<10} {'H2':<10} {'T1':<10} {'T2':<10} "
          f"{'T_OUT':<10} {'Htag':<12}")
    print(f"{'':12} {'Pts.':<6} {'[mm]':<10} {'[mm]':<10} {'':10} {'':10} "
          f"{'[°C]':<10} {'[mm/24h]':<12}")
    print("-" * 120)

    temps = []
    htags = []
    measurement_counts = []

    for date, h1, h2, ts_first, ts_last, mean_temp, measurement_count, htag in daily_stats:
        # Format timestamps for output
        t1_str = datetime.fromisoformat(ts_first).strftime("%H:%M")
        t2_str = datetime.fromisoformat(ts_last).strftime("%H:%M")

        temps.append(mean_temp)
        htags.append(htag)
        measurement_counts.append(measurement_count)

        print(f"{date:<12} {measurement_count:>5} {h1:>9.1f} {h2:>9.1f} {t1_str:<10} {t2_str:<10} "
              f"{mean_temp:>9.1f} {htag:>11.2f}")

    print("-" * 120)
    print()

    # Convert to numpy arrays
    temps = np.array(temps)
    htags = np.array(htags)
    measurement_counts = np.array(measurement_counts)

    # Linear regression for Htag with fixed point
    print("=" * 80)
    print("LINEAR REGRESSION: Htag vs. Outside Temperature (1-AUS)")
    print("With fixed point: dH = 0 at T = 20°C")
    print("=" * 80)

    fixed_temp = 20.0
    slope, intercept, r_value, p_value, std_err, r_squared = perform_regression(temps, htags, fixed_point_temp=fixed_temp)

    print(f"Regression equation: Htag = {slope:.4f} * (T_out - {fixed_temp:.0f})")
    print(f"Or equivalently:     Htag = {slope:.4f} * T_out + {intercept:.4f}")
    print(f"Slope (k):           {slope:.4f} mm/(24h·°C)")
    print(f"Fixed point:         dH = 0 at T = {fixed_temp:.0f}°C")
    print(f"Correlation coeff. (r): {r_value:.4f}")
    print(f"Coefficient of determination (R²): {r_squared:.4f}")
    print(f"p-value:             {p_value:.6f}")
    print(f"Standard error:      {std_err:.4f}")
    print()

    # Interpretation
    print("INTERPRETATION:")
    print("-" * 80)

    # R² evaluation
    if r_squared > 0.7:
        print(f"✓ Linear regression is well suited (R² = {r_squared:.3f} > 0.7)")
    elif r_squared > 0.5:
        print(f"○ Linear regression is acceptable (R² = {r_squared:.3f} > 0.5)")
    else:
        print(f"✗ Linear regression is poorly suited (R² = {r_squared:.3f} < 0.5)")
        print("  Other models (polynomial, exponential) might fit better")

    print()

    # p-value evaluation
    if p_value < 0.05:
        print(f"✓ Regression is statistically significant (p = {p_value:.6f} < 0.05)")
    else:
        print(f"✗ Regression is NOT statistically significant (p = {p_value:.6f} >= 0.05)")

    print()

    # Physical interpretation
    print("PHYSICAL MEANING:")
    print("-" * 80)
    print(f"Per °C temperature change, consumption changes by {slope:.2f} mm/day")
    print()
    print(f"Example: At 10°C outside temperature:")
    expected_consumption = slope * 10 + intercept
    print(f"  Expected consumption: {expected_consumption:.1f} mm/day")
    print()
    print(f"Example: At 0°C outside temperature:")
    expected_consumption_0 = slope * 0 + intercept
    print(f"  Expected consumption: {expected_consumption_0:.1f} mm/day")

    print("=" * 80)
    print()

    # Write regression coefficients to .env file
    write_coefficients_to_env(slope, intercept, r_squared)
    print("✓ Regression coefficients saved to .env")
    print()

    # Create plot (only for Htag, not Htag_sk)
    print("Creating graphic...")
    plot_statistics(temps, htags, measurement_counts, slope, intercept, r_squared, start_date, end_date)

    conn.close()


def write_coefficients_to_env(slope: float, intercept: float, r_squared: float):
    """
    Writes regression coefficients to .env file

    Args:
        slope: Slope of regression (k)
        intercept: Y-intercept (c)
        r_squared: Coefficient of determination (R²)
    """
    env_path = Path(config.BASE_DIR) / ".env"

    # Read existing .env if present
    existing_lines = []
    if env_path.exists():
        with open(env_path, 'r') as f:
            existing_lines = f.readlines()

    # Remove old regression and forecast entries
    filtered_lines = [line for line in existing_lines
                      if not line.startswith('REGRESSION_') and not line.startswith('FORECAST_SOURCE')]

    # Add new regression values
    with open(env_path, 'w') as f:
        # Write existing lines (without old regression values)
        for line in filtered_lines:
            f.write(line)

        # Add new regression values
        f.write("\n# Regression coefficients (F-STAT-840, F-FORE-150)\n")
        f.write(f"# Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"# Formula: dH = k * (T - 20°C)\n")
        f.write(f"# R² = {r_squared:.6f}\n")
        f.write(f"REGRESSION_K={slope:.6f}\n")
        f.write(f"REGRESSION_C={intercept:.6f}\n")
        f.write(f"\n# Weather forecast source (F-FORE-111):\n")
        f.write(f"# brightsky = BrightSky.dev (default, approx. 10-14 days)\n")
        f.write(f"# openmeteo = Open-Meteo (alternative, approx. 16 days)\n")
        f.write(f"FORECAST_SOURCE=openmeteo\n")


def print_usage():
    """Outputs usage instructions"""
    print("Statistics Tool - F-STAT-800")
    print()
    print("Calculates heating oil consumption as a function of outside temperature")
    print()
    print("Usage:")
    print("  python3 statistic_db.py                      # All data")
    print("  python3 statistic_db.py YYYY-MM-DD           # From start date")
    print("  python3 statistic_db.py YYYY-MM-DD YYYY-MM-DD  # From-To")
    print()
    print("Examples:")
    print("  python3 statistic_db.py")
    print("  python3 statistic_db.py 2025-12-01")
    print("  python3 statistic_db.py 2025-12-01 2025-12-31")


def validate_date(date_str: str) -> bool:
    """Validates date format YYYY-MM-DD"""
    try:
        datetime.strptime(date_str, "%Y-%m-%d")
        return True
    except ValueError:
        return False


def main():
    """Main function"""

    # Parse arguments like debug_db.py
    if len(sys.argv) == 1:
        # No parameters: All data
        analyze_data()

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

        analyze_data(start_date=start_date)

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

        analyze_data(start_date=start_date, end_date=end_date)

    else:
        print("Error: Too many parameters")
        print()
        print_usage()
        sys.exit(1)


if __name__ == "__main__":
    main()
