"""Administration des comptes, affectations, rôles et délégations.

Règles anti-escalade (document 03) :
- personne ne modifie ses propres affectations, son niveau d'habilitation, ni
  les permissions d'un rôle qu'il détient ;
- on n'attribue une permission « administration.* » que si on la détient
  soi-même sur l'unité concernée ; on n'étend une affectation aux sous-unités
  que si son propre droit couvre tout le sous-arbre ;
- on n'attribue pas un niveau d'habilitation supérieur au sien ;
- un administrateur d'unité ne gère que les comptes dont toutes les
  affectations en cours sont dans son périmètre.

Les contrôles sont faits avant la transaction, pour que les refus restent
dans le journal d'audit.
"""

import datetime

from django.contrib.auth.password_validation import validate_password
from django.contrib.sessions.models import Session
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone
from django.utils.translation import gettext as _

from acces import moteur
from audit.services import journaliser
from noyau.services import lire_parametre

from .catalogue import PREFIXE_ADMINISTRATION
from .models import Affectation, AppareilTotp, CodeSecours, Delegation, Role, SessionUtilisateur, Utilisateur

PERM_UTILISATEURS = "administration.utilisateurs"
PERM_ROLES = "administration.roles"
CHAMPS_PROFIL = ["nom", "prenom", "nom_ar", "courriel", "langue", "niveau_habilitation"]


# --- Périmètre --------------------------------------------------------------


def utilisateurs_geres(acteur):
    """Comptes que l'acteur peut administrer (requête filtrée, utilisable pour les listes)."""
    base = Utilisateur.objects.filter(institution_id=acteur.institution_id, is_superuser=False).exclude(pk=acteur.pk)
    if moteur.portee_institution(acteur, PERM_UTILISATEURS):
        return base
    unites = moteur.unites_autorisees(acteur, PERM_UTILISATEURS)
    hors_perimetre = Affectation.objects.actives().exclude(unite__in=unites).values("utilisateur")
    dans_perimetre = Affectation.objects.actives().filter(unite__in=unites).values("utilisateur")
    return base.filter(pk__in=dans_perimetre).exclude(pk__in=hors_perimetre)


def peut_gerer(acteur, cible):
    return utilisateurs_geres(acteur).filter(pk=cible.pk).exists()


def _exiger_gestion(acteur, cible, requete):
    if not peut_gerer(acteur, cible):
        moteur.refuser(acteur, PERM_UTILISATEURS, requete=requete, objet=cible)


def _verifier_niveau(acteur, niveau):
    if niveau > acteur.niveau_habilitation:
        raise ValidationError(
            {"niveau_habilitation": _("Vous ne pouvez pas attribuer un niveau d'habilitation supérieur au vôtre.")}
        )


# --- Comptes ----------------------------------------------------------------


def creer_utilisateur(acteur, *, mot_de_passe_temporaire, affectation=None, requete=None, **champs):
    """Crée un compte avec un mot de passe temporaire, à changer à la première connexion.

    Un administrateur dont le droit ne couvre pas toute l'institution doit
    fournir une affectation initiale dans son périmètre (dictionnaire
    unite, role, etendue_sous_unites, poste).
    """
    if not moteur.a_permission(acteur, PERM_UTILISATEURS):
        moteur.refuser(acteur, PERM_UTILISATEURS, requete=requete, details={"operation": "utilisateur.creation"})
    if affectation is None and not moteur.portee_institution(acteur, PERM_UTILISATEURS):
        raise ValidationError(_("Indiquez l'unité et le rôle du nouveau compte."))
    if affectation is not None:
        _verifier_affectation(acteur, None, affectation, requete)
    _verifier_niveau(acteur, champs.get("niveau_habilitation", 0))

    utilisateur = Utilisateur(institution=acteur.institution, doit_changer_mot_de_passe=True, **champs)
    utilisateur.full_clean(exclude=["password"])
    validate_password(mot_de_passe_temporaire, utilisateur)
    utilisateur.set_password(mot_de_passe_temporaire)
    with transaction.atomic():
        utilisateur.save()
        journaliser(
            "utilisateur.creation",
            acteur=acteur,
            objet=utilisateur,
            requete=requete,
            details={champ: getattr(utilisateur, champ) for champ in ["identifiant", *CHAMPS_PROFIL]},
        )
        if affectation is not None:
            _enregistrer_affectation(acteur, utilisateur, affectation, requete)
    return utilisateur


def modifier_utilisateur(acteur, cible, *, requete=None, **champs):
    _exiger_gestion(acteur, cible, requete)
    if "niveau_habilitation" in champs:
        _verifier_niveau(acteur, champs["niveau_habilitation"])
    avant = {champ: getattr(cible, champ) for champ in champs}
    for champ, valeur in champs.items():
        if champ not in CHAMPS_PROFIL:
            raise ValueError(f"Champ non modifiable par ce service : {champ}")
        setattr(cible, champ, valeur)
    cible.full_clean(exclude=["password"])
    with transaction.atomic():
        cible.save()
        journaliser(
            "utilisateur.modification",
            acteur=acteur,
            objet=cible,
            requete=requete,
            details={"avant": avant, "apres": champs},
        )
    return cible


def desactiver_utilisateur(acteur, cible, *, motif, requete=None):
    _exiger_gestion(acteur, cible, requete)
    with transaction.atomic():
        cible.is_active = False
        cible.save(update_fields=["is_active"])
        revoquer_sessions(cible, SessionUtilisateur.MotifFin.DESACTIVATION)
        journaliser("utilisateur.desactivation", acteur=acteur, objet=cible, requete=requete, details={"motif": motif})
    return cible


def reactiver_utilisateur(acteur, cible, *, requete=None):
    _exiger_gestion(acteur, cible, requete)
    with transaction.atomic():
        cible.is_active = True
        cible.save(update_fields=["is_active"])
        journaliser("utilisateur.reactivation", acteur=acteur, objet=cible, requete=requete)
    return cible


def reinitialiser_mot_de_passe(acteur, cible, mot_de_passe_temporaire, *, requete=None):
    _exiger_gestion(acteur, cible, requete)
    validate_password(mot_de_passe_temporaire, cible)
    with transaction.atomic():
        cible.set_password(mot_de_passe_temporaire)
        cible.doit_changer_mot_de_passe = True
        cible.mot_de_passe_modifie_le = timezone.now()
        cible.save(update_fields=["password", "doit_changer_mot_de_passe", "mot_de_passe_modifie_le"])
        revoquer_sessions(cible, SessionUtilisateur.MotifFin.REVOCATION)
        journaliser("utilisateur.mot_de_passe.reinitialisation", acteur=acteur, objet=cible, requete=requete)


def deverrouiller(acteur, cible, *, requete=None):
    _exiger_gestion(acteur, cible, requete)
    with transaction.atomic():
        cible.echecs_connexion = 0
        cible.verrouille_jusqu_a = None
        cible.save(update_fields=["echecs_connexion", "verrouille_jusqu_a"])
        journaliser("utilisateur.deverrouillage", acteur=acteur, objet=cible, requete=requete)


def reinitialiser_mfa(acteur, cible, *, requete=None):
    """Supprime l'application d'authentification et les codes de secours (téléphone perdu…)."""
    _exiger_gestion(acteur, cible, requete)
    with transaction.atomic():
        AppareilTotp.objects.filter(utilisateur=cible).delete()
        CodeSecours.objects.filter(utilisateur=cible).delete()
        revoquer_sessions(cible, SessionUtilisateur.MotifFin.REVOCATION)
        journaliser("mfa.reinitialisation", acteur=acteur, objet=cible, requete=requete)


def revoquer_sessions(cible, motif, *, sauf_cle=None, acteur=None, requete=None):
    """Ferme toutes les sessions ouvertes d'un compte (sauf éventuellement la session courante)."""
    ouvertes = SessionUtilisateur.objects.filter(utilisateur=cible, fin__isnull=True)
    if sauf_cle:
        ouvertes = ouvertes.exclude(cle_session=sauf_cle)
    cles = list(ouvertes.values_list("cle_session", flat=True))
    Session.objects.filter(session_key__in=cles).delete()
    ouvertes.update(fin=timezone.now(), motif_fin=motif)
    if acteur is not None:
        journaliser("sessions.revocation", acteur=acteur, objet=cible, requete=requete, details={"sessions": len(cles)})
    return len(cles)


def revoquer_sessions_par_administrateur(acteur, cible, *, requete=None):
    _exiger_gestion(acteur, cible, requete)
    with transaction.atomic():
        return revoquer_sessions(cible, SessionUtilisateur.MotifFin.REVOCATION, acteur=acteur, requete=requete)


# --- Affectations -----------------------------------------------------------


def _verifier_affectation(acteur, cible, donnees, requete):
    unite, role = donnees["unite"], donnees["role"]
    if cible is not None and cible.pk == acteur.pk:
        moteur.refuser(acteur, PERM_UTILISATEURS, requete=requete, details={"operation": "auto_affectation"})
    if unite.institution_id != acteur.institution_id or role.institution_id != acteur.institution_id:
        moteur.refuser(acteur, PERM_UTILISATEURS, requete=requete, details={"operation": "hors_institution"})
    moteur.exiger(acteur, PERM_UTILISATEURS, unite, requete=requete)
    if donnees.get("etendue_sous_unites") and not moteur.couvre_sous_arbre(acteur, PERM_UTILISATEURS, unite):
        moteur.refuser(acteur, PERM_UTILISATEURS, requete=requete, objet=unite, details={"operation": "etendue"})
    for code in role.permissions.filter(code__startswith=PREFIXE_ADMINISTRATION).values_list("code", flat=True):
        couvert = (
            moteur.couvre_sous_arbre(acteur, code, unite)
            if donnees.get("etendue_sous_unites")
            else moteur.a_permission(acteur, code, unite)
        )
        if not couvert:
            moteur.refuser(
                acteur, code, requete=requete, objet=unite, details={"operation": "escalade", "role": role.code}
            )
    if not role.actif:
        raise ValidationError({"role": _("Ce rôle est désactivé.")})
    if not unite.actif:
        raise ValidationError({"unite": _("Cette unité est désactivée.")})
    poste = donnees.get("poste")
    if poste is not None and poste.unite_id != unite.pk:
        raise ValidationError({"poste": _("Ce poste n'appartient pas à l'unité choisie.")})


def _enregistrer_affectation(acteur, cible, donnees, requete):
    affectation = Affectation(utilisateur=cible, attribuee_par=acteur, **donnees)
    affectation.full_clean()
    affectation.save()
    journaliser(
        "affectation.creation",
        acteur=acteur,
        objet=affectation,
        institution=acteur.institution,
        requete=requete,
        details={
            "utilisateur": str(cible.uuid),
            "unite": affectation.unite.code,
            "role": affectation.role.code,
            "etendue_sous_unites": affectation.etendue_sous_unites,
            "date_debut": str(affectation.date_debut),
            "date_fin": str(affectation.date_fin) if affectation.date_fin else None,
        },
    )
    return affectation


def creer_affectation(acteur, cible, *, requete=None, **donnees):
    if cible.institution_id != acteur.institution_id or cible.is_superuser:
        moteur.refuser(acteur, PERM_UTILISATEURS, requete=requete, objet=cible)
    _verifier_affectation(acteur, cible, donnees, requete)
    with transaction.atomic():
        affectation = _enregistrer_affectation(acteur, cible, donnees, requete)
    moteur.oublier(cible)
    return affectation


def cloturer_affectation(acteur, affectation, *, date_fin=None, requete=None):
    moteur.exiger(acteur, PERM_UTILISATEURS, affectation.unite, requete=requete)
    date_fin = date_fin or timezone.localdate()
    if date_fin < affectation.date_debut:
        date_fin = affectation.date_debut
    if affectation.date_fin is not None and affectation.date_fin <= date_fin:
        raise ValidationError(_("Cette affectation est déjà clôturée à cette date."))
    with transaction.atomic():
        affectation.date_fin = date_fin
        affectation.save(update_fields=["date_fin"])
        journaliser(
            "affectation.cloture",
            acteur=acteur,
            objet=affectation,
            institution=acteur.institution,
            requete=requete,
            details={"date_fin": str(date_fin)},
        )
    moteur.oublier(affectation.utilisateur)
    return affectation


# --- Rôles ------------------------------------------------------------------


def enregistrer_role(acteur, role, permissions, *, requete=None):
    """Crée ou modifie un rôle et fixe ses permissions."""
    if not moteur.portee_institution(acteur, PERM_ROLES):
        moteur.refuser(acteur, PERM_ROLES, requete=requete, objet=role if role.pk else None)
    nouvelles = {p.code for p in permissions}
    anciennes = set(role.permissions.values_list("code", flat=True)) if role.pk else set()
    if (
        role.pk
        and nouvelles != anciennes
        and Affectation.objects.actives().filter(utilisateur=acteur, role=role).exists()
    ):
        moteur.refuser(acteur, PERM_ROLES, requete=requete, objet=role, details={"operation": "role_detenu"})
    for code in sorted(nouvelles - anciennes):
        if code.startswith(PREFIXE_ADMINISTRATION) and not moteur.portee_institution(acteur, code):
            moteur.refuser(acteur, code, requete=requete, details={"operation": "escalade_role"})
    creation = role.pk is None
    role.institution = acteur.institution
    role.full_clean()
    with transaction.atomic():
        role.save()
        role.permissions.set(permissions)
        journaliser(
            f"role.{'creation' if creation else 'modification'}",
            acteur=acteur,
            objet=role,
            requete=requete,
            details={
                "code": role.code,
                "actif": role.actif,
                "mfa_requis": role.mfa_requis,
                "permissions_ajoutees": sorted(nouvelles - anciennes),
                "permissions_retirees": sorted(anciennes - nouvelles),
            },
        )
    return role


# --- Délégations ------------------------------------------------------------


def creer_delegation(acteur, *, delegant, delegataire, debut, fin, motif, roles=(), requete=None):
    if acteur.pk != delegant.pk:
        _exiger_gestion(acteur, delegant, requete)
    if delegataire.institution_id != delegant.institution_id or not delegataire.is_active:
        raise ValidationError({"delegataire": _("Le délégataire doit être un compte actif de la même institution.")})
    if delegataire.pk == delegant.pk:
        raise ValidationError({"delegataire": _("On ne peut pas se déléguer à soi-même.")})
    if fin <= debut:
        raise ValidationError({"fin": _("La fin doit être postérieure au début.")})
    maximum = lire_parametre(delegant.institution, "delegation.duree_max_jours")
    if fin - debut > datetime.timedelta(days=maximum):
        raise ValidationError({"fin": _("Une délégation ne peut pas dépasser %(jours)d jours.") % {"jours": maximum}})
    roles_detenus = set(Affectation.objects.actives().filter(utilisateur=delegant).values_list("role_id", flat=True))
    if any(role.pk not in roles_detenus for role in roles):
        raise ValidationError({"roles": _("Seuls les rôles que le délégant exerce peuvent être délégués.")})
    with transaction.atomic():
        delegation = Delegation.objects.create(
            delegant=delegant, delegataire=delegataire, debut=debut, fin=fin, motif=motif, creee_par=acteur
        )
        delegation.roles.set(roles)
        journaliser(
            "delegation.creation",
            acteur=acteur,
            objet=delegation,
            institution=delegant.institution,
            requete=requete,
            details={
                "delegant": delegant.identifiant,
                "delegataire": delegataire.identifiant,
                "debut": debut.isoformat(),
                "fin": fin.isoformat(),
                "roles": sorted(role.code for role in roles),
                "motif": motif,
            },
        )
    return delegation


def revoquer_delegation(acteur, delegation, *, requete=None):
    if acteur.pk not in (delegation.delegant_id, delegation.delegataire_id):
        _exiger_gestion(acteur, delegation.delegant, requete)
    if delegation.revoquee_le is not None:
        raise ValidationError(_("Cette délégation est déjà révoquée."))
    with transaction.atomic():
        delegation.revoquee_le = timezone.now()
        delegation.revoquee_par = acteur
        delegation.save(update_fields=["revoquee_le", "revoquee_par"])
        journaliser(
            "delegation.revocation",
            acteur=acteur,
            objet=delegation,
            institution=delegation.delegant.institution,
            requete=requete,
        )
    return delegation


def roles_visibles(acteur):
    return Role.objects.filter(institution_id=acteur.institution_id).prefetch_related("permissions")
