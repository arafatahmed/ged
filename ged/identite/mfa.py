"""Double authentification : enrôlement, vérification, codes de secours."""

import hashlib
import secrets

import segno
from django.db import transaction
from django.utils import timezone

from audit.services import journaliser

from . import totp
from .models import Affectation, AppareilTotp, CodeSecours

NOMBRE_CODES_SECOURS = 10


def mfa_requise(utilisateur):
    """Vraie pour le superadministrateur technique et pour qui exerce (en propre) un rôle qui l'impose."""
    if utilisateur.is_superuser:
        return True
    return Affectation.objects.actives().filter(utilisateur=utilisateur, role__mfa_requis=True).exists()


def demarrer_enrolement(utilisateur):
    """Renvoie l'appareil en cours d'enrôlement (créé avec un nouveau secret s'il n'existe pas).

    Le secret reste le même tant que l'enrôlement n'est pas confirmé, pour que le
    QR code affiché ne change pas d'un affichage à l'autre.
    """
    appareil, _cree = AppareilTotp.objects.get_or_create(
        utilisateur=utilisateur, defaults={"secret": totp.nouveau_secret()}
    )
    return appareil


def qr_code_svg(appareil, emetteur):
    uri = totp.uri_configuration(appareil.secret, compte=appareil.utilisateur.identifiant, emetteur=emetteur)
    return segno.make(uri, error="m").svg_data_uri(scale=5, dark="#000", light="#fff", border=2)


def _empreinte(code):
    return hashlib.sha256(code.strip().upper().replace("-", "").encode("utf-8")).hexdigest()


def generer_codes_secours(utilisateur):
    """Remplace les codes de secours et renvoie les nouveaux codes en clair (affichés une seule fois)."""
    codes = []
    CodeSecours.objects.filter(utilisateur=utilisateur).delete()
    for _i in range(NOMBRE_CODES_SECOURS):
        brut = secrets.token_hex(5).upper()
        codes.append(f"{brut[:5]}-{brut[5:]}")
        CodeSecours.objects.create(utilisateur=utilisateur, empreinte=_empreinte(brut))
    return codes


def confirmer_enrolement(utilisateur, code, *, requete=None):
    """Valide le premier code saisi ; renvoie les codes de secours, ou None si le code est faux."""
    with transaction.atomic():
        appareil = AppareilTotp.objects.select_for_update().get(utilisateur=utilisateur)
        pas = totp.verifier(appareil.secret, code, dernier_pas=appareil.dernier_pas)
        if pas is None:
            return None
        appareil.confirme = True
        appareil.confirme_le = timezone.now()
        appareil.dernier_pas = pas
        appareil.save(update_fields=["confirme", "confirme_le", "dernier_pas"])
        codes = generer_codes_secours(utilisateur)
        journaliser("mfa.activation", acteur=utilisateur, objet=utilisateur, requete=requete)
    return codes


def verifier_code(utilisateur, code):
    """Vérifie un code TOTP ou un code de secours (consommé). Vrai si valide."""
    with transaction.atomic():
        appareil = AppareilTotp.objects.select_for_update().filter(utilisateur=utilisateur, confirme=True).first()
        if appareil is None:
            return False
        pas = totp.verifier(appareil.secret, code, dernier_pas=appareil.dernier_pas)
        if pas is not None:
            appareil.dernier_pas = pas
            appareil.save(update_fields=["dernier_pas"])
            return True
        secours = (
            CodeSecours.objects.select_for_update()
            .filter(utilisateur=utilisateur, empreinte=_empreinte(code or ""), utilise_le__isnull=True)
            .first()
        )
        if secours is not None:
            secours.utilise_le = timezone.now()
            secours.save(update_fields=["utilise_le"])
            journaliser("mfa.code_secours_utilise", acteur=utilisateur, objet=utilisateur)
            return True
    return False


def desactiver(utilisateur, *, requete=None):
    with transaction.atomic():
        AppareilTotp.objects.filter(utilisateur=utilisateur).delete()
        CodeSecours.objects.filter(utilisateur=utilisateur).delete()
        journaliser("mfa.desactivation", acteur=utilisateur, objet=utilisateur, requete=requete)
