"""Shared settings and database helpers.

All settings come from environment variables (or a .env file), so the same
code runs locally, on AWS, or for another city without edits.
"""

import os
import re
from contextlib import closing

from dotenv import load_dotenv

load_dotenv()

DB_SETTINGS = {
    "host": os.environ.get("DB_HOST", "localhost"),
    "port": int(os.environ.get("DB_PORT", 5432)),
    "dbname": os.environ.get("DB_NAME", "postgres"),
    "user": os.environ.get("DB_USER", "postgres"),
    "password": os.environ.get("DB_PASS", ""),
}

CITY_NAME = os.environ.get("CITY_NAME", "Porto")
CITY_LAT = float(os.environ.get("CITY_LAT", 41.15))
CITY_LON = float(os.environ.get("CITY_LON", -8.61))
TIMEZONE = os.environ.get("TIMEZONE", "Europe/Lisbon")

# First day to download. 1991 gives a full 1991-2020 climate normal to compare against.
BACKFILL_START = os.environ.get("BACKFILL_START", "1991-01-01")

# Table name kept as "porto_weather" by default so existing databases keep working.
TABLE = os.environ.get("WEATHER_TABLE", "porto_weather")
if not re.fullmatch(r"[a-z_][a-z0-9_]*", TABLE):
    raise ValueError(f"Invalid WEATHER_TABLE name: {TABLE!r}")


def get_conn():
    import psycopg2  # imported here so the analysis code and tests run without a database driver

    return psycopg2.connect(**DB_SETTINGS)


def query(sql, params=None):
    """Run a SELECT and return all rows."""
    with closing(get_conn()) as conn, closing(conn.cursor()) as cur:
        cur.execute(sql, params)
        return cur.fetchall()
