import unicodedata


def normalize_surname(value: str) -> str:
    words = value.split()
    joined = " ".join(words)
    folded = joined.casefold()
    return unicodedata.normalize("NFC", folded)