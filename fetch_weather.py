"""Download daily min/max temperatures from Open-Meteo and store them in PostgreSQL.

First run: backfills everything from BACKFILL_START (default 1991) to yesterday.
Later runs: re-fetch the last 7 days (late corrections) up to yesterday, and fill
any missing early years if BACKFILL_START was moved back.
Safe to run as often as you like: rows are upserted by date.
"""

from contextlib import closing
from datetime import date, timedelta

import requests

from db import BACKFILL_START, CITY_LAT, CITY_LON, TABLE, TIMEZONE, get_conn, query

ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/archive"
CHUNK_DAYS = 365 * 5   # keep each API request to about five years
REFRESH_DAYS = 7       # re-fetch the last week to pick up late corrections


def fetch_weather(start, end):
    """Return [(date_str, temp_max, temp_min), ...] for start..end inclusive."""
    params = {
        "latitude": CITY_LAT,
        "longitude": CITY_LON,
        "start_date": start.isoformat(),
        "end_date": end.isoformat(),
        "daily": "temperature_2m_max,temperature_2m_min",
        "timezone": TIMEZONE,
    }
    r = requests.get(ARCHIVE_URL, params=params, timeout=60)
    r.raise_for_status()
    return parse_daily(r.json())


def parse_daily(payload):
    """Turn an Open-Meteo response into rows, skipping days with missing values."""
    daily = payload["daily"]
    return [
        (d, tmax, tmin)
        for d, tmax, tmin in zip(daily["time"], daily["temperature_2m_max"], daily["temperature_2m_min"])
        if tmax is not None and tmin is not None
    ]


def plan_ranges(first, last, backfill_start, yesterday):
    """Work out which date ranges to download, given what's already stored.

    first/last are the earliest/latest dates in the database (None if empty).
    """
    if first is None:
        ranges = [(backfill_start, yesterday)]
    else:
        ranges = []
        if first > backfill_start:
            ranges.append((backfill_start, first - timedelta(days=1)))
        ranges.append((max(last - timedelta(days=REFRESH_DAYS), first), yesterday))
    return [(s, e) for s, e in ranges if s <= e]


def chunks(start, end, size=CHUNK_DAYS):
    """Split start..end into consecutive ranges of at most `size` days."""
    while start <= end:
        stop = min(start + timedelta(days=size - 1), end)
        yield start, stop
        start = stop + timedelta(days=1)


def upsert_records(records):
    import psycopg2.extras

    with closing(get_conn()) as conn, closing(conn.cursor()) as cur:
        psycopg2.extras.execute_values(cur, f"""
            INSERT INTO {TABLE} (date, temp_max, temp_min)
            VALUES %s
            ON CONFLICT (date) DO UPDATE
            SET temp_max = EXCLUDED.temp_max,
                temp_min = EXCLUDED.temp_min,
                fetched_at = NOW()
        """, records)
        conn.commit()


def main():
    first, last = query(f"SELECT MIN(date), MAX(date) FROM {TABLE}")[0]
    yesterday = date.today() - timedelta(days=1)   # the archive lags about a day behind
    ranges = plan_ranges(first, last, date.fromisoformat(BACKFILL_START), yesterday)

    if not ranges:
        print("✅ Already up to date.")
        return

    total = 0
    for start, end in ranges:
        for chunk_start, chunk_end in chunks(start, end):
            records = fetch_weather(chunk_start, chunk_end)
            if records:
                upsert_records(records)
            total += len(records)
            print(f"🔄 {chunk_start} → {chunk_end}: {len(records)} days")
    print(f"✅ Upserted {total} days in total.")


if __name__ == "__main__":
    main()
