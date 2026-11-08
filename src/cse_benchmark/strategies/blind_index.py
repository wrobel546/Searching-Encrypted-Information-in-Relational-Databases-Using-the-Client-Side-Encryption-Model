from collections.abc import Iterable

import psycopg

from ..crypto import (
    KEY_SIZE,
    decrypt_field,
    encrypt_field,
    surname_token,
)
from ..keys import KeySet
from ..models import Contact
from ..normalization import normalize_surname

def _validation_keys(keys: KeySet) -> None:
    if ((len(keys.encryption_key)) != KEY_SIZE or len(keys.index_key) != KEY_SIZE):
        raise ValueError("Oba klucze muszą mieć dokładnie 32 bajty.")

    if keys.encryption_key == keys.index_key:
        raise ValueError("Klucze szyfrowania i indeksowania muszą być różne.")


def replace_blind_index_contacts(connection: psycopg.Connection, contacts: Iterable[Contact], keys: KeySet):
    _validation_keys(keys)

    with connection.transaction():
        connection.execute("DELETE FROM contacts_blind_index")

        rows = (
            (
                contact.id,
                encrypt_field(
                    contact.surname,
                    keys.encryption_key,
                    record_id=contact.id,
                    field_name="surname",
                ),
                encrypt_field(
                    contact.email,
                    keys.encryption_key,
                    record_id=contact.id,
                    field_name="email",
                ),
                surname_token(contact.surname, keys.index_key),
            )
            for contact in contacts
        )

        with connection.cursor() as cursor:
            cursor.executemany(
                """
                INSERT INTO contacts_blind_index (
                    id,
                    surname_ciphertext,
                    email_ciphertext,
                    surname_token
                )
                VALUES (%s, %s, %s, %s)
                """,
                rows,
            )


def search_blind_index(connection: psycopg.Connection, surname: str, keys: KeySet,) -> list[Contact]:
    normalized_query = normalize_surname(surname)
    query_token = surname_token(surname, keys.index_key)

    rows = connection.execute(
        """
        SELECT id, surname_ciphertext, email_ciphertext
        FROM contacts_blind_index
        WHERE surname_token = %s
        """,
        (query_token,),
    ).fetchall()

    results = []

    for record_id, surname_payload, email_payload in rows:
        original_surname = decrypt_field(
            surname_payload,
            keys.encryption_key,
            record_id=record_id,
            field_name="surname",
        )

        original_email = decrypt_field(
            email_payload,
            keys.encryption_key,
            record_id=record_id,
            field_name="email",
        )

        if normalize_surname(original_surname) == normalized_query:
            results.append(
                Contact(
                    id=record_id,
                    surname=original_surname,
                    email=original_email,
                )
            )

    return results


def update_blind_index_surname(connection: psycopg.Connection, record_id: int, new_surname: str, keys: KeySet,) -> bool:
    _validation_keys(keys)

    surname_payload = encrypt_field(new_surname, keys.encryption_key, record_id=record_id, field_name="surname",)
    token = surname_token(new_surname, keys.index_key)

    with connection.transaction():
        cursor = connection.execute(
            """
            UPDATE contacts_blind_index
            SET surname_ciphertext = %s,
                surname_token = %s
            WHERE id = %s
            """,
            (surname_payload, token, record_id),
        )

        updated = cursor.rowcount == 1

    return updated