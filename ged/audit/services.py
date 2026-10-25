"""Écriture et vérification du journal d'audit chaîné."""

import datetime
import hashlib
import ipaddress
import json
from dataclasses import dataclass, field
from pathlib import Path

from django.conf import settings
from django.db import connection, transaction
from django.utils import timezone

from .models import JournalAudit, Resultat, ScellementAudit

EMPREINTE_ORIGINE = "0" * 64
# Verrou consultatif PostgreSQL qui sérialise l'écriture de la chaîne.
# Il est libéré à la fin de la transaction appelante.
VERROU_CHAINE = 7461001
MAX_ANOMALIES = 100


def _normaliser(valeur):
    """Rend les détails stables après un aller-retour par JSONB.

    Les nombres décimaux sont convertis en texte : PostgreSQL ne restitue pas
    toujours leur écriture d'origine (1e20 devient 100000000000000000000),
    ce qui changerait l'empreinte.
    """
    if isinstance(valeur, dict):
        return {str(k): _normaliser(v) for k, v in valeur.items()}
    if isinstance(valeur, list | tuple):
        return [_normaliser(v) for v in valeur]
    if isinstance(valeur, bool) or valeur is None or isinstance(valeur, int | str):
        return valeur
    return str(valeur)


def contenu_canonique(evenement):
    donnees = {
        "horodatage": evenement.horodatage.astimezone(datetime.UTC).isoformat(timespec="microseconds"),
        "institution": evenement.institution_id,
        "acteur": evenement.acteur_id,
        "acteur_libelle": evenement.acteur_libelle,
        "agissant_pour": evenement.agissant_pour_id,
        "adresse_ip": evenement.adresse_ip,
        "action": evenement.action,
        "objet_type": evenement.objet_type,
        "objet_id": evenement.objet_id,
        "resultat": evenement.resultat,
        "details": evenement.details,
        "empreinte_precedente": evenement.empreinte_precedente,
    }
    return json.dumps(donnees, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def calculer_empreinte(evenement):
    return hashlib.sha256(contenu_canonique(evenement).encode("utf-8")).hexdigest()


def adresse_ip(requete):
    if requete is None:
        return ""
    adresse = requete.META.get("REMOTE_ADDR", "")
    if settings.GED_PROXY_DE_CONFIANCE:
        transmises = requete.META.get("HTTP_X_FORWARDED_FOR", "")
        if transmises:
            # Seule la dernière adresse a été ajoutée par notre proxy ; les précédentes
            # viennent du client et peuvent être falsifiées.
            adresse = transmises.split(",")[-1].strip()
    try:
        return str(ipaddress.ip_address(adresse))
    except ValueError:
        return ""


def _identifier_objet(objet):
    meta = objet._meta
    identifiant = getattr(objet, "uuid", None) or objet.pk
    return f"{meta.app_label}.{meta.model_name}", str(identifiant)


def journaliser(
    action,
    *,
    acteur=None,
    institution=None,
    objet=None,
    objet_type="",
    objet_id="",
    resultat=Resultat.SUCCES,
    details=None,
    requete=None,
    acteur_libelle="",
    agissant_pour=None,
):
    """Ajoute un événement au journal.

    Appelé dans la transaction de l'opération métier, l'événement est validé
    ou annulé avec elle. Les refus et erreurs doivent être journalisés hors
    de toute transaction annulée.
    """
    if acteur is None and requete is not None and requete.user.is_authenticated:
        acteur = requete.user
    if objet is not None:
        objet_type, objet_id = _identifier_objet(objet)
        if institution is None:
            institution = getattr(objet, "institution", None)
            if institution is None and objet._meta.model_name == "institution":
                institution = objet
    if institution is None and acteur is not None:
        institution = acteur.institution
    if acteur is not None and not acteur_libelle:
        acteur_libelle = acteur.get_username()

    with transaction.atomic():
        with connection.cursor() as curseur:
            curseur.execute("SELECT pg_advisory_xact_lock(%s)", [VERROU_CHAINE])
        precedent = JournalAudit.objects.order_by("-id").values_list("empreinte", flat=True).first()
        evenement = JournalAudit(
            horodatage=timezone.now(),
            institution=institution,
            acteur=acteur,
            acteur_libelle=acteur_libelle[:150],
            agissant_pour=agissant_pour,
            adresse_ip=adresse_ip(requete),
            action=action,
            objet_type=objet_type,
            objet_id=objet_id,
            resultat=resultat,
            details=_normaliser(details or {}),
            empreinte_precedente=precedent or EMPREINTE_ORIGINE,
        )
        evenement.empreinte = calculer_empreinte(evenement)
        evenement.save()
    return evenement


@dataclass
class RapportVerification:
    nombre: int = 0
    anomalies: list = field(default_factory=list)

    @property
    def integre(self):
        return not self.anomalies

    def signaler(self, identifiant, raison):
        if len(self.anomalies) < MAX_ANOMALIES:
            self.anomalies.append((identifiant, raison))


def verifier_chaine(repertoire_scellements=None):
    """Recalcule toute la chaîne et la compare aux scellements.

    Détecte une ligne modifiée (empreinte recalculée différente), supprimée
    ou insérée (rupture du lien avec la précédente), et une chaîne réécrite
    en entier (différence avec les scellements exportés).
    """
    rapport = RapportVerification()
    precedente = EMPREINTE_ORIGINE
    empreintes = {}
    for evenement in JournalAudit.objects.order_by("id").iterator(chunk_size=2000):
        rapport.nombre += 1
        if evenement.empreinte_precedente != precedente:
            rapport.signaler(evenement.id, "lien rompu avec l'événement précédent")
        if calculer_empreinte(evenement) != evenement.empreinte:
            rapport.signaler(evenement.id, "contenu modifié")
        precedente = evenement.empreinte
        empreintes[evenement.id] = (evenement.empreinte, rapport.nombre)

    scellements = {s.date.isoformat(): s for s in ScellementAudit.objects.all()}
    for scellement in scellements.values():
        _comparer_scellement(
            rapport,
            empreintes,
            scellement.dernier_id,
            scellement.empreinte,
            scellement.nombre_evenements,
            f"scellement {scellement.date}",
        )

    if repertoire_scellements:
        for chemin in sorted(Path(repertoire_scellements).glob("scellement-*.json")):
            copie = json.loads(chemin.read_text(encoding="utf-8"))
            _comparer_scellement(
                rapport,
                empreintes,
                copie["dernier_id"],
                copie["empreinte"],
                copie["nombre_evenements"],
                f"copie {chemin.name}",
            )
            en_base = scellements.get(copie["date"])
            if en_base is None or en_base.empreinte != copie["empreinte"]:
                rapport.signaler(copie["dernier_id"], f"copie {chemin.name} absente ou différente en base")
    return rapport


def _comparer_scellement(rapport, empreintes, dernier_id, empreinte, nombre, libelle):
    actuel = empreintes.get(dernier_id)
    if actuel is None:
        rapport.signaler(dernier_id, f"{libelle} : événement scellé introuvable")
    elif actuel != (empreinte, nombre):
        rapport.signaler(dernier_id, f"{libelle} : empreinte ou nombre d'événements différent")


def sceller(date, repertoire=None):
    """Scelle le journal à la fin de la journée `date` (fuseau du serveur).

    Renvoie None s'il n'y a aucun événement à sceller.
    """
    fin = timezone.make_aware(datetime.datetime.combine(date + datetime.timedelta(days=1), datetime.time()))
    dernier = JournalAudit.objects.filter(horodatage__lt=fin).order_by("-id").first()
    if dernier is None:
        return None
    with transaction.atomic():
        scellement = ScellementAudit.objects.create(
            date=date,
            dernier_id=dernier.id,
            empreinte=dernier.empreinte,
            nombre_evenements=JournalAudit.objects.filter(id__lte=dernier.id).count(),
        )
        journaliser(
            "audit.scellement",
            objet=scellement,
            details={"date": date.isoformat(), "dernier_id": dernier.id},
            acteur_libelle="systeme",
        )
    repertoire = Path(repertoire or settings.GED_AUDIT_SCELLEMENT_DIR)
    repertoire.mkdir(parents=True, exist_ok=True)
    copie = {
        "date": date.isoformat(),
        "dernier_id": scellement.dernier_id,
        "empreinte": scellement.empreinte,
        "nombre_evenements": scellement.nombre_evenements,
    }
    (repertoire / f"scellement-{date.isoformat()}.json").write_text(
        json.dumps(copie, indent=2) + "\n", encoding="utf-8"
    )
    return scellement
