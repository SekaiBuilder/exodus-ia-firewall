"""Extended detector coverage — more key/token types + validated structured PII.

Validated kinds (credit_card, iban, es_dni/nie, us_ssn, phone_intl) must fire on a
real value and stay quiet on look-alikes that fail the structural check.
"""
from exodus.classify.detectors import scan


def _kinds(text: str) -> set[str]:
    return {d.kind for d in scan(text)}


def test_more_api_keys_and_tokens():
    assert "google_api_key" in _kinds("key=AIza" + "B" * 35)
    assert "slack_token" in _kinds("xoxb-123456789012-abcdefghijkl")
    assert "stripe_key" in _kinds("stripe sk_live_" + "a" * 24)
    assert "github_pat" in _kinds("pat github_pat_" + "A" * 82)
    assert "openai_project_key" in _kinds("sk-proj-" + "Z" * 24)
    assert "db_uri_credentials" in _kinds("postgres://user:s3cr3t@db.example.com:5432/app")
    jwt = "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c"
    assert "jwt" in _kinds(f"token {jwt}")


def test_credit_card_luhn():
    assert "credit_card" in _kinds("pago con 4111 1111 1111 1111 gracias")   # valid Luhn (Visa test)
    assert "credit_card" not in _kinds("ref 1111 1111 1111 1111")             # fails Luhn


def test_iban_mod97():
    assert "iban" in _kinds("IBAN ES91 2100 0418 4502 0005 1332")            # valid
    assert "iban" not in _kinds("ES00 2100 0418 4502 0005 1332")             # bad check digits


def test_spanish_id_documents():
    assert "es_dni" in _kinds("DNI 12345678Z")        # 12345678 % 23 -> Z
    assert "es_dni" not in _kinds("DNI 12345678A")    # wrong check letter
    assert "es_nie" in _kinds("NIE X1234567L")        # valid NIE


def test_ssn_and_intl_phone():
    assert "us_ssn" in _kinds("SSN 536-90-4399")
    assert "us_ssn" not in _kinds("code 000-12-3456")     # invalid area
    assert "phone_intl" in _kinds("llámame al +34 612 345 678")
