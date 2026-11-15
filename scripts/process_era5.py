#!/usr/bin/env python3
"""Convert the Climate Dashboard's daily ERA5 series into a compact JSON for the
website's hero "live climate data" card.

By default this pulls the SAME live daily series the Climate Dashboard uses,
straight from Copernicus Climate Pulse (see ERA5_URL below), so the card stays
fresh on every daily cron run instead of going stale against a checked-in file.
Set ERA5_CSV to a local path (e.g. the Climate Dashboard's copy) to read that
file instead — useful for offline/local rebuilds.

Matches the Climate Dashboard: daily anomalies vs the 1850-1900 preindustrial
baseline are taken from the file's anom_1850_1900 column, which applies
Copernicus's day-by-day offset to the 1991-2020 anomaly
(https://climate.copernicus.eu/climate-bulletin-about-data-and-analysis).
Output is rounded daily anomalies per year plus annual means and a few headline
statistics.

Stdlib only (urllib/csv/json) so it runs in CI without pip.

Output: site/data/era5_daily.json
"""

import csv
import io
import json
import os
import urllib.request
from datetime import datetime, timezone

# Live source — the daily global-mean 2m series published by Copernicus Climate
# Pulse, identical to what the Climate Dashboard fetches (see Climate Dashboard
# config.py). Override the URL with ERA5_URL, or read a local file via ERA5_CSV.
# Climate Pulse 2.0 path (Nov 2026); the old data/series/ file is only kept a
# few weeks after that release.
DEFAULT_URL = (
    "https://sites.ecmwf.int/data/climatepulse/timeseries/csv/daily/"
    "timeseries_era5_t2m_daily_global.csv"
)
ERA5_URL = os.environ.get("ERA5_URL", DEFAULT_URL)
ERA5_CSV = os.environ.get("ERA5_CSV")  # if set, read this local file instead

HERE = os.path.dirname(os.path.abspath(__file__))
OUT_PATH = os.path.join(HERE, "..", "site", "data", "era5_daily.json")



def read_csv_text() -> str:
    if ERA5_CSV:
        with open(ERA5_CSV, "r") as f:
            return f.read()
    req = urllib.request.Request(ERA5_URL, headers={"User-Agent": "zekehausfather.com/1.0"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read().decode("utf-8")


def load_daily():
    """Return rows sorted by date: list of dicts with date, year, month, anom, doy."""
    text = read_csv_text()
    # Strip leading comment lines so the header row is first.
    lines = [ln for ln in text.splitlines() if not ln.startswith("#")]
    reader = csv.DictReader(io.StringIO("\n".join(lines)))

    if "anom_1850_1900" not in (reader.fieldnames or []):
        raise SystemExit("ERA5 CSV has no anom_1850_1900 column (pre-Climate Pulse 2.0 "
                         "file?) — aborting (kept existing JSON).")

    rows = []
    for r in reader:
        ds = (r.get("date") or "").strip()
        raw = (r.get("anom_1850_1900") or "").strip()
        if not ds or not raw:
            continue
        try:
            d = datetime.strptime(ds, "%Y-%m-%d")
            anom = float(raw)
        except ValueError:
            continue
        rows.append({
            "date": ds, "dt": d, "year": d.year, "month": d.month,
            "day": d.day, "anom": anom,
        })

    rows.sort(key=lambda x: x["dt"])

    # Day-of-year aligned to 1..365 with Feb 29 dropped (so every year lines up).
    doy_by_year = {}
    for row in rows:
        if row["month"] == 2 and row["day"] == 29:
            row["doy"] = None
            continue
        n = doy_by_year.get(row["year"], 0) + 1
        doy_by_year[row["year"]] = n
        row["doy"] = n
    return rows


def main() -> None:
    rows = load_daily()
    if not rows:
        raise SystemExit("No ERA5 rows parsed — aborting (kept existing JSON).")

    years = sorted({r["year"] for r in rows})

    # 365-length daily series per year, aligned by day-of-year.
    series = {str(y): [None] * 365 for y in years}
    for r in rows:
        doy = r["doy"]
        if doy and 1 <= doy <= 365:
            series[str(r["year"])][doy - 1] = round(r["anom"], 3)

    # Annual means + day counts.
    annual_list = []
    for y in years:
        vals = [r["anom"] for r in rows if r["year"] == y]
        annual_list.append({
            "year": y,
            "anom": round(sum(vals) / len(vals), 3),
            "days": len(vals),
        })
    complete = [a for a in annual_list if a["days"] >= 360]

    latest_row = rows[-1]
    latest = {"date": latest_row["date"], "anom": round(latest_row["anom"], 3)}

    hottest = max(complete, key=lambda a: a["anom"]) if complete else None
    last_365 = rows[-365:]
    last_365_mean = round(sum(r["anom"] for r in last_365) / len(last_365), 3)
    days_over_15 = {
        str(y): sum(1 for r in rows if r["year"] == y and r["anom"] >= 1.5)
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

    src = ERA5_CSV if ERA5_CSV else ERA5_URL
    size_kb = os.path.getsize(OUT_PATH) / 1024
    print(f"Wrote {OUT_PATH} ({size_kb:.0f} KB) from {src}")
    print(f"  years: {years[0]}-{years[-1]}  latest: {latest['date']} = {latest['anom']}C")
    if hottest:
        print(f"  hottest complete year: {hottest['year']} = {hottest['anom']}C")
    print(f"  trailing-365 mean: {last_365_mean}C")
    print(f"  days >= 1.5C: {days_over_15}")


if __name__ == "__main__":
    main()
