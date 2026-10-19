"""Create the weather table if it doesn't exist yet."""

from contextlib import closing

from db import TABLE, get_conn


def setup():
    with closing(get_conn()) as conn, closing(conn.cursor()) as cur:
        cur.execute(f"""
            CREATE TABLE IF NOT EXISTS {TABLE} (
                date        DATE PRIMARY KEY,
                temp_max    FLOAT,
                temp_min    FLOAT,
                fetched_at  TIMESTAMP DEFAULT NOW()
            );
        """)
        conn.commit()
    print(f"✅ Table {TABLE} is ready.")


if __name__ == "__main__":
    setup()
