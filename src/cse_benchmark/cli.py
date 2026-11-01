import argparse
import sys

import psycopg

from .db import connect


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="cse-benchmark")

    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("check-db",help="Połącz się z PostgreSQL i wykonaj SELECT 1", )

    args = parser.parse_args(argv)

    if args.command == "check-db":
        try:
            with connect() as connection:
                row = connection.execute("SELECT 1").fetchone()
        except psycopg.Error as error:
            print(f"PostgreSQL connection failed: {error}", file=sys.stderr)
            return 1

        if row != (1,):
            print( "PostgreSQL check failed: unexpected SELECT 1 result.",file=sys.stderr, )
            return 1

        print("PostgreSQL connection OK (SELECT 1 = 1).")
        return 0

    return 1