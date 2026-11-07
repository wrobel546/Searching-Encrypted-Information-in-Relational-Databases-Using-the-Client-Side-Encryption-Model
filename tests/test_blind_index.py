import os
from uuid import uuid4

import psycopg
import pytest
from cryptography.exceptions import InvalidTag
from psycopg import sql

from cse_benchmark.crypto import generate_key, surname_token
from cse_benchmark.data import generate_dataset
from cse_benchmark.db import (
    connect,
    create_blind_index_schema,
    create_encrypted_scan_schema,
    create_plaintext_schema,
)
from cse_benchmark.keys import KeySet
from cse_benchmark.models import Contact
from cse_benchmark.strategies.blind_index import (
    replace_blind_index_contacts,
    search_blind_index,
)
from cse_benchmark.strategies.encrypted_scan import (
    replace_encrypted_contacts,
    search_encrypted_scan,
)
from cse_benchmark.strategies.plaintext import (
    replace_plaintext_contacts,
    search_plaintext,
)


@pytest.fixture
def keys():
    return KeySet(
        encryption_key=generate_key(),
        index_key=generate_key(),
    )


def test_token_is_repeatable_and_uses_normalization(keys):
    first = surname_token("  KOWALSKI  ", keys.index_key)
    second = surname_token("Kowalski", keys.index_key)

    assert first == second
    assert len(first) == 32

    assert surname_token("Żółć", keys.index_key) == surname_token(
        "Żo\u0301łc\u0301", keys.index_key
    )

    assert surname_token("Żółć", keys.index_key) != surname_token(
        "Zolc", keys.index_key
    )


def test_token_changes_with_value_or_key(keys):
    token = surname_token("Nowak", keys.index_key)
    different_key = bytes([keys.index_key[0] ^ 1]) + keys.index_key[1:]

    assert token != surname_token("Kowalski", keys.index_key)
    assert token != surname_token("Nowak", different_key)


def test_token_rejects_invalid_key_length():
    with pytest.raises(ValueError, match="32 bajty"):
        surname_token("Nowak", b"short")


@pytest.fixture
def database():
    if os.environ.get("CSE_TEST_DB") != "1":
        pytest.skip("Set CSE_TEST_DB=1 to test a running PostgreSQL database")

    with connect() as connection:
        with connection.transaction(force_rollback=True):
            schema_name = f"test_blind_{uuid4().hex}"

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
            create_blind_index_schema(connection)

            yield connection



@pytest.mark.integration
@pytest.mark.parametrize("distribution", ["uniform", "skewed"])
def test_all_strategies_return_expected_contacts(database, keys, distribution):
    dataset = generate_dataset(
        count=1000,
        seed=42,
        distribution=distribution,
    )

    replace_plaintext_contacts(database, dataset.contacts)
    replace_encrypted_contacts(
        database, dataset.contacts, keys.encryption_key
    )
    replace_blind_index_contacts(database, dataset.contacts, keys)

    by_id = {contact.id: contact for contact in dataset.contacts}

    for query in dataset.queries:
        expected = [
            by_id[record_id]
            for record_id in sorted(query.expected_ids)
        ]

        actual_a = search_plaintext(database, query.surname)
        actual_b = search_encrypted_scan(
            database, query.surname, keys.encryption_key
        )
        actual_c = search_blind_index(database, query.surname, keys)

        for actual in (actual_a, actual_b, actual_c):
            assert sorted(actual, key=lambda item: item.id) == expected



@pytest.mark.integration
def test_equal_surnames_have_equal_tokens_and_different_ciphertexts(
    database, keys
):
    contacts = [
        Contact(id=1, surname="Nowak", email="a@example.com"),
        Contact(id=2, surname="Nowak", email="b@example.com"),
    ]

    replace_blind_index_contacts(database, contacts, keys)

    rows = database.execute(
        """
        SELECT surname_ciphertext, surname_token
        FROM contacts_blind_index
        ORDER BY id
        """
    ).fetchall()

    assert rows[0][0] != rows[1][0]
    assert rows[0][1] == rows[1][1]
    assert len(rows[0][1]) == 32


@pytest.mark.integration
def test_false_candidate_is_rejected_after_decryption(database, keys):
    nowak = Contact(id=1, surname="Nowak", email="a@example.com")
    kowalski = Contact(id=2, surname="Kowalski", email="b@example.com")

    replace_blind_index_contacts(database, [nowak, kowalski], keys)

    token = surname_token("Nowak", keys.index_key)

    database.execute(
        """
        UPDATE contacts_blind_index
        SET surname_token = %s
        WHERE id = 2
        """,
        (token,),
    )

    candidate_count = database.execute(
        """
        SELECT COUNT(*)
        FROM contacts_blind_index
        WHERE surname_token = %s
        """,
        (token,),
    ).fetchone()[0]

    assert candidate_count == 2
    assert search_blind_index(database, "Nowak", keys) == [nowak]



@pytest.mark.integration
def test_modified_ciphertext_is_rejected(database, keys):
    contact = Contact(id=1, surname="Nowak", email="a@example.com")
    replace_blind_index_contacts(database, [contact], keys)

    payload = database.execute(
        "SELECT surname_ciphertext FROM contacts_blind_index WHERE id = 1"
    ).fetchone()[0]

    modified = bytearray(payload)
    modified[-1] ^= 1

    database.execute(
        """
        UPDATE contacts_blind_index
        SET surname_ciphertext = %s
        WHERE id = 1
        """,
        (bytes(modified),),
    )

    with pytest.raises(InvalidTag):
        search_blind_index(database, "Nowak", keys)


@pytest.mark.integration
def test_failed_replacement_preserves_previous_data(database, keys):
    original = Contact(id=1, surname="Nowak", email="a@example.com")
    replace_blind_index_contacts(database, [original], keys)

    invalid_contacts = [
        Contact(id=2, surname="Kowalski", email="b@example.com"),
        Contact(id=2, surname="Wiśniewski", email="c@example.com"),
    ]

    with pytest.raises(psycopg.errors.UniqueViolation):
        replace_blind_index_contacts(database, invalid_contacts, keys)

    assert search_blind_index(database, "Nowak", keys) == [original]
    assert search_blind_index(database, "Kowalski", keys) == []


@pytest.mark.integration
def test_token_has_btree_index(database):
    row = database.execute(
        """
        SELECT indexdef
        FROM pg_indexes
        WHERE schemaname = current_schema()
          AND tablename = 'contacts_blind_index'
          AND indexname = 'idx_contacts_blind_index_surname_token'
        """
    ).fetchone()

    assert row is not None
    assert "USING btree (surname_token)" in row[0]