import json
import subprocess
import sys

import pytest

from cse_benchmark.keys import (
    KeyConfigurationError,
    create_keys_file,
    load_keys,
)


def test_creates_and_loads_separate_keys(tmp_path):
    path = tmp_path / "secrets" / "keys.json"

    create_keys_file(path)
    keys = load_keys(path)

    assert len(keys.encryption_key) == 32
    assert len(keys.index_key) == 32
    assert keys.encryption_key != keys.index_key
    assert load_keys(path) == keys


def test_missing_file_raises_error_without_creating_keys(tmp_path):
    path = tmp_path / "keys.json"

    with pytest.raises(KeyConfigurationError, match="Brak pliku"):
        load_keys(path)

    assert not path.exists()


def test_existing_keys_cannot_be_overwritten(tmp_path):
    path = tmp_path / "keys.json"
    create_keys_file(path)
    original = path.read_bytes()

    with pytest.raises(KeyConfigurationError, match="już istnieje"):
        create_keys_file(path)

    assert path.read_bytes() == original


@pytest.mark.parametrize("name", ["encryption_key", "index_key"])
def test_missing_key_is_rejected(tmp_path, name):
    path = tmp_path / "keys.json"
    create_keys_file(path)

    content = json.loads(path.read_text(encoding="utf-8"))
    del content[name]
    path.write_text(json.dumps(content), encoding="utf-8")

    with pytest.raises(KeyConfigurationError, match=name):
        load_keys(path)


@pytest.mark.parametrize("name", ["encryption_key", "index_key"])
@pytest.mark.parametrize("value", ["not-hex", "ab", None])
def test_invalid_key_is_rejected(tmp_path, name, value):
    path = tmp_path / "keys.json"
    create_keys_file(path)

    content = json.loads(path.read_text(encoding="utf-8"))
    content[name] = value
    path.write_text(json.dumps(content), encoding="utf-8")

    with pytest.raises(KeyConfigurationError, match=name):
        load_keys(path)


def test_identical_keys_are_rejected(tmp_path):
    path = tmp_path / "keys.json"
    create_keys_file(path)

    content = json.loads(path.read_text(encoding="utf-8"))
    content["index_key"] = content["encryption_key"]
    path.write_text(json.dumps(content), encoding="utf-8")

    with pytest.raises(KeyConfigurationError, match="muszą być różne"):
        load_keys(path)


def test_invalid_json_is_rejected(tmp_path):
    path = tmp_path / "keys.json"
    path.write_text("{broken", encoding="utf-8")

    with pytest.raises(KeyConfigurationError, match="JSON"):
        load_keys(path)


def test_unknown_version_is_rejected(tmp_path):
    path = tmp_path / "keys.json"
    create_keys_file(path)

    content = json.loads(path.read_text(encoding="utf-8"))
    content["version"] = 2
    path.write_text(json.dumps(content), encoding="utf-8")

    with pytest.raises(KeyConfigurationError, match="wersja"):
        load_keys(path)


def test_keys_work_after_process_restart(tmp_path):
    path = tmp_path / "keys.json"
    create_keys_file(path)

    encrypt_script = """
import hmac
import json
import sys
from pathlib import Path

from cse_benchmark.crypto import encrypt_field
from cse_benchmark.keys import load_keys

keys = load_keys(Path(sys.argv[1]))

payload = encrypt_field(
    "Kowalski",
    keys.encryption_key,
    record_id=15,
    field_name="surname",
)

probe = hmac.digest(
    keys.index_key,
    b"restart-test",
    "sha256",
).hex()

print(json.dumps({
    "payload": payload.hex(),
    "index_probe": probe,
}))
"""

    first = subprocess.run(
        [sys.executable, "-c", encrypt_script, str(path)],
        capture_output=True,
        text=True,
        check=True,
        timeout=30,
    )

    decrypt_script = """
import hmac
import json
import sys
from pathlib import Path

from cse_benchmark.crypto import decrypt_field
from cse_benchmark.keys import load_keys

keys = load_keys(Path(sys.argv[1]))
saved = json.loads(sys.stdin.read())

restored = decrypt_field(
    bytes.fromhex(saved["payload"]),
    keys.encryption_key,
    record_id=15,
    field_name="surname",
)

probe = hmac.digest(
    keys.index_key,
    b"restart-test",
    "sha256",
).hex()

print(json.dumps({
    "restored": restored,
    "index_key_matches": hmac.compare_digest(
        probe,
        saved["index_probe"],
    ),
}))
"""

    second = subprocess.run(
        [sys.executable, "-c", decrypt_script, str(path)],
        input=first.stdout,
        capture_output=True,
        text=True,
        check=True,
        timeout=30,
    )

    result = json.loads(second.stdout)

    assert result["restored"] == "Kowalski"
    assert result["index_key_matches"] is True