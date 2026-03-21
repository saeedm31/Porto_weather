import requests
import psycopg2
import psycopg2.extras
import os
from datetime import date, timedelta
from dotenv import load_dotenv

load_dotenv()

DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_PORT = int(os.environ.get("DB_PORT", 5432))
DB_NAME = os.environ.get("DB_NAME", "postgres")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASS = os.environ.get("DB_PASS", "")

CITY_LAT = float(os.environ.get("CITY_LAT", 41.15))
CITY_LON = float(os.environ.get("CITY_LON", -8.61))
BACKFILL_START = "2023-01-01"

def get_conn():
    return psycopg2.connect(
        host=DB_HOST, port=DB_PORT,
        dbname=DB_NAME, user=DB_USER, password=DB_PASS
    )

def fetch_weather(start_date: str, end_date: str):
    """Fetch daily min/max temps from Open-Meteo (free, no API key)."""
    url = "https://archive-api.open-meteo.com/v1/archive"
    params = {
        "latitude": CITY_LAT,
        "longitude": CITY_LON,
        "start_date": start_date,
        "end_date": end_date,
        "daily": "temperature_2m_max,temperature_2m_min",
        "timezone": "Europe/Lisbon"
    }
    r = requests.get(url, params=params, timeout=30)
    r.raise_for_status()
    data = r.json()["daily"]
    records = []
    for d, tmax, tmin in zip(data["time"], data["temperature_2m_max"], data["temperature_2m_min"]):
        if tmax is not None and tmin is not None:
            records.append((d, tmax, tmin))
    return records

def upsert_records(records):
    conn = get_conn()
    cur = conn.cursor()
    psycopg2.extras.execute_values(cur, """
        INSERT INTO porto_weather (date, temp_max, temp_min)
        VALUES %s
        ON CONFLICT (date) DO UPDATE
        SET temp_max = EXCLUDED.temp_max,
            temp_min = EXCLUDED.temp_min,
            fetched_at = NOW()
    """, [(r[0], r[1], r[2]) for r in records])
    conn.commit()
    cur.close()
    conn.close()

def get_last_date():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT MAX(date) FROM porto_weather")
    result = cur.fetchone()[0]
    cur.close()
    conn.close()
    return result

def main():
    last = get_last_date()
    if last is None:
        start = BACKFILL_START
        print(f"🌍 Backfilling from {start}...")
    else:
        # Go back 7 days to catch any late-arriving data
        start = (last - timedelta(days=7)).strftime("%Y-%m-%d")
        print(f"🔄 Updating from {start}...")

    # Open-Meteo archive has ~1 day delay
    end = (date.today() - timedelta(days=1)).strftime("%Y-%m-%d")

    if start > end:
        print("✅ Already up to date.")
        return

    records = fetch_weather(start, end)
    upsert_records(records)
    print(f"✅ Upserted {len(records)} records ({start} → {end})")

if __name__ == "__main__":
    main()
