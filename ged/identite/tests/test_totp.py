import base64

import pytest

from identite import totp

# Vecteurs de la RFC 6238 (annexe B), algorithme SHA-1, 8 chiffres.
SECRET_RFC = base64.b32encode(b"12345678901234567890").decode()


@pytest.mark.parametrize(
    "instant, attendu",
    [
        (59, "94287082"),
        (1111111109, "07081804"),
        (1111111111, "14050471"),
        (1234567890, "89005924"),
        (2000000000, "69279037"),
        (20000000000, "65353130"),
    ],
)
def test_vecteurs_rfc6238(instant, attendu):
    assert totp.code_hotp(SECRET_RFC, instant // 30, chiffres=8) == attendu


def test_verification_et_fenetre():
    secret = totp.nouveau_secret()
    instant = 1_800_000_000
    code = totp.code_hotp(secret, totp.pas_courant(instant))
    assert totp.verifier(secret, code, instant=instant) == totp.pas_courant(instant)
    precedent = totp.code_hotp(secret, totp.pas_courant(instant) - 1)
    assert totp.verifier(secret, precedent, instant=instant) is not None
    trop_ancien = totp.code_hotp(secret, totp.pas_courant(instant) - 3)
    assert totp.verifier(secret, trop_ancien, instant=instant) is None


def test_code_rejoue_refuse():
    secret = totp.nouveau_secret()
    instant = 1_800_000_000
    code = totp.code_hotp(secret, totp.pas_courant(instant))
    pas = totp.verifier(secret, code, instant=instant)
    assert totp.verifier(secret, code, dernier_pas=pas, instant=instant) is None


@pytest.mark.parametrize("code", ["", "12345", "abcdef", "1234567", None])
def test_formats_invalides(code):
    assert totp.verifier(totp.nouveau_secret(), code) is None


def test_uri_de_configuration():
    uri = totp.uri_configuration("ABC", compte="awa.diallo", emetteur="DEMO")
    assert uri.startswith("otpauth://totp/DEMO%3Aawa.diallo?")
    assert "secret=ABC" in uri and "issuer=DEMO" in uri
