import os
from uuid import uuid4

import pytest
from psycopg import sql

from cse_benchmark.crypto import (
    decrypt_field,
    generate_key,
    surname_token,
)
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
    update_blind_index_surname,
)
from cse_benchmark.strategies.encrypted_scan import (
    replace_encrypted_contacts,
    search_encrypted_scan,
    update_encrypted_scan_surname,
)
from cse_benchmark.strategies.plaintext import (
    replace_plaintext_contacts,
    search_plaintext,
    update_plaintext_surname,
)


pytestmark = pytest.mark.integration

@pytest.fixture
def keys():
    return KeySet(
        encryption_key=generate_key(),
        index_key=generate_key(),
    )


@pytest.fixture
def database():
    if os.environ.get("CSE_TEST_DB") != "1":
        pytest.skip("Ustaw CSE_TEST_DB=1, aby uruchomić testy bazy.")

    with connect() as connection:
        with connection.transaction(force_rollback=True):
            schema_name = f"test_strategies_{uuid4().hex}"

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


@pytest.fixture
def contacts():
    return [
        Contact(id=1, surname="Nowak", email="a@example.com"),
        Contact(id=2, surname="NOWAK", email="b@example.com"),
        Contact(id=3, surname="  Nowak  ", email="c@example.com"),
        Contact(id=4, surname="Żółć", email="d@example.com"),
        Contact(id=5, surname="Wiśniewski", email="e@example.com"),
        Contact(id=6, surname="O'Connor", email="f@example.com"),
        Contact(id=7, surname="Nowak Kowalski", email="g@example.com"),
    ]


def load_all_strategies(database, contacts, keys):
    replace_plaintext_contacts(database, contacts)
    replace_encrypted_contacts(
        database, contacts, keys.encryption_key
    )
    replace_blind_index_contacts(database, contacts, keys)


def search_all_strategies(database, surname, keys):
    return {
        "A": search_plaintext(database, surname),
        "B": search_encrypted_scan(
            database,
            surname,
            keys.encryption_key,
            batch_size=2,
        ),
        "C": search_blind_index(database, surname, keys),
    }


def assert_matching_ids(database, surname, keys, expected_ids):
    results = search_all_strategies(database, surname, keys)

    for strategy, found_contacts in results.items():
        actual_ids = sorted(contact.id for contact in found_contacts)

        assert actual_ids == sorted(expected_ids), (
            f"Strategia {strategy}, zapytanie {surname!r}: "
            f"oczekiwano {sorted(expected_ids)}, "
            f"otrzymano {actual_ids}"
        )


@pytest.mark.parametrize(
    ("query", "expected_ids"),
    [
        ("Nieobecny", []),
        ("Nowak", [1, 2, 3]),
        ("  nOwAk  ", [1, 2, 3]),
        ("ŻÓŁĆ", [4]),
        ("Żo\u0301łc\u0301", [4]),
        ("Zolc", []),
        ("  WIŚNIEWSKI  ", [5]),
        ("O'CONNOR", [6]),
        ("Nowak   Kowalski", [7]),
        ("Now", []),
    ],
)


def test_search_results_match_expected_ids(database, keys, contacts, query, expected_ids):
    load_all_strategies(database, contacts, keys)

    assert_matching_ids(database, query, keys, expected_ids)


def update_all_strategies(database, record_id, new_surname, keys):
    return {
        "A": update_plaintext_surname(
            database, record_id, new_surname
        ),
        "B": update_encrypted_scan_surname(
            database, record_id, new_surname, keys.encryption_key
        ),
        "C": update_blind_index_surname(
            database, record_id, new_surname, keys
        ),
    }


def test_surname_change_updates_search_results(database, keys, contacts):
    load_all_strategies(database, contacts, keys)

    assert_matching_ids(database, "Nowak", keys, [1, 2, 3])
    assert_matching_ids(database, "Wiśniewski", keys, [5])

    updated = update_all_strategies(
        database, 1, "Wiśniewski", keys
    )

    assert updated == {"A": True, "B": True, "C": True}

    assert_matching_ids(database, "Nowak", keys, [2, 3])
    assert_matching_ids(database, "Wiśniewski", keys, [1, 5])

    results = search_all_strategies(database, "Wiśniewski", keys)

    expected_contact = Contact(
        id=1,
        surname="Wiśniewski",
        email="a@example.com",
    )

    for strategy, found_contacts in results.items():
        updated_contact = next(
            contact for contact in found_contacts if contact.id == 1
        )

        assert updated_contact == expected_contact, strategy


def read_blind_index_row(database, record_id):
    return database.execute(
        """
        SELECT surname_ciphertext, surname_token, email_ciphertext
        FROM contacts_blind_index
        WHERE id = %s
        """,
        (record_id,),
    ).fetchone()



def test_blind_index_update_changes_ciphertext_and_token(database, keys, contacts):
    load_all_strategies(database, contacts, keys)

    before = read_blind_index_row(database, 1)

    assert update_blind_index_surname(
        database, 1, "Wiśniewski", keys
    ) is True

    after = read_blind_index_row(database, 1)

    old_ciphertext, old_token, old_email = before
    new_ciphertext, new_token, new_email = after

    assert new_ciphertext != old_ciphertext
    assert new_token != old_token
    assert new_email == old_email

    assert new_token == surname_token(
        "Wiśniewski", keys.index_key
    )

    restored = decrypt_field(
        new_ciphertext,
        keys.encryption_key,
        record_id=1,
        field_name="surname",
    )

    assert restored == "Wiśniewski"


def test_normalization_equivalent_update_preserves_token(database, keys, contacts):
    load_all_strategies(database, contacts, keys)

    before = read_blind_index_row(database, 1)

    updated = update_all_strategies(
        database, 1, "  NOWAK  ", keys
    )

    assert updated == {"A": True, "B": True, "C": True}

    after = read_blind_index_row(database, 1)

    assert after[0] != before[0]
    assert after[1] == before[1]
    assert after[2] == before[2]

    assert_matching_ids(database, "Nowak", keys, [1, 2, 3])

    for strategy, found_contacts in search_all_strategies(
        database, "Nowak", keys
    ).items():
        contact = next(
            item for item in found_contacts if item.id == 1
        )
        assert contact.surname == "  NOWAK  ", strategy



def test_failed_transaction_restores_previous_data(database, keys, contacts):
    load_all_strategies(database, contacts, keys)

    before = read_blind_index_row(database, 1)

    with pytest.raises(RuntimeError, match="Symulowana awaria"):
        with database.transaction():
            updated = update_all_strategies(
                database, 1, "Wiśniewski", keys
            )

            assert updated == {"A": True, "B": True, "C": True}

            assert_matching_ids(
                database, "Nowak", keys, [2, 3]
            )
            assert_matching_ids(
                database, "Wiśniewski", keys, [1, 5]
            )

            during = read_blind_index_row(database, 1)

            assert during[0] != before[0]
            assert during[1] != before[1]

            raise RuntimeError("Symulowana awaria")

    after = read_blind_index_row(database, 1)

    assert after == before

    assert_matching_ids(database, "Nowak", keys, [1, 2, 3])
    assert_matching_ids(database, "Wiśniewski", keys, [5])




def test_updating_missing_contact_returns_false(database, keys, contacts):
    load_all_strategies(database, contacts, keys)

    updated = update_all_strategies(
        database, 999, "Kowalski", keys
    )

    assert updated == {"A": False, "B": False, "C": False}

    assert_matching_ids(database, "Nowak", keys, [1, 2, 3])
    assert_matching_ids(database, "Kowalski", keys, [])