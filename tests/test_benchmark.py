import csv
import hashlib
import json
from collections import Counter
from itertools import count

import pytest

from cse_benchmark import benchmark
from cse_benchmark.benchmark import (
    BenchmarkError,
    BenchmarkSettings,
    load_benchmark_manifest,
    load_verified_dataset,
    rotate_names,
    run_search_benchmark,
    validate_results,
)
from cse_benchmark.data import (
    SearchQuery,
    SyntheticDataset,
    save_dataset,
)
from cse_benchmark.keys import KeySet
from cse_benchmark.models import Contact


def write_single_scenario(tmp_path):
    contact = Contact(
        id=1,
        surname="Nowak",
        email="a@example.com",
    )
    query = SearchQuery(
        category="one",
        surname="Nowak",
        expected_ids=[1],
    )
    dataset = SyntheticDataset(
        seed=42,
        distribution="uniform",
        contacts=[contact],
        queries=[query],
    )

    dataset_path = tmp_path / "uniform_1_seed42.json"
    save_dataset(dataset, dataset_path)

    dataset_hash = hashlib.sha256(
        dataset_path.read_bytes()
    ).hexdigest()

    manifest = {
        "scenario_version": 1,
        "scenarios": [
            {
                "name": "uniform_1_seed42",
                "count": 1,
                "distribution": "uniform",
                "seed": 42,
                "file": dataset_path.name,
                "sha256": dataset_hash,
            }
        ],
    }

    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(
        json.dumps(manifest),
        encoding="utf-8",
    )

    return manifest_path, dataset, contact


def test_default_benchmark_settings():
    settings = BenchmarkSettings()

    assert settings.warmups == 3
    assert settings.repetitions == 30
    assert settings.scan_batch_size == 100


@pytest.mark.parametrize(
    "arguments",
    [
        {"warmups": -1},
        {"warmups": True},
        {"repetitions": 0},
        {"repetitions": True},
        {"scan_batch_size": 0},
        {"scan_batch_size": True},
    ],
)
def test_benchmark_settings_reject_invalid_values(arguments):
    with pytest.raises(ValueError):
        BenchmarkSettings(**arguments)


def test_strategy_names_are_rotated():
    names = ["A", "B", "C"]

    assert rotate_names(names, 0) == ["A", "B", "C"]
    assert rotate_names(names, 1) == ["B", "C", "A"]
    assert rotate_names(names, 2) == ["C", "A", "B"]
    assert rotate_names(names, 3) == ["A", "B", "C"]


def test_result_validation_accepts_matching_ids_in_any_order():
    query = SearchQuery(
        category="few",
        surname="Nowak",
        expected_ids=[1, 3],
    )
    results = [
        Contact(id=3, surname="Nowak", email="c@example.com"),
        Contact(id=1, surname="Nowak", email="a@example.com"),
    ]

    assert validate_results("A_plaintext", query, results) == 2


def test_result_validation_rejects_different_ids():
    query = SearchQuery(
        category="one",
        surname="Nowak",
        expected_ids=[1],
    )
    results = [
        Contact(id=2, surname="Nowak", email="b@example.com")
    ]

    with pytest.raises(BenchmarkError, match="niepoprawne wyniki"):
        validate_results("A_plaintext", query, results)


def test_manifest_dataset_is_loaded_and_hash_is_verified(tmp_path):
    manifest_path, expected_dataset, _ = write_single_scenario(
        tmp_path
    )

    version, scenarios = load_benchmark_manifest(manifest_path)
    loaded_dataset = load_verified_dataset(scenarios[0])

    assert version == 1
    assert loaded_dataset == expected_dataset

    scenarios[0].dataset_path.write_text(
        "zmieniona zawartość",
        encoding="utf-8",
    )

    with pytest.raises(BenchmarkError, match="SHA-256"):
        load_verified_dataset(scenarios[0])


def test_benchmark_writes_only_measured_repetitions(
    tmp_path,
    monkeypatch,
):
    manifest_path, expected_dataset, contact = (
        write_single_scenario(tmp_path)
    )
    output_path = tmp_path / "results.csv"
    settings = BenchmarkSettings(
        warmups=2,
        repetitions=3,
        scan_batch_size=100,
    )
    keys = KeySet(
        encryption_key=b"a" * 32,
        index_key=b"b" * 32,
    )

    prepared_datasets = []
    calls = Counter()

    def fake_prepare_database(connection, dataset, received_keys):
        assert connection is fake_connection
        assert received_keys is keys
        prepared_datasets.append(dataset)

    def make_search(strategy_name):
        def search(surname):
            assert surname == "Nowak"
            calls[strategy_name] += 1
            return [contact]

        return search

    def fake_build_search_functions(
        connection,
        received_keys,
        received_settings,
    ):
        assert connection is fake_connection
        assert received_keys is keys
        assert received_settings is settings

        return {
            "A_plaintext": make_search("A_plaintext"),
            "B_encrypted_scan": make_search("B_encrypted_scan"),
            "C_blind_index": make_search("C_blind_index"),
        }

    monkeypatch.setattr(
        benchmark,
        "prepare_database",
        fake_prepare_database,
    )
    monkeypatch.setattr(
        benchmark,
        "build_search_functions",
        fake_build_search_functions,
    )

    fake_connection = object()
    clock_values = count(start=0, step=10)

    result_path = run_search_benchmark(
        connection=fake_connection,
        keys=keys,
        manifest_path=manifest_path,
        output_path=output_path,
        settings=settings,
        clock=clock_values.__next__,
    )

    with result_path.open(encoding="utf-8", newline="") as file:
        rows = list(csv.DictReader(file))

    assert prepared_datasets == [expected_dataset]
    assert calls == {
        "A_plaintext": 5,
        "B_encrypted_scan": 5,
        "C_blind_index": 5,
    }

    assert len(rows) == 9
    assert {row["strategy"] for row in rows} == {
        "A_plaintext",
        "B_encrypted_scan",
        "C_blind_index",
    }
    assert Counter(row["repetition"] for row in rows) == {
        "1": 3,
        "2": 3,
        "3": 3,
    }
    assert {row["warmups"] for row in rows} == {"2"}
    assert {row["expected_count"] for row in rows} == {"1"}
    assert {row["actual_count"] for row in rows} == {"1"}
    assert {row["elapsed_ns"] for row in rows} == {"10"}
    assert len({row["run_id"] for row in rows}) == 1
