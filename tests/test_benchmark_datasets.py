import hashlib
import json
from collections import Counter

import pytest

from cse_benchmark.benchmark_datasets import (
    BENCHMARK_CONFIGS,
    BenchmarkDatasetConfig,
    export_benchmark_datasets,
)
from cse_benchmark.data import (
    BASE_SURNAMES,
    QUERY_DEFINITIONS,
    generate_dataset,
)
from cse_benchmark.normalization import normalize_surname


def test_configs_cover_all_sizes_and_distributions():
    actual = {
        (config.count, config.distribution, config.seed)
        for config in BENCHMARK_CONFIGS
    }

    expected = {
        (1_000, "uniform", 42),
        (1_000, "skewed", 42),
        (10_000, "uniform", 42),
        (10_000, "skewed", 42),
        (100_000, "uniform", 42),
        (100_000, "skewed", 42),
    }

    assert actual == expected
    assert len(BENCHMARK_CONFIGS) == 6
    assert len({config.name for config in BENCHMARK_CONFIGS}) == 6


@pytest.mark.parametrize("config", BENCHMARK_CONFIGS, ids=lambda config: config.name,)
def test_scenario_has_expected_distribution_and_queries(config):
    dataset = generate_dataset(count=config.count, seed=config.seed, distribution=config.distribution,)

    assert len(dataset.contacts) == config.count
    assert [contact.id for contact in dataset.contacts] == list(range(1, config.count + 1))
    assert len({contact.email for contact in dataset.contacts}) == config.count

    counts = Counter(contact.surname for contact in dataset.contacts)

    assert counts["UnikatowyTestowy"] == 1
    assert counts["RzadkiTestowy"] == 3
    assert counts["NieobecnyTestowy"] == 0

    remaining = config.count - 4

    if config.distribution == "uniform":
        base_counts = [
            counts[surname] for surname in BASE_SURNAMES
        ]

        assert sum(base_counts) == remaining
        assert max(base_counts) - min(base_counts) <= 1

        many_count = config.count // 10
    else:
        many_count = remaining // 2

        assert counts["Nowak"] == many_count

        other_counts = [
            counts[surname] for surname in BASE_SURNAMES[1:]
        ]

        assert sum(other_counts) == remaining - many_count
        assert max(other_counts) - min(other_counts) <= 1

    assert [
        (query.category, query.surname)
        for query in dataset.queries
    ] == list(QUERY_DEFINITIONS)

    assert {
        query.category: len(query.expected_ids)
        for query in dataset.queries
    } == {
        "zero": 0,
        "one": 1,
        "few": 3,
        "many": many_count,
    }

    for query in dataset.queries:
        normalized_query = normalize_surname(query.surname)

        matching_ids = [
            contact.id
            for contact in dataset.contacts
            if normalize_surname(contact.surname) == normalized_query
        ]

        assert query.expected_ids == matching_ids


@pytest.mark.parametrize( "config", BENCHMARK_CONFIGS, ids=lambda config: config.name,)
def test_scenario_is_reproducible(config):
    first = generate_dataset(
        count=config.count,
        seed=config.seed,
        distribution=config.distribution,
    )
    second = generate_dataset(
        count=config.count,
        seed=config.seed,
        distribution=config.distribution,
    )

    assert first == second


def test_export_writes_datasets_and_manifest(tmp_path):
    output_dir = tmp_path / "benchmark"

    manifest_path = export_benchmark_datasets(output_dir)

    manifest = json.loads(
        manifest_path.read_text(encoding="utf-8")
    )

    assert manifest["scenario_version"] == 1
    assert len(manifest["scenarios"]) == 6

    assert manifest["queries"] == [
        {"category": category, "surname": surname}
        for category, surname in QUERY_DEFINITIONS
    ]

    assert {
        scenario["name"] for scenario in manifest["scenarios"]
    } == {
        config.name for config in BENCHMARK_CONFIGS
    }

    for scenario in manifest["scenarios"]:
        dataset_path = output_dir / scenario["file"]

        assert dataset_path.is_file()

        content = dataset_path.read_bytes()

        assert hashlib.sha256(content).hexdigest() == scenario["sha256"]

        saved = json.loads(content)

        assert len(saved["contacts"]) == scenario["count"]
        assert saved["seed"] == scenario["seed"]
        assert saved["distribution"] == scenario["distribution"]

        assert [
            {
                "category": query["category"],
                "surname": query["surname"],
            }
            for query in saved["queries"]
        ] == manifest["queries"]

        assert {
            query["category"]: len(query["expected_ids"])
            for query in saved["queries"]
        } == scenario["expected_counts"]


def test_config_rejects_unsupported_size():
    with pytest.raises(ValueError, match="Rozmiar benchmarku"):
        BenchmarkDatasetConfig(
            count=5_000,
            distribution="uniform",
        )