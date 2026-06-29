#!/usr/bin/env python3
"""Convert the Climate Dashboard's daily ERA5 series into a compact JSON for the
website's interactive temperature chart.

Mirrors the baseline logic in The Climate Brink/GMST visualizations/gmst_data.py:
ERA5 daily anomalies (vs 1991-2020) are shifted onto the 1850-1900 preindustrial
baseline using per-month offsets. Output is rounded daily anomalies per year plus
annual means and a few headline statistics.

Output: site/data/era5_daily.json
"""

import json
import os
from datetime import datetime, timezone

import numpy as np
import pandas as pd

# Source CSV (same file the GMST visualizations use). Override with ERA5_CSV env var.
DEFAULT_CSV = (
    "/Users/hausfath/Desktop/Climate Science/Climate Dashboard/"
    "data/era5_daily_series_2t_global.csv"
)
CSV_PATH = os.environ.get("ERA5_CSV", DEFAULT_CSV)

HERE = os.path.dirname(os.path.abspath(__file__))
OUT_PATH = os.path.join(HERE, "..", "site", "data", "era5_daily.json")

# Per-month offsets: ERA5 anomaly (1991-2020 baseline) + offset = anomaly vs 1850-1900
MONTHLY_PREINDUSTRIAL_OFFSETS = {
    1: 0.96, 2: 0.96, 3: 0.95, 4: 0.91, 5: 0.87, 6: 0.83,
    7: 0.80, 8: 0.80, 9: 0.81, 10: 0.85, 11: 0.89, 12: 0.93,
}


def load_daily() -> pd.DataFrame:
    df = pd.read_csv(CSV_PATH, comment="#", parse_dates=["date"])
    df = df.rename(columns={"ano_91-20": "anom9120", "2t": "abs_t"})
    df["year"] = df["date"].dt.year
    df["month"] = df["date"].dt.month
    df["day"] = df["date"].dt.day
    df["anom"] = df["anom9120"] + df["month"].map(MONTHLY_PREINDUSTRIAL_OFFSETS)
    # Drop Feb 29 so every year aligns to 1..365.
    noleap = df[~((df["month"] == 2) & (df["day"] == 29))].copy()
    noleap["doy"] = noleap.groupby("year").cumcount() + 1
    df = df.merge(noleap[["date", "doy"]], on="date", how="left")
    return df


def main() -> None:
    df = load_daily()

    years = sorted(df["year"].unique().tolist())
    series = {}
    for y in years:
        sub = df[df["year"] == y].sort_values("doy")
        # 365-length list aligned by day-of-year; None where the year is incomplete.
        vals = [None] * 365
        for doy, anom in zip(sub["doy"], sub["anom"]):
            if pd.notna(doy) and 1 <= int(doy) <= 365:
                vals[int(doy) - 1] = round(float(anom), 3)
        series[str(y)] = vals

    annual = (
        df.groupby("year")["anom"].agg(["mean", "count"]).reset_index()
    )
    annual_list = [
        {"year": int(r.year), "anom": round(float(r.mean), 3), "days": int(r.count)}
        for r in annual.itertuples()
    ]
    complete = [a for a in annual_list if a["days"] >= 360]

    latest_row = df.sort_values("date").iloc[-1]
    latest = {
        "date": latest_row["date"].strftime("%Y-%m-%d"),
        "anom": round(float(latest_row["anom"]), 3),
    }

    # Headline stats
    hottest = max(complete, key=lambda a: a["anom"]) if complete else None
    last_365 = df.sort_values("date").tail(365)
    last_365_mean = round(float(last_365["anom"].mean()), 3)
    days_over_15 = {
        str(y): int((df[df["year"] == y]["anom"] >= 1.5).sum())
        for y in (2023, 2024, 2025, 2026)
        if y in years
    }

    out = {
        "updated": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        "source": "ERA5 (Copernicus / C3S)",
        "baseline": "1850-1900 preindustrial",
        "units": "degrees C above preindustrial",
        "year_range": [years[0], years[-1]],
        "latest": latest,
        "stats": {
            "hottest_year": hottest,
            "trailing_365_mean": last_365_mean,
            "days_over_1p5C": days_over_15,
        },
        "annual": annual_list,
        "series": series,
    }

    os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
    with open(OUT_PATH, "w") as f:
        json.dump(out, f, separators=(",", ":"))

    size_kb = os.path.getsize(OUT_PATH) / 1024
    print(f"Wrote {OUT_PATH} ({size_kb:.0f} KB)")
    print(f"  years: {years[0]}-{years[-1]}  latest: {latest['date']} = {latest['anom']}C")
    if hottest:
        print(f"  hottest complete year: {hottest['year']} = {hottest['anom']}C")
    print(f"  trailing-365 mean: {last_365_mean}C")
    print(f"  days >= 1.5C: {days_over_15}")


if __name__ == "__main__":
    main()
