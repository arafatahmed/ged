"""Services des documents : création, métadonnées, versions, fichiers, relations.

Règles appliquées (document 04, 4.4) :
- les octets sont écrits d'abord sous une clé de quarantaine ; la ligne du
  fichier est créée dans la transaction ; l'analyseur (antivirus, contrôle de
  l'empreinte et du type) publie ensuite le fichier ou le refuse ;
- le type réel est contrôlé dès l'envoi (signature et extension) : un fichier
  déguisé est refusé sans être stocké ;
- une nouvelle version n'écrase jamais la précédente ;
- les contrôles de droits sont faits avant d'ouvrir la transaction, pour que
  les refus restent dans le journal d'audit.
"""

import datetime
import hashlib
import os
import uuid

from django.core.exceptions import ValidationError
from django.core.files.storage import default_storage
from django.db import IntegrityError, transaction
from django.db.models import Max
from django.utils.translation import gettext as _

from acces import documents as acces
from acces import moteur
from audit.models import Resultat
from audit.services import journaliser
from identite.models import NiveauHabilitation
from noyau.services import lire_parametre

from .formats import TAILLE_SIGNATURE, format_par_extension, reconnaitre
from .models import (
    DefinitionMetadonnee,
    Document,
    EtatAnalyse,
    FichierDocument,
    NatureMetadonnee,
    RelationDocument,
    RoleFichier,
    TypeDocument,
    VersionDocument,
)

PREFIXE_QUARANTAINE = "quarantaine/"
MOTS_CLES_MAX = 30
TEXTE_MAX = 1000
CHAMPS_MODIFIABLES = ("titre", "objet", "date_document", "mots_cles", "metadonnees", "confidentialite")


# --- Métadonnées -------------------------------------------------------------------


def _valeur_metadonnee(definition, valeur):
    if definition.nature == NatureMetadonnee.TEXTE:
        if not isinstance(valeur, str) or len(valeur.strip()) > TEXTE_MAX:
            raise ValueError(_("Texte de %(max)d caractères au plus attendu.") % {"max": TEXTE_MAX})
        return valeur.strip()
    if definition.nature == NatureMetadonnee.NOMBRE:
        if isinstance(valeur, bool):
            raise ValueError(_("Nombre attendu."))
        try:
            nombre = float(valeur)
        except (TypeError, ValueError):
            raise ValueError(_("Nombre attendu.")) from None
        return int(nombre) if nombre.is_integer() else nombre
    if definition.nature == NatureMetadonnee.DATE:
        try:
            return datetime.date.fromisoformat(str(valeur)).isoformat()
        except ValueError:
            raise ValueError(_("Date attendue (AAAA-MM-JJ).")) from None
    if valeur not in definition.valeurs_liste:
        raise ValueError(_("Valeur hors de la liste."))
    return valeur


def valider_metadonnees(type_document, valeurs):
    """Contrôle les valeurs contre les définitions actives du type ; renvoie les valeurs normalisées."""
    valeurs = valeurs or {}
    if not isinstance(valeurs, dict):
        raise ValidationError({"metadonnees": [_("Objet attendu.")]})
    definitions = {d.code: d for d in type_document.definitions.filter(actif=True)}
    erreurs = {}
    for code in set(valeurs) - set(definitions):
        erreurs[f"metadonnees.{code}"] = [_("Métadonnée inconnue pour ce type de document.")]
    resultat = {}
    for code, definition in definitions.items():
        valeur = valeurs.get(code)
        if valeur is None or (isinstance(valeur, str) and not valeur.strip()):
            if definition.obligatoire:
                erreurs[f"metadonnees.{code}"] = [_("Ce champ est obligatoire.")]
            continue
        try:
            resultat[code] = _valeur_metadonnee(definition, valeur)
        except ValueError as erreur:
            erreurs[f"metadonnees.{code}"] = [str(erreur)]
    if erreurs:
        raise ValidationError(erreurs)
    return resultat


def normaliser_mots_cles(mots_cles):
    if mots_cles in (None, ""):
        return []
    if not isinstance(mots_cles, list) or not all(isinstance(m, str) for m in mots_cles):
        raise ValidationError({"mots_cles": [_("Liste de mots-clés attendue.")]})
    resultat = []
    for mot in mots_cles:
        mot = mot.strip()[:100]
        if mot and mot.lower() not in {m.lower() for m in resultat}:
            resultat.append(mot)
    if len(resultat) > MOTS_CLES_MAX:
        raise ValidationError({"mots_cles": [_("%(max)d mots-clés au plus.") % {"max": MOTS_CLES_MAX}]})
    return resultat


def _controler_niveau(acteur, niveau):
    if not moteur.niveau_suffisant(acteur, niveau):
        raise ValidationError(
            {"confidentialite": [_("Vous ne pouvez pas attribuer un niveau supérieur à votre habilitation.")]}
        )


# --- Fichiers ----------------------------------------------------------------------


def _refuser_fichier(acteur, message, *, requete, document=None, details=None):
    journaliser(
        "fichier.refus",
        acteur=acteur,
        objet=document,
        requete=requete,
        resultat=Resultat.REFUS,
        details=details or {},
    )
    raise ValidationError({"fichier": [message]})


def controler_fichier(acteur, type_document, fichier, *, requete=None, document=None):
    """Taille, signature et extension ; renvoie le format reconnu. Refus journalisé, rien n'est stocké."""
    nom = os.path.basename(fichier.name or "")[:255]
    taille_max = lire_parametre(acteur.institution, "fichiers.taille_max_mo")
    details = {"nom": nom, "taille": fichier.size}
    if not fichier.size:
        _refuser_fichier(acteur, _("Le fichier est vide."), requete=requete, document=document, details=details)
    if fichier.size > taille_max * 1024 * 1024:
        _refuser_fichier(
            acteur,
            _("Le fichier dépasse la taille maximale de %(max)d Mo.") % {"max": taille_max},
            requete=requete,
            document=document,
            details=details,
        )
    fichier.seek(0)
    entete = fichier.read(TAILLE_SIGNATURE)
    fichier.seek(0)
    reconnu = reconnaitre(entete)
    if reconnu is None or reconnu != format_par_extension(nom):
        _refuser_fichier(
            acteur,
            _("Le contenu du fichier ne correspond pas à un format admis ou ne correspond pas à son extension."),
            requete=requete,
            document=document,
            details={**details, "format_reconnu": reconnu.code if reconnu else None},
        )
    if not type_document.admet(reconnu.code):
        _refuser_fichier(
            acteur,
            _("Le format %(format)s n'est pas admis pour ce type de document.") % {"format": reconnu.libelle},
            requete=requete,
            document=document,
            details={**details, "format_reconnu": reconnu.code},
        )
    return nom, reconnu


def _deposer_en_quarantaine(fichier):
    empreinte = hashlib.sha256()
    fichier.seek(0)
    for morceau in fichier.chunks():
        empreinte.update(morceau)
    fichier.seek(0)
    cle = default_storage.save(f"{PREFIXE_QUARANTAINE}{uuid.uuid4().hex}", fichier)
    return cle, empreinte.hexdigest()


class _Depot:
    """Fichier contrôlé puis déposé en quarantaine ; l'objet est supprimé si la transaction échoue."""

    def __init__(self, acteur, type_document, fichier, *, requete, document=None):
        self.acteur = acteur
        self.nom, self.format = controler_fichier(acteur, type_document, fichier, requete=requete, document=document)
        self.taille = fichier.size
        self.cle, self.sha256 = _deposer_en_quarantaine(fichier)

    def enregistrer(self, version, role):
        return FichierDocument.objects.create(
            institution_id=version.document.institution_id,
            version=version,
            role=role,
            nom_origine=self.nom,
            format=self.format.code,
            type_mime=self.format.type_mime,
            taille=self.taille,
            sha256=self.sha256,
            cle_objet=self.cle,
            depose_par=self.acteur,
        )

    def __enter__(self):
        return self

    def __exit__(self, type_erreur, erreur, trace):
        if type_erreur is not None:
            default_storage.delete(self.cle)
        return False


def _details_fichier(fichier):
    return {
        "fichier": str(fichier.uuid),
        "nom": fichier.nom_origine,
        "sha256": fichier.sha256,
        "taille": fichier.taille,
    }


# --- Documents -------------------------------------------------------------------


def creer_document(
    acteur,
    *,
    type_document,
    unite_proprietaire,
    titre,
    objet="",
    date_document=None,
    confidentialite=None,
    mots_cles=None,
    metadonnees=None,
    fichier=None,
    commentaire="",
    requete=None,
):
    moteur.exiger(acteur, acces.CREER, unite_proprietaire, requete=requete)
    if type_document.institution_id != acteur.institution_id or not type_document.actif:
        raise ValidationError({"type": [_("Type de document inconnu ou inactif.")]})
    if confidentialite is None:
        confidentialite = type_document.confidentialite_defaut
    _controler_niveau(acteur, confidentialite)
    valeurs = valider_metadonnees(type_document, metadonnees)
    mots_cles = normaliser_mots_cles(mots_cles)
    document = Document(
        institution_id=acteur.institution_id,
        type=type_document,
        unite_proprietaire=unite_proprietaire,
        titre=titre,
        objet=objet,
        date_document=date_document,
        confidentialite=confidentialite,
        mots_cles=mots_cles,
        metadonnees=valeurs,
        cree_par=acteur,
    )
    document.full_clean(exclude=["version_courante"])
    if fichier is None:
        with transaction.atomic():
            document.save()
            journaliser("document.creation", acteur=acteur, objet=document, requete=requete, details=_resume(document))
        return document
    with _Depot(acteur, type_document, fichier, requete=requete) as depot, transaction.atomic():
        document.save()
        version = VersionDocument.objects.create(document=document, numero=1, commentaire=commentaire, creee_par=acteur)
        enregistre = depot.enregistrer(version, RoleFichier.PRINCIPAL)
        document.version_courante = version
        document.save(update_fields=["version_courante"])
        journaliser(
            "document.creation",
            acteur=acteur,
            objet=document,
            requete=requete,
            details={**_resume(document), **_details_fichier(enregistre)},
        )
    return document


def _resume(document):
    return {
        "type": document.type.code,
        "unite": document.unite_proprietaire.code,
        "confidentialite": document.confidentialite,
    }


def modifier_document(acteur, document, *, requete=None, **champs):
    """Modifie les champs fournis (parmi CHAMPS_MODIFIABLES).

    Le journal garde les noms des champs modifiés, jamais leur contenu.
    """
    if not acces.peut_modifier(acteur, document):
        moteur.refuser(acteur, acces.MODIFIER, requete=requete, objet=document)
    champs = {nom: valeur for nom, valeur in champs.items() if nom in CHAMPS_MODIFIABLES}
    details = {}
    if "confidentialite" in champs and champs["confidentialite"] != document.confidentialite:
        nouveau = champs["confidentialite"]
        unite = document.unite_proprietaire
        if not moteur.a_permission(acteur, acces.CONFIDENTIALITE, unite) or (
            nouveau < document.confidentialite and not acces.peut_abaisser_confidentialite(acteur, document)
        ):
            moteur.refuser(acteur, acces.CONFIDENTIALITE, requete=requete, objet=document)
        _controler_niveau(acteur, nouveau)
        details["confidentialite"] = {"avant": document.confidentialite, "apres": nouveau}
    if "metadonnees" in champs:
        champs["metadonnees"] = valider_metadonnees(document.type, champs["metadonnees"])
    if "mots_cles" in champs:
        champs["mots_cles"] = normaliser_mots_cles(champs["mots_cles"])
    with transaction.atomic():
        document = Document.objects.select_for_update().get(pk=document.pk)
        modifies = sorted(nom for nom, valeur in champs.items() if getattr(document, nom) != valeur)
        if not modifies:
            return document
        for nom in modifies:
            setattr(document, nom, champs[nom])
        document.modifie_par = acteur
        document.full_clean(exclude=["version_courante"])
        document.save()
        journaliser(
            "document.modification",
            acteur=acteur,
            objet=document,
            requete=requete,
            details={"champs": modifies, **details},
        )
    return document


def ajouter_version(acteur, document, fichier, *, commentaire="", requete=None):
    """Nouvelle version avec son fichier principal ; les versions précédentes restent intactes."""
    premiere = document.version_courante_id is None
    autorise = acces.peut_versionner(acteur, document) or (premiere and acces.peut_modifier(acteur, document))
    if not autorise:
        moteur.refuser(acteur, acces.VERSIONNER, requete=requete, objet=document)
    with _Depot(acteur, document.type, fichier, requete=requete, document=document) as depot, transaction.atomic():
        document = Document.objects.select_for_update().get(pk=document.pk)
        numero = (document.versions.aggregate(dernier=Max("numero"))["dernier"] or 0) + 1
        version = VersionDocument.objects.create(
            document=document, numero=numero, commentaire=commentaire, creee_par=acteur
        )
        enregistre = depot.enregistrer(version, RoleFichier.PRINCIPAL)
        document.version_courante = version
        document.modifie_par = acteur
        document.save(update_fields=["version_courante", "modifie_par", "modifie_le"])
        journaliser(
            "document.version",
            acteur=acteur,
            objet=document,
            requete=requete,
            details={"numero": numero, **_details_fichier(enregistre)},
        )
    return version


def ajouter_piece_jointe(acteur, document, fichier, *, requete=None):
    if not acces.peut_modifier(acteur, document):
        moteur.refuser(acteur, acces.MODIFIER, requete=requete, objet=document)
    if document.version_courante_id is None:
        raise ValidationError({"fichier": [_("Ajoutez d'abord le fichier principal du document.")]})
    with _Depot(acteur, document.type, fichier, requete=requete, document=document) as depot, transaction.atomic():
        enregistre = depot.enregistrer(document.version_courante, RoleFichier.PIECE_JOINTE)
        journaliser(
            "document.piece_jointe",
            acteur=acteur,
            objet=document,
            requete=requete,
            details=_details_fichier(enregistre),
        )
    return enregistre


def journaliser_consultation(acteur, document, *, requete=None):
    """Toute consultation d'un document de niveau Confidentiel ou plus est journalisée (document 04, 4.4)."""
    if document.confidentialite >= NiveauHabilitation.CONFIDENTIEL:
        journaliser("document.consultation", acteur=acteur, objet=document, requete=requete)


def ouvrir_fichier(acteur, fichier, *, telechargement, requete=None):
    """Contrôle les droits et l'état du fichier, journalise, puis renvoie le flux à transmettre."""
    document = fichier.version.document
    if telechargement and not acces.peut_telecharger(acteur, document):
        moteur.refuser(acteur, acces.TELECHARGER, requete=requete, objet=document)
    if not telechargement and not acces.voit_contenu(acteur, document):
        moteur.refuser(acteur, acces.CONSULTER, requete=requete, objet=document)
    if not fichier.lisible:
        raise ValidationError(_("Ce fichier n'est pas disponible : analyse en cours, ou fichier refusé."))
    if telechargement or document.confidentialite >= NiveauHabilitation.CONFIDENTIEL:
        journaliser(
            "fichier.telechargement" if telechargement else "fichier.apercu",
            acteur=acteur,
            objet=document,
            requete=requete,
            details=_details_fichier(fichier),
        )
    return default_storage.open(fichier.cle_objet, "rb")


def doublons_visibles(acteur, document):
    """Documents visibles par l'utilisateur qui contiennent un fichier identique (même empreinte).

    Un doublon dans un document invisible n'est jamais signalé : sa simple
    existence serait une information.
    """
    empreintes = set(
        FichierDocument.objects.filter(version__document=document)
        .exclude(etat_analyse__in=[EtatAnalyse.INFECTE, EtatAnalyse.REFUSE])
        .values_list("sha256", flat=True)
    )
    if not empreintes:
        return Document.objects.none()
    candidats = Document.objects.filter(
        versions__fichiers__sha256__in=empreintes,
        versions__fichiers__etat_analyse__in=[EtatAnalyse.SAIN, EtatAnalyse.EN_ATTENTE],
    ).exclude(pk=document.pk)
    return acces.filtrer_visibles(acteur, candidats).distinct()


# --- Relations -------------------------------------------------------------------


def relier(acteur, source, cible, nature, *, requete=None):
    if not acces.peut_modifier(acteur, source):
        moteur.refuser(acteur, acces.MODIFIER, requete=requete, objet=source)
    if source.pk == cible.pk:
        raise ValidationError({"cible": [_("Un document ne peut pas être relié à lui-même.")]})
    try:
        with transaction.atomic():
            relation = RelationDocument.objects.create(
                institution_id=source.institution_id, source=source, cible=cible, nature=nature, creee_par=acteur
            )
            journaliser(
                "relation.creation",
                acteur=acteur,
                objet=source,
                requete=requete,
                details={"cible": str(cible.uuid), "nature": nature},
            )
    except IntegrityError:
        raise ValidationError({"cible": [_("Cette relation existe déjà.")]}) from None
    return relation


def supprimer_relation(acteur, relation, *, requete=None):
    if not acces.peut_modifier(acteur, relation.source):
        moteur.refuser(acteur, acces.MODIFIER, requete=requete, objet=relation.source)
    with transaction.atomic():
        journaliser(
            "relation.suppression",
            acteur=acteur,
            objet=relation.source,
            requete=requete,
            details={"cible": str(relation.cible.uuid), "nature": relation.nature},
        )
        relation.delete()


# --- Types de documents (administration fonctionnelle) ---------------------------

ADMINISTRATION = "administration.institution"
CHAMPS_DEFINITION = ("libelle_fr", "libelle_ar", "nature", "obligatoire", "valeurs_liste", "ordre", "actif")


def enregistrer_type_document(acteur, type_document, definitions, *, requete=None):
    """Enregistre le type et ses définitions de métadonnées.

    Les définitions sont rapprochées par leur code ; une définition absente de
    la liste est désactivée, jamais supprimée (des documents peuvent porter sa valeur).
    """
    if not moteur.portee_institution(acteur, ADMINISTRATION):
        moteur.refuser(acteur, ADMINISTRATION, requete=requete, details={"operation": "type_document"})
    creation = type_document.pk is None
    type_document.institution = acteur.institution
    type_document.full_clean()
    codes = [d["code"] for d in definitions]
    if len(codes) != len(set(codes)):
        raise ValidationError({"metadonnees": [_("Deux métadonnées portent le même code.")]})
    with transaction.atomic():
        type_document.save()
        existantes = {d.code: d for d in type_document.definitions.all()}
        for donnees in definitions:
            definition = existantes.get(donnees["code"]) or DefinitionMetadonnee(
                type_document=type_document, code=donnees["code"]
            )
            for champ in CHAMPS_DEFINITION:
                setattr(definition, champ, donnees[champ])
            definition.full_clean()
            definition.save()
        type_document.definitions.exclude(code__in=codes).update(actif=False)
        journaliser(
            f"typedocument.{'creation' if creation else 'modification'}",
            acteur=acteur,
            objet=type_document,
            requete=requete,
            details={
                "code": type_document.code,
                "formats": type_document.formats_autorises,
                "metadonnees": codes,
                "actif": type_document.actif,
            },
        )
    return type_document


def types_actifs(institution_id):
    return TypeDocument.objects.filter(institution_id=institution_id, actif=True).prefetch_related("definitions")
