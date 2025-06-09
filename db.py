import os
import psycopg2

DB_URL = os.environ["DATABASE_URL"]  # Railway даёт эту переменную

def get_connection():
    return psycopg2.connect(DB_URL)

def ensure_table_exists():
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS sent_ids (
                    ad_id TEXT PRIMARY KEY
                );
            """)
            conn.commit()

def load_sent_ids():
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT ad_id FROM sent_ids;")
            rows = cur.fetchall()
            return set(r[0] for r in rows)

def save_sent_id(ad_id):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("INSERT INTO sent_ids (ad_id) VALUES (%s) ON CONFLICT DO NOTHING;", (ad_id,))
            conn.commit()
