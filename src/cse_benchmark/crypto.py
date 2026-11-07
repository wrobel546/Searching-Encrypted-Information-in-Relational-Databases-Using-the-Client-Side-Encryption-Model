import json
import secrets
import hmac

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from .normalization import normalize_surname

KEY_SIZE = 32
NONCE_SIZE = 12
TAG_SIZE = 16
FORMAT_VERSION = b"\x01"


def generate_key() -> bytes:
    return AESGCM.generate_key(bit_length=256)


def _create_cipher(key: bytes) -> AESGCM:
    if len(key) != KEY_SIZE:
        raise ValueError("Klucz musi mieć dokładnie 32 bajty.")

    return AESGCM(key)

def _build_aad(record_id: int, field_name: str):
    if (not isinstance(record_id, int) or isinstance(record_id, bool) or record_id <= 0):
        raise ValueError("ID rekordu musi być dodatnią liczbą całkowitą.")
    if (field_name not in ('surname','email')):
            raise ValueError("Nazwa pola musi być 'surname' lub 'email'.")

    context = ["cse-benchmark", FORMAT_VERSION[0], record_id, field_name,]

    return json.dumps(context, ensure_ascii=False, separators=(",", ":"),).encode("utf-8")

def encrypt_field(value: str, key: bytes, *, record_id: int, field_name: str, ) -> bytes:
    cipher = _create_cipher(key)
    aad = _build_aad(record_id, field_name)
    nonce = secrets.token_bytes(NONCE_SIZE)
     
    plaintext = value.encode("utf-8")
    ciphertext = cipher.encrypt(nonce, plaintext, aad)

    return FORMAT_VERSION + nonce + ciphertext

def decrypt_field(payload: bytes, key: bytes, *, record_id: int, field_name: str):
    minimum_size = len(FORMAT_VERSION) + NONCE_SIZE + TAG_SIZE

    if len(payload) < minimum_size:
        raise ValueError("Zaszyfrowane pole jest zbyt krótkie.")

    if payload[:1] != FORMAT_VERSION:
        raise ValueError("Nieobsługiwana wersja zaszyfrowanego pola.")

    cipher = _create_cipher(key)
    aad = _build_aad(record_id, field_name)
    nonce = payload[1 : 1 + NONCE_SIZE]
    ciphertext = payload[1 + NONCE_SIZE :]

    plaintext = cipher.decrypt(nonce, ciphertext, aad)

    return plaintext.decode("utf-8")    


def surname_token(value: str, index_key: bytes) -> bytes:
    if len(index_key) != KEY_SIZE:
        raise ValueError("Klucz indeksowania musi mieć dokładnie 32 bajty.")

    normalized = normalize_surname(value)

    context = ["cse-benchmark", "blind-index", 1, "surname", normalized,]

    message = json.dumps(context, ensure_ascii=False, separators=(",", ":"),).encode("utf-8")
    return hmac.digest(index_key, message, "sha256")