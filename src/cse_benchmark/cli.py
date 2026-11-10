import argparse
import sys
from pathlib import Path

import psycopg

from .benchmark_datasets import export_benchmark_datasets
from .db import connect


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="cse-benchmark")

    commands = parser.add_subparsers(dest="command",required=True,)

    commands.add_parser("check-db", help="Połącz się z PostgreSQL i wykonaj SELECT 1",)

    generate_parser = commands.add_parser( "generate-datasets", help="Wygeneruj sześć scenariuszy danych benchmarku",)
    generate_parser.add_argument("--output", type=Path,default=Path("data/generated/benchmark_v1"),help="Folder docelowy na zbiory danych i manifest",)

    args = parser.parse_args(argv)

    if args.command == "generate-datasets":
        try:
            manifest_path = export_benchmark_datasets(args.output)
        except OSError as error:
            print( f"Nie udało się zapisać danych: {error}", file=sys.stderr,)
            return 1

        print(f"Zapisano scenariusze. Manifest: {manifest_path}")
        return 0

    if args.command == "check-db":
        try:
            with connect() as connection:
                row = connection.execute("SELECT 1").fetchone()
        except psycopg.Error as error:
            print(f"PostgreSQL connection failed: {error}", file=sys.stderr,)
            return 1

        if row != (1,):
            print("PostgreSQL check failed: unexpected SELECT 1 result.",file=sys.stderr,)
            return 1

        print("PostgreSQL connection OK (SELECT 1 = 1).")
        return 0

    return 1