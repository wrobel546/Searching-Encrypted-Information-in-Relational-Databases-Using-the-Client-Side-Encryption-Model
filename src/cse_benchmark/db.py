import os

import psycopg


def connect() -> psycopg.Connection:
    return psycopg.connect(
        host=os.environ.get("PGHOST", "127.0.0.1"),
        port=os.environ.get("PGPORT", "5432"),
        dbname=os.environ.get("PGDATABASE", "cse_benchmark"),
        user=os.environ.get("PGUSER", "cse"),
        password=os.environ.get("PGPASSWORD", "cse_local"),
        connect_timeout=5,
    )