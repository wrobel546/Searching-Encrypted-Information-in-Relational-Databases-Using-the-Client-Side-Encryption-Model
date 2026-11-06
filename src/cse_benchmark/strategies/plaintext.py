from collections.abc import Iterable

import psycopg

from ..models import Contact
from ..normalization import normalize_surname


def replace_plaintext_contacts(connection: psycopg.Connection, contacts: Iterable[Contact],) -> None:
    with connection.transaction():
        connection.execute("DELETE FROM contacts_plaintext")

        rows = (
            (
                contact.id,
                contact.surname,
                normalize_surname(contact.surname),
                contact.email,
            )
            for contact in contacts
        )

        with connection.cursor() as cursor:
            cursor.executemany(
                """
                INSERT INTO contacts_plaintext (
                    id,
                    surname,
                    surname_normalized,
                    email
                )
                VALUES (%s, %s, %s, %s)
                """,
                rows,
            )


def search_plaintext(connection: psycopg.Connection, surname: str,) -> list[Contact]:
    normalized = normalize_surname(surname)

    rows = connection.execute(
        """
        SELECT id, surname, email
        FROM contacts_plaintext
        WHERE surname_normalized = %s
        """,
        (normalized,),
    ).fetchall()

    return [
        Contact(id=row[0], surname=row[1], email=row[2])
        for row in rows
    ]