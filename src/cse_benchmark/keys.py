import json
import secrets
from dataclasses import dataclass, field
from pathlib import Path

from .crypto import KEY_SIZE, generate_key

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_KEYS_PATH = PROJECT_ROOT / "secrets" / "keys.json"

class KeyConfigurationError(RuntimeError):
    pass

@dataclass(frozen=True)
class KeySet:
    encryption_key: bytes = field(repr=False)
    index_key: bytes = field(repr=False)


def create_keys_file(path: Path = DEFAULT_KEYS_PATH) -> None:
    encryption_key = generate_key()
    index_key = secrets.token_bytes(32)

    while index_key == encryption_key:
        index_key = secrets.token_bytes(32)

    content = {
        "version": 1,
        "encryption_key": encryption_key.hex(),
        "index_key": index_key.hex(),
    }

    try:
        path.parent.mkdir(parents=True, exist_ok=True)

        with path.open("x", encoding="utf-8") as file:
            json.dump(content, file, indent=2)
            file.write("\n")

    except FileExistsError:
        raise KeyConfigurationError(f"Plik kluczy już istnieje: {path}. Nie został nadpisany.") from None
    except OSError:
        raise KeyConfigurationError(f"Nie można zapisać pliku kluczy: {path}.") from None

def _decode_key(content: dict, name: str) -> bytes:
    value = content.get(name)

    if not isinstance(value, str):
        raise KeyConfigurationError(f"Brak klucza '{name}' lub niepoprawny typ wartości.")

    try:
        key = bytes.fromhex(value)
    except ValueError:
        raise KeyConfigurationError(f"Klucz '{name}' nie ma poprawnego zapisu hex.") from None

    if len(key) != KEY_SIZE:
        raise KeyConfigurationError(f"Klucz '{name}' musi mieć dokładnie {KEY_SIZE} bajty.")

    return key

def load_keys(path: Path = DEFAULT_KEYS_PATH) -> KeySet:
    try:
        content = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise KeyConfigurationError(
            f"Brak pliku kluczy: {path}. "
            "Dla nowego zbioru utwórz klucze jednorazowo. "
            "Dla istniejących szyfrogramów przywróć właściwy plik kluczy."
        ) from None
    except (json.JSONDecodeError, UnicodeError):
        raise KeyConfigurationError( f"Plik kluczy nie jest poprawnym dokumentem JSON UTF-8: {path}.") from None
    except OSError:
        raise KeyConfigurationError(f"Nie można odczytać pliku kluczy: {path}.") from None

    if not isinstance(content, dict):
        raise KeyConfigurationError("Plik kluczy musi zawierać obiekt JSON.")

    if type(content.get("version")) is not int or content["version"] != 1:
        raise KeyConfigurationError("Nieobsługiwana wersja pliku kluczy.")

    encryption_key = _decode_key(content, "encryption_key")
    index_key = _decode_key(content, "index_key")

    if encryption_key == index_key:
        raise KeyConfigurationError( "Klucz szyfrowania i klucz indeksowania muszą być różne.")

    return KeySet(encryption_key=encryption_key, index_key=index_key,)