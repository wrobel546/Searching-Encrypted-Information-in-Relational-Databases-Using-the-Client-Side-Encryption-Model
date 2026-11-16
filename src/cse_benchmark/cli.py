import argparse
import sys
from pathlib import Path

import psycopg

from .benchmark import (
    BenchmarkError,
    BenchmarkSettings,
    run_search_benchmark,
)
from .benchmark_datasets import export_benchmark_datasets
from .db import connect
from .keys import (
    DEFAULT_KEYS_PATH,
    KeyConfigurationError,
    load_keys,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="cse-benchmark")

    commands = parser.add_subparsers(
        dest="command",
        required=True,
    )

    commands.add_parser(
        "check-db",
        help="Połącz się z PostgreSQL i wykonaj SELECT 1",
    )

    generate_parser = commands.add_parser(
        "generate-datasets",
        help="Wygeneruj sześć scenariuszy danych benchmarku",
    )
    generate_parser.add_argument(
        "--output",
        type=Path,
        default=Path("data/generated/benchmark_v1"),
        help="Folder docelowy na zbiory danych i manifest",
    )

    benchmark_parser = commands.add_parser(
        "benchmark-search",
        help="Uruchom benchmark trzech strategii wyszukiwania",
    )

    benchmark_parser.add_argument(
        "--manifest",
        type=Path,
        default=Path(
            "data/generated/benchmark_v1/manifest.json"
        ),
        help="Ścieżka do manifestu scenariuszy",
    )

    benchmark_parser.add_argument(
        "--output",
        type=Path,
        default=Path(
            "results/raw/search_benchmark_v1.csv"
        ),
        help="Plik CSV na surowe wyniki",
    )

    benchmark_parser.add_argument(
        "--keys",
        type=Path,
        default=DEFAULT_KEYS_PATH,
        help="Plik z kluczami",
    )

    benchmark_parser.add_argument(
        "--warmups",
        type=int,
        default=3,
        help="Liczba rozgrzewek",
    )

    benchmark_parser.add_argument(
        "--repetitions",
        type=int,
        default=30,
        help="Liczba zapisywanych powtórzeń",
    )

    benchmark_parser.add_argument(
        "--scan-batch-size",
        type=int,
        default=100,
        help="Rozmiar partii strategii B",
    )

    benchmark_parser.add_argument(
        "--scenario",
        action="append",
        help=(
            "Nazwa wybranego scenariusza. "
            "Opcję można podać wielokrotnie."
        ),
    )

    args = parser.parse_args(argv)

    if args.command == "generate-datasets":
        try:
            manifest_path = export_benchmark_datasets(args.output)
        except OSError as error:
            print(
                f"Nie udało się zapisać danych: {error}",
                file=sys.stderr,
            )
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
            print(
                "PostgreSQL check failed: unexpected SELECT 1 result.",
                file=sys.stderr,
            )
            return 1

        print("PostgreSQL connection OK (SELECT 1 = 1).")
        return 0
    if args.command == "benchmark-search":
        try:
            settings = BenchmarkSettings(
                warmups=args.warmups,
                repetitions=args.repetitions,
                scan_batch_size=args.scan_batch_size,
            )

            keys = load_keys(args.keys)

            selected_scenarios = (
                set(args.scenario)
                if args.scenario
                else None
            )

            with connect() as connection:
                connection.autocommit = True

                result_path = run_search_benchmark(
                    connection=connection,
                    keys=keys,
                    manifest_path=args.manifest,
                    output_path=args.output,
                    settings=settings,
                    selected_scenarios=selected_scenarios,
                )

        except (
            BenchmarkError,
            KeyConfigurationError,
            OSError,
            ValueError,
            psycopg.Error,
        ) as error:
            print(
                f"Benchmark failed: {error}",
                file=sys.stderr,
            )
            return 1

        print(f"Zapisano wyniki benchmarku: {result_path}")
        return 0

    return 1
