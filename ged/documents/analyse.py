"""Analyse des fichiers en quarantaine (processus « analyseur »).

Pour chaque fichier en attente, une seule lecture du stockage alimente à la
fois l'antivirus, le recalcul de l'empreinte SHA-256 et la reconnaissance du
type. Le fichier est publié (déplacé hors de la quarantaine) seulement si les
trois contrôles réussissent ; un fichier infecté est effacé du stockage, sa
ligne et l'événement d'audit sont conservés.

La file d'attente est la table elle-même (`SELECT … FOR UPDATE SKIP LOCKED`) :
plusieurs analyseurs peuvent tourner sans traiter deux fois le même fichier,
sans courtier de messages à exploiter.
"""

import hashlib
import logging

from django.core.files import File
from django.core.files.storage import default_storage
from django.db import transaction
from django.utils import timezone

from audit.models import Resultat
from audit.services import journaliser

from . import antivirus
from .formats import TAILLE_SIGNATURE, reconnaitre
from .models import EtatAnalyse, FichierDocument
from .services import PREFIXE_QUARANTAINE

journal = logging.getLogger(__name__)

TAILLE_MORCEAU = 1024 * 1024
ACTEUR = "analyseur"


def _cle_publiee(fichier):
    return f"documents/{fichier.institution.uuid}/{fichier.uuid}"


def _conclure(fichier, etat, action, *, motif="", resultat=Resultat.SUCCES, details=None, effacer=False):
    quarantaine = fichier.cle_objet
    fichier.etat_analyse = etat
    fichier.motif = motif[:255]
    fichier.analyse_le = timezone.now()
    fichier.save(update_fields=["etat_analyse", "motif", "analyse_le", "cle_objet"])
    journaliser(
        action,
        objet=fichier,
        institution=fichier.institution,
        acteur_libelle=ACTEUR,
        resultat=resultat,
        details={"document": str(fichier.version.document.uuid), "sha256": fichier.sha256, **(details or {})},
    )
    if effacer:
        transaction.on_commit(lambda: default_storage.delete(quarantaine))


def _analyser(fichier, client):
    """Analyse un fichier verrouillé. Renvoie False si l'antivirus n'a pas pu rendre de verdict."""
    empreinte = hashlib.sha256()
    entete = bytearray()

    def morceaux():
        with default_storage.open(fichier.cle_objet, "rb") as flux:
            while morceau := flux.read(TAILLE_MORCEAU):
                empreinte.update(morceau)
                if len(entete) < TAILLE_SIGNATURE:
                    entete.extend(morceau[: TAILLE_SIGNATURE - len(entete)])
                yield morceau

    try:
        verdict = client.analyser(morceaux())
    except antivirus.AntivirusIndisponible as erreur:
        fichier.tentatives += 1
        fichier.save(update_fields=["tentatives"])
        journal.warning(
            "Antivirus indisponible (fichier %s, tentative %d) : %s", fichier.uuid, fichier.tentatives, erreur
        )
        return False
    except FileNotFoundError:
        _conclure(
            fichier, EtatAnalyse.REFUSE, "fichier.refus", motif="objet absent du stockage", resultat=Resultat.ERREUR
        )
        return True

    details = {"antivirus": client.nom}
    if verdict.trop_volumineux:
        _conclure(
            fichier,
            EtatAnalyse.REFUSE,
            "fichier.refus",
            motif="trop volumineux pour l'antivirus",
            resultat=Resultat.REFUS,
            details=details,
            effacer=True,
        )
    elif not verdict.sain:
        _conclure(
            fichier,
            EtatAnalyse.INFECTE,
            "fichier.infecte",
            motif=verdict.signature,
            resultat=Resultat.REFUS,
            details={**details, "signature": verdict.signature},
            effacer=True,
        )
    elif empreinte.hexdigest() != fichier.sha256:
        _conclure(
            fichier,
            EtatAnalyse.REFUSE,
            "fichier.refus",
            motif="empreinte différente de celle calculée à l'envoi",
            resultat=Resultat.ERREUR,
            details={**details, "sha256_relu": empreinte.hexdigest()},
            effacer=True,
        )
    elif (reconnu := reconnaitre(bytes(entete))) is None or reconnu.code != fichier.format:
        _conclure(
            fichier,
            EtatAnalyse.REFUSE,
            "fichier.refus",
            motif="type réel différent du type contrôlé à l'envoi",
            resultat=Resultat.REFUS,
            details=details,
            effacer=True,
        )
    else:
        quarantaine = fichier.cle_objet
        with default_storage.open(quarantaine, "rb") as flux:
            fichier.cle_objet = default_storage.save(_cle_publiee(fichier), File(flux))
        try:
            _conclure(fichier, EtatAnalyse.SAIN, "fichier.analyse", details=details)
        except Exception:
            default_storage.delete(fichier.cle_objet)
            raise
        transaction.on_commit(lambda: default_storage.delete(quarantaine))
    return True


def analyser_suivant(client=None):
    """Analyse le plus ancien fichier en attente non verrouillé.

    Renvoie le fichier traité, None s'il n'y en a pas, ou lève AntivirusIndisponible.
    """
    client = client or antivirus.client()
    with transaction.atomic():
        fichier = (
            FichierDocument.objects.select_for_update(skip_locked=True, of=("self",))
            .select_related("institution", "version__document")
            .filter(etat_analyse=EtatAnalyse.EN_ATTENTE)
            .order_by("pk")
            .first()
        )
        if fichier is None:
            return None
        verdict_rendu = _analyser(fichier, client)
    # Hors de la transaction : le compteur de tentatives doit rester enregistré.
    if not verdict_rendu:
        raise antivirus.AntivirusIndisponible(str(fichier.uuid))
    return fichier


def analyser_en_attente(client=None, limite=None):
    """Analyse les fichiers en attente ; renvoie le nombre de fichiers traités."""
    client = client or antivirus.client()
    traites = 0
    while limite is None or traites < limite:
        if analyser_suivant(client) is None:
            break
        traites += 1
    return traites


def nettoyer_quarantaine(age_heures=24):
    """Efface les objets de quarantaine sans fichier enregistré (envoi interrompu) plus vieux que le délai."""
    try:
        _dossiers, noms = default_storage.listdir(PREFIXE_QUARANTAINE.rstrip("/"))
    except FileNotFoundError:
        return 0
    connus = set(
        FichierDocument.objects.filter(cle_objet__startswith=PREFIXE_QUARANTAINE).values_list("cle_objet", flat=True)
    )
    limite = timezone.now() - timezone.timedelta(hours=age_heures)
    effaces = 0
    for nom in noms:
        cle = f"{PREFIXE_QUARANTAINE}{nom}"
        if cle not in connus and default_storage.get_modified_time(cle) < limite:
            default_storage.delete(cle)
            effaces += 1
    return effaces
