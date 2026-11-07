import os
from uuid import uuid4

import psycopg
import pytest
from cryptography.exceptions import InvalidTag
from psycopg import sql

from cse_benchmark.crypto import generate_key
from cse_benchmark.data import generate_dataset
from cse_benchmark.db import (
    connect,
    create_encrypted_scan_schema,
    create_plaintext_schema,
)
from cse_benchmark.models import Contact
from cse_benchmark.strategies.encrypted_scan import (
    replace_encrypted_contacts,
    search_encrypted_scan,
)
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
            schema_name = f"test_scan_{uuid4().hex}"

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
            create_encrypted_scan_schema(connection)

            yield connection


@pytest.fixture
def key():
    return generate_key()


@pytest.mark.parametrize("distribution", ["uniform", "skewed"])
@pytest.mark.parametrize("batch_size", [128, 2000])
def test_scan_matches_expected_results_and_plaintext(
    database, key, distribution, batch_size
):
    dataset = generate_dataset(
        count=1000,
        seed=42,
        distribution=distribution,
    )

    replace_plaintext_contacts(database, dataset.contacts)
    replace_encrypted_contacts(database, dataset.contacts, key)

    by_id = {contact.id: contact for contact in dataset.contacts}

    for query in dataset.queries:
        encrypted_results = search_encrypted_scan(
            database,
            query.surname,
            key,
            batch_size=batch_size,
        )
        plaintext_results = search_plaintext(database, query.surname)

        encrypted_ids = sorted(contact.id for contact in encrypted_results)
        plaintext_ids = sorted(contact.id for contact in plaintext_results)

        assert encrypted_ids == sorted(query.expected_ids), query.category
        assert encrypted_ids == plaintext_ids

        for contact in encrypted_results:
            assert contact == by_id[contact.id]


def test_empty_table_returns_no_results(database, key):
    assert search_encrypted_scan(database, "Nowak", key) == []


def test_normalization_and_single_row_batches(database, key):
    contacts = [
        Contact(id=1, surname="  ŻÓŁĆ  ", email="a@example.com"),
        Contact(id=2, surname="Żółć", email="b@example.com"),
        Contact(id=3, surname="Zolc", email="c@example.com"),
    ]

    replace_encrypted_contacts(database, contacts, key)

    results = search_encrypted_scan(
        database,
        "Żo\u0301łc\u0301",
        key,
        batch_size=1,
    )

    assert sorted(results, key=lambda contact: contact.id) == contacts[:2]


def test_repeated_values_have_different_ciphertexts(database, key):
    contacts = [
        Contact(id=1, surname="Nowak", email="same@example.com"),
        Contact(id=2, surname="Nowak", email="same@example.com"),
    ]

    replace_encrypted_contacts(database, contacts, key)

    rows = database.execute(
        """
        SELECT surname_ciphertext, email_ciphertext
        FROM contacts_encrypted_scan
        ORDER BY id
        """
    ).fetchall()

    assert isinstance(rows[0][0], bytes)
    assert rows[0][0] != rows[1][0]
    assert rows[0][1] != rows[1][1]

    results = search_encrypted_scan(database, "Nowak", key)
    assert sorted(results, key=lambda contact: contact.id) == contacts


def test_wrong_key_is_rejected(database, key):
    contact = Contact(id=1, surname="Nowak", email="a@example.com")
    replace_encrypted_contacts(database, [contact], key)

    wrong_key = bytes([key[0] ^ 1]) + key[1:]

    with pytest.raises(InvalidTag):
        search_encrypted_scan(database, "Nowak", wrong_key)


def test_modified_ciphertext_aborts_scan(database, key):
    contact = Contact(id=1, surname="Nowak", email="a@example.com")
    replace_encrypted_contacts(database, [contact], key)

    payload = database.execute(
        "SELECT surname_ciphertext FROM contacts_encrypted_scan WHERE id = 1"
    ).fetchone()[0]

    modified = bytearray(payload)
    modified[-1] ^= 1

    database.execute(
        """
        UPDATE contacts_encrypted_scan
        SET surname_ciphertext = %s
        WHERE id = 1
        """,
        (bytes(modified),),
    )

    with pytest.raises(InvalidTag):
        search_encrypted_scan(database, "Kowalski", key)


def test_failed_replacement_preserves_previous_data(database, key):
    original = Contact(id=1, surname="Nowak", email="a@example.com")
    replace_encrypted_contacts(database, [original], key)

    invalid_contacts = [
        Contact(id=2, surname="Kowalski", email="b@example.com"),
        Contact(id=2, surname="Wiśniewski", email="c@example.com"),
    ]

    with pytest.raises(psycopg.errors.UniqueViolation):
        replace_encrypted_contacts(database, invalid_contacts, key)

    assert search_encrypted_scan(database, "Nowak", key) == [original]
    assert search_encrypted_scan(database, "Kowalski", key) == []


@pytest.mark.parametrize("batch_size", [0, -1, True])
def test_invalid_batch_size_is_rejected(database, key, batch_size):
    with pytest.raises(ValueError, match="Rozmiar partii"):
        search_encrypted_scan(
            database,
            "Nowak",
            key,
            batch_size=batch_size,
        )