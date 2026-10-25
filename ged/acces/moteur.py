"""Moteur de décision d'accès.

Une permission n'est jamais accordée « en général » : elle s'exerce dans une
unité, par une affectation active (rôle × unité × période), éventuellement
étendue aux sous-unités, ou par une délégation en cours. Le refus est la
valeur par défaut.

Règles :
- aucun droit sans compte actif rattaché à une institution ; le
  superadministrateur technique (hors institution) n'obtient ici aucun droit ;
- jamais d'accès à une unité d'une autre institution ;
- une délégation transmet les rôles du délégant, sauf les permissions
  « administration.* » ;
- le niveau d'habilitation borne l'accès aux objets confidentiels.

Toutes les listes filtrées par droits doivent passer par `unites_autorisees`
ou `filtrer_par_unite` ; aucun écran ne filtre lui-même.
"""

from dataclasses import dataclass

from django.core.exceptions import PermissionDenied
from django.db.models import Q

from audit.models import Resultat
from audit.services import journaliser
from identite.catalogue import PREFIXE_ADMINISTRATION
from identite.models import Affectation, Delegation
from organisation.models import UniteOrganisationnelle


@dataclass(frozen=True)
class Droit:
    unite_id: int
    chemin: str
    etendue: bool
    permissions: frozenset
    delegant_id: int | None = None

    def couvre(self, unite):
        if self.unite_id == unite.pk:
            return True
        return self.etendue and unite.chemin.startswith(self.chemin)

    def couvre_sous_arbre(self, unite):
        """Vrai si le droit s'exerce sur l'unité et sur toutes ses sous-unités."""
        return self.etendue and unite.chemin.startswith(self.chemin)


def _droits_des_affectations(affectations, *, delegant_id=None, roles_delegues=None):
    droits = []
    for affectation in affectations:
        if roles_delegues and affectation.role_id not in roles_delegues:
            continue
        permissions = {p.code for p in affectation.role.permissions.all() if p.actif}
        if delegant_id is not None:
            permissions = {p for p in permissions if not p.startswith(PREFIXE_ADMINISTRATION)}
        if permissions:
            droits.append(
                Droit(
                    unite_id=affectation.unite_id,
                    chemin=affectation.unite.chemin,
                    etendue=affectation.etendue_sous_unites,
                    permissions=frozenset(permissions),
                    delegant_id=delegant_id,
                )
            )
    return droits


def _affectations_actives(utilisateur):
    return (
        Affectation.objects.actives()
        .filter(utilisateur=utilisateur, unite__institution_id=utilisateur.institution_id)
        .select_related("unite", "role")
        .prefetch_related("role__permissions")
    )


def droits(utilisateur):
    """Droits effectifs de l'utilisateur, calculés une fois par instance (donc par requête)."""
    cache = getattr(utilisateur, "_droits_acces", None)
    if cache is not None:
        return cache
    if not getattr(utilisateur, "is_authenticated", False) or not utilisateur.is_active:
        return []
    if utilisateur.institution_id is None:
        return []

    resultat = _droits_des_affectations(_affectations_actives(utilisateur))
    delegations = (
        Delegation.objects.en_cours()
        .filter(
            delegataire=utilisateur,
            delegant__is_active=True,
            delegant__institution_id=utilisateur.institution_id,
        )
        .select_related("delegant")
        .prefetch_related("roles")
    )
    for delegation in delegations:
        roles = {role.pk for role in delegation.roles.all()}
        resultat += _droits_des_affectations(
            _affectations_actives(delegation.delegant),
            delegant_id=delegation.delegant_id,
            roles_delegues=roles,
        )
    utilisateur._droits_acces = resultat
    return resultat


def oublier(utilisateur):
    """Vide le cache des droits (après une modification d'affectation dans la même requête)."""
    if hasattr(utilisateur, "_droits_acces"):
        del utilisateur._droits_acces


def a_permission(utilisateur, code, unite=None):
    """Vrai si l'utilisateur détient la permission dans l'unité (ou dans au moins une unité si `unite` est None)."""
    if unite is not None and unite.institution_id != getattr(utilisateur, "institution_id", None):
        return False
    for droit in droits(utilisateur):
        if code in droit.permissions and (unite is None or droit.couvre(unite)):
            return True
    return False


def couvre_sous_arbre(utilisateur, code, unite):
    if unite.institution_id != getattr(utilisateur, "institution_id", None):
        return False
    return any(code in d.permissions and d.couvre_sous_arbre(unite) for d in droits(utilisateur))


def unites_autorisees(utilisateur, code):
    """Unités où l'utilisateur détient la permission."""
    condition = Q()
    for droit in droits(utilisateur):
        if code in droit.permissions:
            condition |= Q(pk=droit.unite_id)
            if droit.etendue:
                condition |= Q(chemin__startswith=droit.chemin)
    if not condition:
        return UniteOrganisationnelle.objects.none()
    return UniteOrganisationnelle.objects.filter(condition, institution_id=utilisateur.institution_id)


def filtrer_par_unite(utilisateur, queryset, code, champ="unite"):
    """Restreint une requête aux objets rattachés à une unité où l'utilisateur détient la permission."""
    return queryset.filter(**{f"{champ}__in": unites_autorisees(utilisateur, code)})


def portee_institution(utilisateur, code):
    """Vrai si la permission couvre toute l'institution (toutes les unités racines, sous-unités comprises)."""
    racines = list(
        UniteOrganisationnelle.objects.filter(
            institution_id=getattr(utilisateur, "institution_id", None), parent__isnull=True, actif=True
        )
    )
    return bool(racines) and all(couvre_sous_arbre(utilisateur, code, racine) for racine in racines)


def niveau_suffisant(utilisateur, niveau):
    return getattr(utilisateur, "niveau_habilitation", -1) >= niveau


def refuser(utilisateur, code, *, requete=None, objet=None, details=None):
    """Journalise un refus puis lève PermissionDenied.

    À appeler hors de toute transaction qui sera annulée, sinon le refus
    disparaîtrait du journal avec elle.
    """
    journaliser(
        "acces.refus",
        acteur=utilisateur if getattr(utilisateur, "is_authenticated", False) else None,
        objet=objet,
        requete=requete,
        resultat=Resultat.REFUS,
        details={"permission": code, **(details or {})},
    )
    raise PermissionDenied


def exiger(utilisateur, code, unite=None, *, requete=None):
    if not a_permission(utilisateur, code, unite):
        refuser(utilisateur, code, requete=requete, objet=unite)
