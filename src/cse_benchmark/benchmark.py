import csv
import hashlib
import json
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4

import psycopg

from .data import SearchQuery, SyntheticDataset, load_dataset
from .db import (
    create_blind_index_schema,
    create_encrypted_scan_schema,
    create_plaintext_schema,
)
from .keys import KeySet
from .models import Contact
from .strategies.blind_index import (
    replace_blind_index_contacts,
    search_blind_index,
)
from .strategies.encrypted_scan import (
    replace_encrypted_contacts,
    search_encrypted_scan,
)
from .strategies.plaintext import (
    replace_plaintext_contacts,
    search_plaintext,
)


class BenchmarkError(RuntimeError):
    pass


@dataclass(frozen=True)
class BenchmarkSettings:
    warmups: int = 3
    repetitions: int = 30
    scan_batch_size: int = 100

    def __post_init__(self) -> None:
        if type(self.warmups) is not int or self.warmups < 0:
            raise ValueError(
                "Liczba rozgrzewek musi być nieujemną "
                "liczbą całkowitą."
            )

        if (
            type(self.repetitions) is not int
            or self.repetitions <= 0
        ):
            raise ValueError(
                "Liczba powtórzeń musi być dodatnią "
                "liczbą całkowitą."
            )

        if (
            type(self.scan_batch_size) is not int
            or self.scan_batch_size <= 0
        ):
            raise ValueError(
                "Rozmiar partii musi być dodatnią "
                "liczbą całkowitą."
            )


@dataclass(frozen=True)
class BenchmarkScenario:
    name: str
    count: int
    distribution: str
    seed: int
    dataset_path: Path
    sha256: str


SearchFunction = Callable[[str], list[Contact]]


CSV_FIELDS = (
    "run_id",
    "scenario_version",
    "scenario",
    "record_count",
    "distribution",
    "seed",
    "strategy",
    "query_category",
    "query_value",
    "expected_count",
    "actual_count",
    "repetition",
    "warmups",
    "scan_batch_size",
    "elapsed_ns",
)


def load_benchmark_manifest(
    manifest_path: Path,
) -> tuple[int, list[BenchmarkScenario]]:
    try:
        content = json.loads(
            manifest_path.read_text(encoding="utf-8")
        )
    except FileNotFoundError:
        raise BenchmarkError(
            f"Nie znaleziono manifestu: {manifest_path}"
        ) from None
    except json.JSONDecodeError:
        raise BenchmarkError(
            f"Manifest nie jest poprawnym JSON: {manifest_path}"
        ) from None

    scenario_version = content.get("scenario_version")

    if type(scenario_version) is not int:
        raise BenchmarkError(
            "Manifest nie zawiera poprawnej wersji scenariuszy."
        )

    raw_scenarios = content.get("scenarios")

    if not isinstance(raw_scenarios, list):
        raise BenchmarkError(
            "Manifest nie zawiera listy scenariuszy."
        )

    scenarios = []

    for item in raw_scenarios:
        try:
            scenario = BenchmarkScenario(
                name=item["name"],
                count=item["count"],
                distribution=item["distribution"],
                seed=item["seed"],
                dataset_path=(
                    manifest_path.parent / item["file"]
                ),
                sha256=item["sha256"],
            )
        except (KeyError, TypeError):
            raise BenchmarkError(
                "Manifest zawiera niepoprawny opis scenariusza."
            ) from None

        scenarios.append(scenario)

    return scenario_version, scenarios


def load_verified_dataset(
    scenario: BenchmarkScenario,
) -> SyntheticDataset:
    try:
        content = scenario.dataset_path.read_bytes()
    except FileNotFoundError:
        raise BenchmarkError(
            f"Nie znaleziono zbioru: {scenario.dataset_path}"
        ) from None

    actual_hash = hashlib.sha256(content).hexdigest()

    if actual_hash != scenario.sha256:
        raise BenchmarkError(
            "Suma SHA-256 zbioru nie zgadza się z manifestem: "
            f"{scenario.dataset_path}"
        )

    dataset = load_dataset(scenario.dataset_path)

    if len(dataset.contacts) != scenario.count:
        raise BenchmarkError(
            f"Scenariusz {scenario.name} powinien zawierać "
            f"{scenario.count} rekordów, ale zawiera "
            f"{len(dataset.contacts)}."
        )

    if dataset.seed != scenario.seed:
        raise BenchmarkError(
            f"Seed zbioru {scenario.name} "
            "nie zgadza się z manifestem."
        )

    if dataset.distribution != scenario.distribution:
        raise BenchmarkError(
            f"Rozkład zbioru {scenario.name} "
            "nie zgadza się z manifestem."
        )

    return dataset


def prepare_database(
    connection: psycopg.Connection,
    dataset: SyntheticDataset,
    keys: KeySet,
) -> None:
    create_plaintext_schema(connection)
    create_encrypted_scan_schema(connection)
    create_blind_index_schema(connection)

    connection.execute(
        """
        TRUNCATE TABLE
            contacts_plaintext,
            contacts_encrypted_scan,
            contacts_blind_index
        """
    )

    replace_plaintext_contacts(
        connection,
        dataset.contacts,
    )

    replace_encrypted_contacts(
        connection,
        dataset.contacts,
        keys.encryption_key,
    )

    replace_blind_index_contacts(
        connection,
        dataset.contacts,
        keys,
    )

    connection.execute("ANALYZE contacts_plaintext")
    connection.execute("ANALYZE contacts_encrypted_scan")
    connection.execute("ANALYZE contacts_blind_index")


def build_search_functions(
    connection: psycopg.Connection,
    keys: KeySet,
    settings: BenchmarkSettings,
) -> dict[str, SearchFunction]:
    return {
        "A_plaintext": lambda surname: search_plaintext(
            connection,
            surname,
        ),
        "B_encrypted_scan": lambda surname: (
            search_encrypted_scan(
                connection,
                surname,
                keys.encryption_key,
                batch_size=settings.scan_batch_size,
            )
        ),
        "C_blind_index": lambda surname: search_blind_index(
            connection,
            surname,
            keys,
        ),
    }


def validate_results(
    strategy_name: str,
    query: SearchQuery,
    results: list[Contact],
) -> int:
    expected_ids = sorted(query.expected_ids)
    actual_ids = sorted(contact.id for contact in results)

    if actual_ids != expected_ids:
        raise BenchmarkError(
            f"Strategia {strategy_name} zwróciła "
            f"niepoprawne wyniki dla zapytania "
            f"{query.category!r}. "
            f"Oczekiwano {expected_ids}, "
            f"otrzymano {actual_ids}."
        )

    return len(actual_ids)


def rotate_names(
    names: list[str],
    offset: int,
) -> list[str]:
    position = offset % len(names)

    return names[position:] + names[:position]


def run_search_benchmark(
    connection: psycopg.Connection,
    keys: KeySet,
    manifest_path: Path,
    output_path: Path,
    settings: BenchmarkSettings,
    *,
    selected_scenarios: set[str] | None = None,
    clock: Callable[[], int] = time.perf_counter_ns,
) -> Path:
    scenario_version, scenarios = load_benchmark_manifest(
        manifest_path
    )

    if selected_scenarios:
        available_names = {
            scenario.name for scenario in scenarios
        }
        unknown_names = selected_scenarios - available_names

        if unknown_names:
            raise BenchmarkError(
                "Nieznane scenariusze: "
                + ", ".join(sorted(unknown_names))
            )

        scenarios = [
            scenario
            for scenario in scenarios
            if scenario.name in selected_scenarios
        ]

    output_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    run_id = uuid4().hex

    with output_path.open(
        "x",
        encoding="utf-8",
        newline="",
    ) as output_file:
        writer = csv.DictWriter(
            output_file,
            fieldnames=CSV_FIELDS,
        )
        writer.writeheader()

        for scenario in scenarios:
            print(f"Scenariusz: {scenario.name}")

            dataset = load_verified_dataset(scenario)

            prepare_database(
                connection,
                dataset,
                keys,
            )

            search_functions = build_search_functions(
                connection,
                keys,
                settings,
            )

            strategy_names = list(search_functions)

            for query in dataset.queries:
                print(
                    f"  Zapytanie: {query.category} "
                    f"({len(query.expected_ids)} wyników)"
                )

                for warmup_number in range(settings.warmups):
                    order = rotate_names(
                        strategy_names,
                        warmup_number,
                    )

                    for strategy_name in order:
                        results = search_functions[strategy_name](
                            query.surname
                        )

                        validate_results(
                            strategy_name,
                            query,
                            results,
                        )

                for repetition in range(
                    1,
                    settings.repetitions + 1,
                ):
                    order = rotate_names(
                        strategy_names,
                        repetition - 1,
                    )

                    for strategy_name in order:
                        search_function = search_functions[
                            strategy_name
                        ]

                        started_ns = clock()

                        results = search_function(
                            query.surname
                        )

                        elapsed_ns = clock() - started_ns

                        actual_count = validate_results(
                            strategy_name,
                            query,
                            results,
                        )

                        writer.writerow(
                            {
                                "run_id": run_id,
                                "scenario_version": (
                                    scenario_version
                                ),
                                "scenario": scenario.name,
                                "record_count": scenario.count,
                                "distribution": (
                                    scenario.distribution
                                ),
                                "seed": scenario.seed,
                                "strategy": strategy_name,
                                "query_category": (
                                    query.category
                                ),
                                "query_value": query.surname,
                                "expected_count": len(
                                    query.expected_ids
                                ),
                                "actual_count": actual_count,
                                "repetition": repetition,
                                "warmups": settings.warmups,
                                "scan_batch_size": (
                                    settings.scan_batch_size
                                ),
                                "elapsed_ns": elapsed_ns,
                            }
                        )

            output_file.flush()

    return output_path
