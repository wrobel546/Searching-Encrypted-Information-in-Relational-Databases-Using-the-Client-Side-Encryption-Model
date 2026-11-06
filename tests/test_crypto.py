import pytest
from cryptography.exceptions import InvalidTag

from cse_benchmark.crypto import (
    decrypt_field,
    encrypt_field,
    generate_key,
)


@pytest.fixture
def key():
    return generate_key()


@pytest.mark.parametrize(
    ("value", "field_name"),
    [
        ("Kowalski", "surname"),
        ("  ŻÓŁĆ  ", "surname"),
        ("Żo\u0301łc\u0301", "surname"),
        ("", "surname"),
        ("jan@example.com", "email"),
    ],
)
def test_encrypt_decrypt_preserves_original_text(key, value, field_name):
    payload = encrypt_field(
        value,
        key,
        record_id=15,
        field_name=field_name,
    )

    restored = decrypt_field(
        payload,
        key,
        record_id=15,
        field_name=field_name,
    )

    assert restored == value


def test_generate_key_returns_256_bit_key():
    assert len(generate_key()) == 32


def test_repeated_encryption_uses_different_nonces(key):
    first = encrypt_field(
        "Nowak", key, record_id=1, field_name="surname"
    )
    second = encrypt_field(
        "Nowak", key, record_id=1, field_name="surname"
    )

    assert first[1:13] != second[1:13]
    assert first != second

    for payload in (first, second):
        assert decrypt_field(
            payload, key, record_id=1, field_name="surname"
        ) == "Nowak"


@pytest.mark.parametrize(
    "position",
    [1, 13, -1],
    ids=["nonce", "ciphertext", "tag"],
)
def test_detects_modified_payload(key, position):
    payload = encrypt_field(
        "Kowalski", key, record_id=15, field_name="surname"
    )

    modified = bytearray(payload)
    modified[position] ^= 1

    with pytest.raises(InvalidTag):
        decrypt_field(
            bytes(modified),
            key,
            record_id=15,
            field_name="surname",
        )


@pytest.mark.parametrize(
    ("record_id", "field_name"),
    [
        (16, "surname"),
        (15, "email"),
    ],
    ids=["different_record", "different_field"],
)
def test_rejects_wrong_context(key, record_id, field_name):
    payload = encrypt_field(
        "Kowalski", key, record_id=15, field_name="surname"
    )

    with pytest.raises(InvalidTag):
        decrypt_field(
            payload,
            key,
            record_id=record_id,
            field_name=field_name,
        )


def test_rejects_wrong_key(key):
    payload = encrypt_field(
        "Kowalski", key, record_id=15, field_name="surname"
    )

    wrong_key = bytearray(key)
    wrong_key[0] ^= 1

    with pytest.raises(InvalidTag):
        decrypt_field(
            payload,
            bytes(wrong_key),
            record_id=15,
            field_name="surname",
        )


def test_rejects_truncated_ciphertext(key):
    payload = encrypt_field(
        "Kowalski", key, record_id=15, field_name="surname"
    )

    with pytest.raises(InvalidTag):
        decrypt_field(
            payload[:-1],
            key,
            record_id=15,
            field_name="surname",
        )


def test_rejects_too_short_payload(key):
    with pytest.raises(ValueError, match="zbyt krótkie"):
        decrypt_field(
            b"\x01",
            key,
            record_id=15,
            field_name="surname",
        )


def test_rejects_unknown_format_version(key):
    payload = encrypt_field(
        "Kowalski", key, record_id=15, field_name="surname"
    )

    modified = b"\x02" + payload[1:]

    with pytest.raises(ValueError, match="wersja|wersji"):
        decrypt_field(
            modified,
            key,
            record_id=15,
            field_name="surname",
        )


def test_rejects_wrong_key_length():
    with pytest.raises(ValueError, match="32 bajty"):
        encrypt_field(
            "Nowak",
            b"too-short",
            record_id=1,
            field_name="surname",
        )