from cse_benchmark.models import Contact
from cse_benchmark.normalization import normalize_surname


def test_contact_keeps_original_values():
    contact = Contact(
        id=1,
        surname="  ŻÓŁĆ  ",
        email="jan@example.com",
    )

    assert contact.id == 1
    assert contact.surname == "  ŻÓŁĆ  "
    assert contact.email == "jan@example.com"


def test_ignores_case():
    assert normalize_surname("NOWAK") == normalize_surname("nowak")
    assert normalize_surname("ŻÓŁĆ") == "żółć"


def test_removes_extra_whitespace():
    assert normalize_surname("  Nowak \t Kowalski\n") == "nowak kowalski"


def test_unifies_equivalent_unicode_spelling():
    composed = "Żółć"
    decomposed = "Żo\u0301łc\u0301"

    assert normalize_surname(composed) == normalize_surname(decomposed)
    assert normalize_surname(decomposed) == "żółć"


def test_preserves_polish_letters():
    assert normalize_surname("Żółć") != normalize_surname("Zolc")


def test_normalizing_twice_gives_the_same_result():
    once = normalize_surname("  ŻÓŁĆ  ")
    assert normalize_surname(once) == once