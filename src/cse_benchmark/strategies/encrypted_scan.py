from collections.abc import Iterable
from uuid import uuid4

import psycopg

from ..crypto import KEY_SIZE, decrypt_field, encrypt_field
from ..models import Contact
from ..normalization import normalize_surname

def replace_encrypted_contacts(connection: psycopg.Connection, contacts: Iterable[Contact], encryption_key: bytes, ) -> None:
    if len(encryption_key) != KEY_SIZE:
        raise ValueError("Klucz musi mieć dokładnie 32 bajty.")

    with connection.transaction():
        connection.execute("DELETE FROM contacts_encrypted_scan")

        rows= ((    contact.id,
                    encrypt_field(contact.surname,
                        encryption_key,
                        record_id=contact.id,
                        field_name="surname"),
                    encrypt_field(
                        contact.email,
                        encryption_key,
                        record_id=contact.id,
                        field_name="email",
                    ),
                )
                for contact in contacts)
    
        with connection.cursor() as cursor:
            cursor.executemany(
                """
                INSERT INTO contacts_encrypted_scan (
                    id,
                    surname_ciphertext,
                    email_ciphertext
                )
                VALUES (%s, %s, %s)
                """,
                rows,
            )

def search_encrypted_scan(connection: psycopg.Connection, surname: str, encryption_key: bytes, *, batch_size: int = 100, ) -> list[Contact]:
    if type(batch_size) is not int or batch_size <= 0:
        raise ValueError("Rozmiar partii musi być dodatnią liczbą całkowitą.")

    if len(encryption_key) != KEY_SIZE:
        raise ValueError("Klucz musi mieć dokładnie 32 bajty.")

    normalized_query = normalize_surname(surname)
    results = []
    
    cursor_name = f"encrypted_scan_{uuid4().hex}"

    with connection.transaction():
        with connection.cursor(name=cursor_name) as cursor:
            cursor.execute(
                """
                SELECT id, surname_ciphertext, email_ciphertext
                FROM contacts_encrypted_scan
                """
            )

            while True:
                rows = cursor.fetchmany(batch_size)

                if not rows:
                    break
                for record_id, surname_payload, email_payload in rows:
                        original_surname = decrypt_field(
                            surname_payload,
                            encryption_key,
                            record_id=record_id,
                            field_name="surname",
                        )

                        original_email = decrypt_field(
                            email_payload,
                            encryption_key,
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

def update_encrypted_scan_surname(connection: psycopg.Connection, record_id: int, new_surname: str, encryption_key: bytes, ) -> bool:
    surname_payload = encrypt_field(new_surname,encryption_key, record_id=record_id,field_name="surname",)

    with connection.transaction():
        cursor = connection.execute(
            """
            UPDATE contacts_encrypted_scan
            SET surname_ciphertext = %s
            WHERE id = %s
            """,
            (surname_payload, record_id),
        )

        updated = cursor.rowcount == 1

    return updated
