import json
import random
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Literal

from .models import Contact
from .normalization import normalize_surname


Distribution = Literal["uniform", "skewed"]

BASE_SURNAMES = (
    "Nowak",
    "Kowalski",
    "Wiśniewski",
    "Wójcik",
    "Kowalczyk",
    "Kamiński",
    "Lewandowski",
    "Zieliński",
    "Szymański",
    "Woźniak",
)


@dataclass
class SearchQuery:
    category: str
    surname: str
    expected_ids: list[int]


@dataclass
class SyntheticDataset:
    seed: int
    distribution: Distribution
    contacts: list[Contact]
    queries: list[SearchQuery]


def generate_dataset(count: int = 1000,seed: int = 42,distribution: Distribution = "uniform",) -> SyntheticDataset:
    if count < 100:
        raise ValueError("Liczba rekordów musi wynosić co najmniej 100.")

    if distribution not in ("uniform", "skewed"):
        raise ValueError("Rozkład musi mieć wartość 'uniform' lub 'skewed'.")

    rng = random.Random(seed)

    surnames = [
        "UnikatowyTestowy",
        "RzadkiTestowy",
        "RzadkiTestowy",
        "RzadkiTestowy",
    ]

    remaining = count - len(surnames)

    if distribution == "uniform":
        surnames.extend(
            BASE_SURNAMES[index % len(BASE_SURNAMES)]
            for index in range(remaining)
        )
    else:
        frequent_count = remaining // 2
        surnames.extend([BASE_SURNAMES[0]] * frequent_count)

        other_surnames = BASE_SURNAMES[1:]
        surnames.extend(
            other_surnames[index % len(other_surnames)]
            for index in range(remaining - frequent_count)
        )

    rng.shuffle(surnames)

    contacts = [
        Contact(
            id=index,
            surname=surname,
            email=f"kontakt{index}@example.com",
        )
        for index, surname in enumerate(surnames, start=1)
    ]

    query_definitions = [
        ("zero", "NieobecnyTestowy"),
        ("one", "UnikatowyTestowy"),
        ("few", "RzadkiTestowy"),
        ("many", "  NOWAK  "),
    ]

    queries = []

    for category, surname in query_definitions:
        normalized = normalize_surname(surname)

        expected_ids = [
            contact.id
            for contact in contacts
            if normalize_surname(contact.surname) == normalized
        ]

        queries.append(
            SearchQuery(
                category=category,
                surname=surname,
                expected_ids=expected_ids,
            )
        )

    return SyntheticDataset(
        seed=seed,
        distribution=distribution,
        contacts=contacts,
        queries=queries,
    )


def save_dataset(dataset: SyntheticDataset, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)

    content = json.dumps(
        asdict(dataset),
        ensure_ascii=False,
        indent=2,
    )

    path.write_text(content, encoding="utf-8")