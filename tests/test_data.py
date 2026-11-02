import json
from collections import Counter

import pytest

from cse_benchmark.data import (
    BASE_SURNAMES,
    generate_dataset,
    save_dataset,
)
from cse_benchmark.normalization import normalize_surname


@pytest.mark.parametrize("distribution", ["uniform", "skewed"])
def test_generates_1000_contacts_with_unique_ids_and_emails(distribution):
    dataset = generate_dataset(distribution=distribution)

    assert len(dataset.contacts) == 1000
    assert [contact.id for contact in dataset.contacts] == list(range(1, 1001))
    assert len({contact.email for contact in dataset.contacts}) == 1000


@pytest.mark.parametrize("distribution", ["uniform", "skewed"])
def test_same_seed_reproduces_the_dataset(distribution):
    first = generate_dataset(seed=42, distribution=distribution)
    second = generate_dataset(seed=42, distribution=distribution)

    assert first == second


def test_different_seed_changes_contact_assignment():
    first = generate_dataset(seed=42)
    second = generate_dataset(seed=43)

    assert first.contacts != second.contacts

    first_counts = Counter(contact.surname for contact in first.contacts)
    second_counts = Counter(contact.surname for contact in second.contacts)

    assert first_counts == second_counts


def test_uniform_distribution_balances_base_surnames():
    dataset = generate_dataset(distribution="uniform")
    counts = Counter(contact.surname for contact in dataset.contacts)

    base_counts = [counts[surname] for surname in BASE_SURNAMES]

    assert sum(base_counts) == 996
    assert max(base_counts) - min(base_counts) <= 1


def test_skewed_distribution_has_a_dominant_surname():
    dataset = generate_dataset(distribution="skewed")
    counts = Counter(contact.surname for contact in dataset.contacts)

    assert counts["Nowak"] == 498

    other_counts = [counts[surname] for surname in BASE_SURNAMES[1:]]

    assert sum(other_counts) == 498
    assert max(other_counts) - min(other_counts) <= 1


@pytest.mark.parametrize(
    ("distribution", "many_count"),
    [
        ("uniform", 100),
        ("skewed", 498),
    ],
)
def test_query_results_cover_zero_one_few_and_many(distribution, many_count):
    dataset = generate_dataset(distribution=distribution)
    queries = {query.category: query for query in dataset.queries}

    assert set(queries) == {"zero", "one", "few", "many"}
    assert len(queries["zero"].expected_ids) == 0
    assert len(queries["one"].expected_ids) == 1
    assert len(queries["few"].expected_ids) == 3
    assert len(queries["many"].expected_ids) == many_count

    for query in dataset.queries:
        matching_ids = {
            contact.id
            for contact in dataset.contacts
            if normalize_surname(contact.surname)
            == normalize_surname(query.surname)
        }

        assert set(query.expected_ids) == matching_ids
        assert len(query.expected_ids) == len(matching_ids)


def test_saves_contacts_and_expected_results_to_json(tmp_path):
    dataset = generate_dataset(seed=42)
    path = tmp_path / "generated" / "dataset.json"

    save_dataset(dataset, path)

    saved = json.loads(path.read_text(encoding="utf-8"))

    assert saved["seed"] == 42
    assert saved["distribution"] == "uniform"
    assert len(saved["contacts"]) == 1000

    first_contact = dataset.contacts[0]
    assert saved["contacts"][0] == {
        "id": first_contact.id,
        "surname": first_contact.surname,
        "email": first_contact.email,
    }

    assert saved["queries"] == [
        {
            "category": query.category,
            "surname": query.surname,
            "expected_ids": query.expected_ids,
        }
        for query in dataset.queries
    ]


def test_rejects_too_small_dataset():
    with pytest.raises(ValueError, match="co najmniej 100"):
        generate_dataset(count=99)


def test_rejects_unknown_distribution():
    with pytest.raises(ValueError, match="Rozkład"):
        generate_dataset(distribution="unknown")