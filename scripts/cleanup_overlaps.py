import psycopg2
import os


def db_dsn_from_env():
    url = os.getenv("DATABASE_URL")
    if url:
        return url
    host = os.getenv("PGHOST", "127.0.0.1")
    port = int(os.getenv("PGPORT", "5432"))
    user = os.getenv("PGUSER", "agingos")
    password = os.getenv("PGPASSWORD", "agingos")
    dbname = os.getenv("PGDATABASE", "agingos")
    return f"postgresql://{user}:{password}@{host}:{port}/{dbname}"


def delete_overlap(conn, since, until):
    with conn.cursor() as cur:
        # Advisory lock
        cur.execute("SELECT pg_advisory_lock(123456789);")

        # Delete overlapping episodes
        cur.execute(
            """DELETE FROM episodes
               WHERE start_ts < %s
               AND COALESCE(end_ts, start_ts) > %s;""",
            (until, since),
        )

        deleted_count = cur.rowcount
        conn.commit()

        # Release advisory lock
        cur.execute("SELECT pg_advisory_unlock(123456789);")

    return deleted_count


# Example usage
if __name__ == "__main__":
    from datetime import datetime, timedelta

    conn = psycopg2.connect(db_dsn_from_env())

    # Get time window for last 24 hours
    until = datetime.now()
    since = until - timedelta(hours=24)

    deleted = delete_overlap(conn, since, until)
    print(f"Deleted {deleted} overlapping episodes")
    conn.close()
