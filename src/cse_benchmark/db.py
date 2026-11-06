import os
from pathlib import Path

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


def create_plaintext_schema(connection: psycopg.Connection) -> None:
    project_root = Path(__file__).resolve().parents[2]
    sql_path = project_root / "sql" / "001_plaintext.sql"

    connection.execute(sql_path.read_text(encoding="utf-8"))