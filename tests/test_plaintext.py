import os
from uuid import uuid4

import psycopg
import pytest
from psycopg import sql

from cse_benchmark.data import generate_dataset
from cse_benchmark.db import connect, create_plaintext_schema
from cse_benchmark.models import Contact
from cse_benchmark.strategies.plaintext import (
    replace_plaintext_contacts,
    search_plaintext,
)


pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        os.environ.get("CSE_TEST_DB") != "1",
        reason="Set CSE_TEST_DB=1 to test a running PostgreSQL database",
    ),
]


@pytest.fixture
def database():
    with connect() as connection:
        with connection.transaction(force_rollback=True):
            schema_name = f"test_plaintext_{uuid4().hex}"

            connection.execute(
                sql.SQL("CREATE SCHEMA {}").format(
                    sql.Identifier(schema_name)
                )
            )

            connection.execute(
                sql.SQL("SET LOCAL search_path TO {}").format(
                    sql.Identifier(schema_name)
                )
            )

            create_plaintext_schema(connection)

            yield connection


@pytest.mark.parametrize("distribution", ["uniform", "skewed"])
def test_search_matches_expected_ids(database, distribution):
    dataset = generate_dataset(
        count=1000,
        seed=42,
        distribution=distribution,
    )

    replace_plaintext_contacts(database, dataset.contacts)

    row = database.execute(
        "SELECT COUNT(*) FROM contacts_plaintext"
    ).fetchone()

    assert row == (1000,)

    contacts_by_id = {
        contact.id: contact
        for contact in dataset.contacts
    }

    for query in dataset.queries:
        results = search_plaintext(database, query.surname)
        actual_ids = sorted(contact.id for contact in results)

        assert actual_ids == sorted(query.expected_ids), query.category

        for contact in results:
            assert contact == contacts_by_id[contact.id]


def test_search_normalizes_query_and_preserves_original_values(database):
    contact = Contact(
        id=1,
        surname="  ŻÓŁĆ  ",
        email="jan@example.com",
    )

    replace_plaintext_contacts(database, [contact])

    assert search_plaintext(database, "żółć") == [contact]
    assert search_plaintext(database, "  Żo\u0301łc\u0301  ") == [contact]
    assert search_plaintext(database, "Zolc") == []


def test_search_handles_apostrophe_as_part_of_surname(database):
    contact = Contact(
        id=1,
        surname="O'Connor",
        email="kontakt@example.com",
    )

    replace_plaintext_contacts(database, [contact])

    assert search_plaintext(database, "o'connor") == [contact]
    assert search_plaintext(database, "' OR 1=1 --") == []


def test_replacement_removes_previous_dataset(database):
    previous = Contact(
        id=1,
        surname="Nowak",
        email="pierwszy@example.com",
    )
    replacement = Contact(
        id=2,
        surname="Kowalski",
        email="drugi@example.com",
    )

    replace_plaintext_contacts(database, [previous])
    replace_plaintext_contacts(database, [replacement])

    assert search_plaintext(database, "Nowak") == []
    assert search_plaintext(database, "Kowalski") == [replacement]

    row = database.execute(
        "SELECT COUNT(*) FROM contacts_plaintext"
    ).fetchone()

    assert row == (1,)


def test_failed_replacement_preserves_previous_dataset(database):
    original = Contact(
        id=1,
        surname="Nowak",
        email="oryginalny@example.com",
    )

    replace_plaintext_contacts(database, [original])

    invalid_contacts = [
        Contact(id=2, surname="Kowalski", email="a@example.com"),
        Contact(id=2, surname="Wiśniewski", email="b@example.com"),
    ]

    with pytest.raises(psycopg.errors.UniqueViolation):
        replace_plaintext_contacts(database, invalid_contacts)

    assert search_plaintext(database, "Nowak") == [original]
    assert search_plaintext(database, "Kowalski") == []


def test_normalized_surname_has_btree_index(database):
    row = database.execute(
        """
        SELECT indexdef
        FROM pg_indexes
        WHERE schemaname = current_schema()
          AND tablename = 'contacts_plaintext'
          AND indexname = 'idx_contacts_plaintext_surname_normalized'
        """
    ).fetchone()

    assert row is not None
    assert "USING btree (surname_normalized)" in row[0]