"""Règles d'accès aux documents (document 03, matrice 3.5).

Un document est vu si toutes ces conditions sont vraies :
- il appartient à l'institution de l'utilisateur ;
- l'utilisateur détient, dans l'unité propriétaire, « document.consulter » ou
  « document.consulter_metadonnees » (fiche seule), ou il a créé le document
  et détient « document.creer » dans cette unité ;
- son niveau d'habilitation est au moins celui du document ;
- au niveau Secret, il figure sur la liste nominative : en attendant les accès
  explicites (lot 7), cette liste se limite à l'auteur du document.

Les cases « P » de la matrice sont les permissions « _propres » : elles ne
s'exercent que sur les documents créés par l'utilisateur. Les listes passent
toutes par `filtrer_visibles` ; aucun écran ne filtre lui-même.
"""

from django.db.models import Q

from identite.catalogue import SUFFIXE_PROPRES
from identite.models import NiveauHabilitation

from . import moteur

CREER = "document.creer"
CONSULTER = "document.consulter"
METADONNEES = "document.consulter_metadonnees"
TELECHARGER = "document.telecharger"
MODIFIER = "document.modifier"
VERSIONNER = "document.versionner"
CONFIDENTIALITE = "document.confidentialite"


def _propre(utilisateur, document):
    return document.cree_par_id == utilisateur.pk


def _permission(utilisateur, code, document):
    """Permission complète dans l'unité propriétaire, ou variante « _propres » sur son propre document."""
    unite = document.unite_proprietaire
    if moteur.a_permission(utilisateur, code, unite):
        return True
    return _propre(utilisateur, document) and moteur.a_permission(utilisateur, code + SUFFIXE_PROPRES, unite)


def _habilite(utilisateur, document):
    if not moteur.niveau_suffisant(utilisateur, document.confidentialite):
        return False
    return document.confidentialite < NiveauHabilitation.SECRET or _propre(utilisateur, document)


def voit(utilisateur, document):
    """La fiche descriptive est visible (métadonnées)."""
    if document.institution_id != getattr(utilisateur, "institution_id", None) or not _habilite(utilisateur, document):
        return False
    unite = document.unite_proprietaire
    return (
        moteur.a_permission(utilisateur, CONSULTER, unite)
        or moteur.a_permission(utilisateur, METADONNEES, unite)
        or (_propre(utilisateur, document) and moteur.a_permission(utilisateur, CREER, unite))
    )


def voit_contenu(utilisateur, document):
    """Les fichiers peuvent être affichés (aperçu), pas seulement la fiche."""
    if not voit(utilisateur, document):
        return False
    unite = document.unite_proprietaire
    return moteur.a_permission(utilisateur, CONSULTER, unite) or (
        _propre(utilisateur, document) and moteur.a_permission(utilisateur, CREER, unite)
    )


def peut_telecharger(utilisateur, document):
    return voit_contenu(utilisateur, document) and _permission(utilisateur, TELECHARGER, document)


def peut_modifier(utilisateur, document):
    return document.modifiable and voit(utilisateur, document) and _permission(utilisateur, MODIFIER, document)


def peut_versionner(utilisateur, document):
    return (
        document.modifiable and voit_contenu(utilisateur, document) and _permission(utilisateur, VERSIONNER, document)
    )


def peut_abaisser_confidentialite(utilisateur, document):
    """Abaisser le niveau exige le droit de confidentialité et la modification sur tout le périmètre (pas « P »)."""
    unite = document.unite_proprietaire
    return moteur.a_permission(utilisateur, CONFIDENTIALITE, unite) and moteur.a_permission(
        utilisateur, MODIFIER, unite
    )


def droits(utilisateur, document):
    return {
        "contenu": voit_contenu(utilisateur, document),
        "telecharger": peut_telecharger(utilisateur, document),
        "modifier": peut_modifier(utilisateur, document),
        "versionner": peut_versionner(utilisateur, document),
        "abaisser_confidentialite": peut_abaisser_confidentialite(utilisateur, document),
    }


def filtrer_visibles(utilisateur, requete):
    """Restreint une requête de documents à ceux dont l'utilisateur voit la fiche."""
    if getattr(utilisateur, "institution_id", None) is None:
        return requete.none()
    consultation = moteur.unites_autorisees(utilisateur, CONSULTER)
    metadonnees = moteur.unites_autorisees(utilisateur, METADONNEES)
    creation = moteur.unites_autorisees(utilisateur, CREER)
    perimetre = (
        Q(unite_proprietaire__in=consultation)
        | Q(unite_proprietaire__in=metadonnees)
        | Q(cree_par=utilisateur, unite_proprietaire__in=creation)
    )
    niveau = getattr(utilisateur, "niveau_habilitation", -1)
    habilitation = Q(confidentialite__lte=niveau) & (
        Q(confidentialite__lt=NiveauHabilitation.SECRET) | Q(cree_par=utilisateur)
    )
    return requete.filter(perimetre, habilitation, institution_id=utilisateur.institution_id)


def unites_de_creation(utilisateur):
    return moteur.unites_autorisees(utilisateur, CREER).filter(actif=True)
