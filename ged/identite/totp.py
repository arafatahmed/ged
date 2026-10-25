"""Mots de passe à usage unique basés sur le temps (TOTP, RFC 6238), compatibles avec
les applications d'authentification courantes (SHA-1, 6 chiffres, pas de 30 s)."""

import base64
import hashlib
import hmac
import secrets
import struct
import time
from urllib.parse import quote, urlencode

PAS = 30
CHIFFRES = 6
# Tolérance d'un pas avant ou après, pour les horloges légèrement décalées.
FENETRE = 1


def nouveau_secret():
    return base64.b32encode(secrets.token_bytes(20)).decode("ascii")


def code_hotp(secret, compteur, chiffres=CHIFFRES, algorithme=hashlib.sha1):
    cle = base64.b32decode(secret, casefold=True)
    empreinte = hmac.new(cle, struct.pack(">Q", compteur), algorithme).digest()
    decalage = empreinte[-1] & 0x0F
    valeur = struct.unpack(">I", empreinte[decalage : decalage + 4])[0] & 0x7FFFFFFF
    return str(valeur % 10**chiffres).zfill(chiffres)


def pas_courant(instant=None):
    return int((time.time() if instant is None else instant) // PAS)


def verifier(secret, code, *, dernier_pas=0, instant=None):
    """Renvoie le pas de temps du code s'il est valide et pas encore utilisé, sinon None.

    L'appelant enregistre ce pas comme `dernier_pas` : un code ne peut servir qu'une fois.
    """
    code = (code or "").strip().replace(" ", "")
    if len(code) != CHIFFRES or not code.isdigit():
        return None
    courant = pas_courant(instant)
    for pas in range(courant - FENETRE, courant + FENETRE + 1):
        if pas > dernier_pas and hmac.compare_digest(code_hotp(secret, pas), code):
            return pas
    return None


def uri_configuration(secret, *, compte, emetteur):
    libelle = quote(f"{emetteur}:{compte}")
    parametres = urlencode({"secret": secret, "issuer": emetteur, "digits": CHIFFRES, "period": PAS})
    return f"otpauth://totp/{libelle}?{parametres}"
