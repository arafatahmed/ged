"""Gestion de l'arbre des unités, des types d'unité et des postes.

Les contrôles de droits sont faits avant d'ouvrir la transaction, pour que
les refus restent dans le journal d'audit.
"""

from django.core.exceptions import ValidationError
from django.db import connection, transaction
from django.db.models import Value
from django.db.models.functions import Concat, Substr
from django.utils.translation import gettext as _

from acces import moteur
from audit.services import journaliser

from .models import Poste, TypeUnite, UniteOrganisationnelle

PERMISSION = "administration.organisation"


def _valeurs(objet, champs):
    return {champ: str(getattr(objet, champ)) if getattr(objet, champ) is not None else None for champ in champs}


def _verifier_droit_sur_parent(acteur, parent, requete):
    # L'unité racine, créée à l'installation, représente l'institution entière : toute autre
    # unité s'y rattache. Une seconde racine échapperait aux droits étendus à toute l'institution.
    if parent is None:
        raise ValidationError(
            {"parent": _("Rattachez l'unité à une unité parente : l'unité racine représente l'institution.")}
        )
    moteur.exiger(acteur, PERMISSION, parent, requete=requete)


def _enregistrer_chemin(unite):
    base = unite.parent.chemin if unite.parent_id else "/"
    unite.chemin = f"{base}{unite.pk}/"
    UniteOrganisationnelle.objects.filter(pk=unite.pk).update(chemin=unite.chemin)


def creer_unite_racine(institution):
    """Unité racine représentant l'institution entière (créée à l'installation, sans acteur)."""
    type_racine = TypeUnite.objects.get(institution=institution, code="institution")
    with transaction.atomic():
        unite = UniteOrganisationnelle.objects.create(
            institution=institution,
            type=type_racine,
            code=institution.sigle.lower()[:30] or "racine",
            sigle=institution.sigle,
            libelle_fr=institution.nom_fr,
            libelle_ar=institution.nom_ar,
        )
        _enregistrer_chemin(unite)
        journaliser("unite.creation", objet=unite, acteur_libelle="systeme", details={"code": unite.code})
    return unite


def creer_unite(acteur, *, requete=None, **champs):
    parent = champs.get("parent")
    _verifier_droit_sur_parent(acteur, parent, requete)
    unite = UniteOrganisationnelle(institution=acteur.institution, **champs)
    unite.full_clean(exclude=["chemin"])
    with transaction.atomic():
        unite.save()
        _enregistrer_chemin(unite)
        journaliser(
            "unite.creation",
            acteur=acteur,
            objet=unite,
            requete=requete,
            details=_valeurs(unite, ["code", "libelle_fr", "parent_id", "type_id"]),
        )
    return unite


def modifier_unite(acteur, unite, *, requete=None, **champs):
    """Modifie une unité ; un changement de parent déplace tout le sous-arbre."""
    moteur.exiger(acteur, PERMISSION, unite, requete=requete)
    ancien_parent_id = unite.parent_id
    nouveau_parent = champs.get("parent", unite.parent)
    if (nouveau_parent.pk if nouveau_parent else None) != ancien_parent_id:
        if ancien_parent_id is None:
            raise ValidationError({"parent": _("L'unité racine ne peut pas être déplacée.")})
        _verifier_droit_sur_parent(acteur, nouveau_parent, requete)
    avant = _valeurs(unite, list(champs))
    for champ, valeur in champs.items():
        setattr(unite, champ, valeur)
    unite.full_clean(exclude=["chemin"])
    with transaction.atomic():
        unite.save()
        if unite.parent_id != ancien_parent_id:
            _deplacer_sous_arbre(unite)
        journaliser(
            "unite.modification",
            acteur=acteur,
            objet=unite,
            requete=requete,
            details={"avant": avant, "apres": _valeurs(unite, list(champs))},
        )
    return unite


def _deplacer_sous_arbre(unite):
    ancien = UniteOrganisationnelle.objects.values_list("chemin", flat=True).get(pk=unite.pk)
    base = unite.parent.chemin if unite.parent_id else "/"
    nouveau = f"{base}{unite.pk}/"
    with connection.cursor() as curseur:
        curseur.execute("LOCK TABLE organisation_uniteorganisationnelle IN SHARE ROW EXCLUSIVE MODE")
    UniteOrganisationnelle.objects.filter(chemin__startswith=ancien).update(
        chemin=Concat(Value(nouveau), Substr("chemin", len(ancien) + 1))
    )
    unite.chemin = nouveau


def desactiver_unite(acteur, unite, *, requete=None):
    moteur.exiger(acteur, PERMISSION, unite, requete=requete)
    erreurs = []
    if unite.enfants.filter(actif=True).exists():
        erreurs.append(_("Désactivez ou déplacez d'abord ses sous-unités actives."))
    if unite.affectations.actives().exists():
        erreurs.append(_("Clôturez ou transférez d'abord les affectations en cours dans cette unité."))
    if unite.postes.filter(actif=True).exists():
        erreurs.append(_("Désactivez d'abord les postes de cette unité."))
    if erreurs:
        raise ValidationError(erreurs)
    with transaction.atomic():
        unite.actif = False
        unite.save(update_fields=["actif", "modifie_le"])
        journaliser("unite.desactivation", acteur=acteur, objet=unite, requete=requete)
    return unite


def enregistrer_type_unite(acteur, type_unite, *, requete=None):
    if not moteur.portee_institution(acteur, PERMISSION):
        moteur.refuser(acteur, PERMISSION, requete=requete, details={"operation": "type_unite"})
    creation = type_unite.pk is None
    type_unite.institution = acteur.institution
    type_unite.full_clean()
    with transaction.atomic():
        type_unite.save()
        journaliser(
            f"typeunite.{'creation' if creation else 'modification'}",
            acteur=acteur,
            objet=type_unite,
            requete=requete,
            details=_valeurs(type_unite, ["code", "libelle_fr", "actif"]),
        )
    return type_unite


def enregistrer_poste(acteur, poste, *, requete=None):
    moteur.exiger(acteur, PERMISSION, poste.unite, requete=requete)
    creation = poste.pk is None
    poste.institution = acteur.institution
    poste.full_clean()
    with transaction.atomic():
        poste.save()
        journaliser(
            f"poste.{'creation' if creation else 'modification'}",
            acteur=acteur,
            objet=poste,
            requete=requete,
            details=_valeurs(poste, ["intitule_fr", "unite_id", "superieur_id", "actif"]),
        )
    return poste


def postes_visibles(acteur):
    return moteur.filtrer_par_unite(acteur, Poste.objects.select_related("unite"), PERMISSION)
