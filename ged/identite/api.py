"""API de session (connexion en deux étapes, double authentification) et de « Mon compte ».

Authentification par session Django et cookie HttpOnly : le frontend Angular est
servi par le même domaine et envoie le jeton CSRF dans l'en-tête X-CSRFToken.
La connexion elle-même est protégée contre le CSRF (DRF ne le fait que pour les
utilisateurs déjà connectés).
"""

import time

from django.conf import settings
from django.contrib.auth import authenticate, login, logout, update_session_auth_hash
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.db import transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.utils.translation import gettext as _
from django.utils.translation import gettext_noop
from django.views.decorators.csrf import ensure_csrf_cookie
from rest_framework import exceptions, status
from rest_framework.authentication import CSRFCheck
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from acces import moteur
from audit.models import Resultat
from audit.services import journaliser
from noyau.api_outils import documenter, erreurs_validation, reponse_erreurs

from . import mfa, services
from .backends import enregistrer_echec
from .models import Delegation, Role, SessionUtilisateur, Utilisateur

CLE_PARTIELLE = "connexion_partielle"
DUREE_ETAPE_MFA = 5 * 60
# Même message pour un mot de passe faux et un compte verrouillé : on ne révèle rien.
MESSAGE_ECHEC = gettext_noop("Identifiant ou mot de passe incorrect, ou compte temporairement verrouillé.")


# --- Représentations -------------------------------------------------------------


def institution_publique(institution):
    if institution is None:
        return None
    return {
        "nom_fr": institution.nom_fr,
        "nom_ar": institution.nom_ar,
        "sigle": institution.sigle,
        "couleur_primaire": institution.couleur_primaire,
        "couleur_secondaire": institution.couleur_secondaire,
        "langue_defaut": institution.langue_defaut,
        "format_date": institution.format_date,
        "logo": bool(institution.logo),
    }


def droits_menu(utilisateur):
    return {
        "organisation": moteur.a_permission(utilisateur, "administration.organisation"),
        "types_unite": moteur.portee_institution(utilisateur, "administration.organisation"),
        "utilisateurs": moteur.a_permission(utilisateur, "administration.utilisateurs"),
        "roles": moteur.portee_institution(utilisateur, "administration.roles"),
        "connexions": moteur.portee_institution(utilisateur, "audit.consulter"),
    }


def utilisateur_public(utilisateur):
    return {
        "uuid": str(utilisateur.uuid),
        "identifiant": utilisateur.identifiant,
        "nom": utilisateur.nom,
        "prenom": utilisateur.prenom,
        "nom_complet": utilisateur.get_full_name(),
        "nom_ar": utilisateur.nom_ar,
        "courriel": utilisateur.courriel,
        "langue": utilisateur.langue,
        "niveau_habilitation": utilisateur.niveau_habilitation,
        "niveau_habilitation_libelle": utilisateur.get_niveau_habilitation_display(),
        "superadministrateur": utilisateur.is_superuser,
        "mfa_active": utilisateur.mfa_active,
    }


def etat_session(request):
    utilisateur = request.user
    institution = getattr(request, "institution", None)
    if not utilisateur.is_authenticated:
        partiel, _etat = utilisateur_partiel(request)
        etape = None
        if partiel is not None:
            etape = "mfa" if partiel.mfa_active else "enrolement"
        return {
            "authentifie": False,
            "etape": etape,
            "utilisateur": None,
            "institution": institution_publique(institution),
        }
    return {
        "authentifie": True,
        "etape": None,
        "utilisateur": utilisateur_public(utilisateur),
        "institution": institution_publique(institution),
        "exigences": {
            "changer_mot_de_passe": utilisateur.doit_changer_mot_de_passe,
            "activer_mfa": not utilisateur.mfa_active and mfa.mfa_requise(utilisateur),
        },
        "droits": droits_menu(utilisateur),
    }


# --- Étape intermédiaire de connexion --------------------------------------------


def utilisateur_partiel(request):
    """Utilisateur dont le mot de passe est vérifié mais pas encore la double authentification."""
    etat = request.session.get(CLE_PARTIELLE)
    if not etat or time.time() - etat["depuis"] > DUREE_ETAPE_MFA:
        request.session.pop(CLE_PARTIELLE, None)
        return None, None
    utilisateur = Utilisateur.objects.filter(pk=etat["id"], is_active=True).first()
    if utilisateur is None or utilisateur.est_verrouille():
        request.session.pop(CLE_PARTIELLE, None)
        return None, None
    utilisateur.backend = etat["backend"]
    return utilisateur, etat


def exiger_csrf(request):
    """Vérifie le jeton CSRF même pour un visiteur non connecté (DRF ne le fait que pour les sessions ouvertes)."""
    verification = CSRFCheck(lambda requete: None)
    verification.process_request(request)
    raison = verification.process_view(request, None, (), {})
    if raison:
        raise exceptions.PermissionDenied(f"CSRF : {raison}")


def _terminer_connexion(request, utilisateur, etat):
    request.session.pop(CLE_PARTIELLE, None)
    login(request, utilisateur, backend=etat["backend"])


# --- Session ------------------------------------------------------------------------


@documenter
@api_view(["GET"])
@permission_classes([AllowAny])
@ensure_csrf_cookie
def session(request):
    """État de la session ; dépose aussi le cookie CSRF dont le frontend a besoin."""
    return Response(etat_session(request))


@documenter
@api_view(["POST"])
@permission_classes([AllowAny])
def connexion(request):
    exiger_csrf(request)
    identifiant = str(request.data.get("identifiant", "")).strip()
    mot_de_passe = str(request.data.get("mot_de_passe", ""))
    if not identifiant or not mot_de_passe:
        return reponse_erreurs({"__all__": [_("Saisissez votre identifiant et votre mot de passe.")]})
    utilisateur = authenticate(request, username=identifiant, password=mot_de_passe)
    if utilisateur is None:
        return reponse_erreurs({"__all__": [_(MESSAGE_ECHEC)]})
    if utilisateur.mfa_active or mfa.mfa_requise(utilisateur):
        request.session.cycle_key()
        request.session[CLE_PARTIELLE] = {"id": utilisateur.pk, "backend": utilisateur.backend, "depuis": time.time()}
        journaliser(
            "connexion.mot_de_passe_valide", objet=utilisateur, acteur_libelle=utilisateur.identifiant, requete=request
        )
        return Response(etat_session(request))
    login(request, utilisateur)
    return Response(etat_session(request))


@documenter
@api_view(["POST"])
@permission_classes([AllowAny])
def verification(request):
    exiger_csrf(request)
    utilisateur, etat = utilisateur_partiel(request)
    if utilisateur is None:
        return Response({"detail": _("Étape expirée : reconnectez-vous."), "code": "etape_expiree"}, status=401)
    if mfa.verifier_code(utilisateur, str(request.data.get("code", ""))):
        _terminer_connexion(request, utilisateur, etat)
        return Response(etat_session(request))
    journaliser(
        "connexion.mfa_echec",
        objet=utilisateur,
        acteur_libelle=utilisateur.identifiant,
        requete=request,
        resultat=Resultat.REFUS,
    )
    enregistrer_echec(utilisateur, request, motif="mfa")
    utilisateur.refresh_from_db()
    if utilisateur.est_verrouille():
        request.session.pop(CLE_PARTIELLE, None)
        return Response({"detail": _(MESSAGE_ECHEC), "code": "etape_expiree"}, status=401)
    return reponse_erreurs({"code": [_("Code incorrect ou déjà utilisé.")]})


def _sujet_enrolement(request):
    if request.user.is_authenticated:
        return request.user, None
    return utilisateur_partiel(request)


@documenter
@api_view(["GET", "POST"])
@permission_classes([AllowAny])
def enrolement(request):
    """Activation de la double authentification, pendant la connexion ou depuis « Mon compte »."""
    if request.method == "POST":
        exiger_csrf(request)
    utilisateur, etat = _sujet_enrolement(request)
    if utilisateur is None:
        return Response({"detail": _("Étape expirée : reconnectez-vous."), "code": "etape_expiree"}, status=401)
    if utilisateur.mfa_active:
        return reponse_erreurs({"__all__": [_("La double authentification est déjà activée.")]})
    appareil = mfa.demarrer_enrolement(utilisateur)
    if request.method == "GET":
        emetteur = getattr(request, "institution", None)
        return Response(
            {
                "qr_code": mfa.qr_code_svg(appareil, emetteur.sigle if emetteur else "GED"),
                "secret": " ".join(appareil.secret[i : i + 4] for i in range(0, len(appareil.secret), 4)),
                "obligatoire": mfa.mfa_requise(utilisateur),
            }
        )
    codes = mfa.confirmer_enrolement(utilisateur, str(request.data.get("code", "")), requete=request)
    if codes is None:
        return reponse_erreurs({"code": [_("Code incorrect. Vérifiez l'heure de votre téléphone et réessayez.")]})
    if etat is not None:
        _terminer_connexion(request, utilisateur, etat)
    return Response({"codes_secours": codes, "session": etat_session(request)})


@documenter
@api_view(["POST"])
@permission_classes([AllowAny])
def deconnexion(request):
    exiger_csrf(request)
    if request.user.is_authenticated:
        logout(request)
    else:
        request.session.flush()
    return Response(etat_session(request))


# --- Mon compte ----------------------------------------------------------------------


def _delegation(delegation):
    return {
        "uuid": str(delegation.uuid),
        "delegant": delegation.delegant.get_full_name(),
        "delegataire": delegation.delegataire.get_full_name(),
        "debut": delegation.debut,
        "fin": delegation.fin,
        "motif": delegation.motif,
        "roles": [role.libelle_fr for role in delegation.roles.all()],
        "revoquee": delegation.revoquee_le is not None,
    }


def _affectation(affectation):
    return {
        "uuid": str(affectation.uuid),
        "role": affectation.role.libelle_fr,
        "role_ar": affectation.role.libelle_ar,
        "unite": affectation.unite.libelle_fr,
        "unite_ar": affectation.unite.libelle_ar,
        "unite_sigle": affectation.unite.sigle or affectation.unite.code,
        "etendue_sous_unites": affectation.etendue_sous_unites,
        "date_debut": affectation.date_debut,
        "date_fin": affectation.date_fin,
    }


@documenter
@api_view(["GET", "PATCH"])
def compte(request):
    utilisateur = request.user
    if request.method == "PATCH":
        langue = request.data.get("langue", "")
        if langue not in {"", *dict(settings.LANGUAGES)}:
            return reponse_erreurs({"langue": [_("Langue inconnue.")]})
        with transaction.atomic():
            utilisateur.langue = langue
            utilisateur.save(update_fields=["langue"])
            journaliser(
                "compte.preferences", acteur=utilisateur, objet=utilisateur, requete=request, details={"langue": langue}
            )
    maintenant = timezone.now()
    return Response(
        {
            "utilisateur": utilisateur_public(utilisateur),
            "affectations": [
                _affectation(a) for a in utilisateur.affectations.actives().select_related("unite", "role")
            ],
            "sessions": [
                {
                    "debut": s.debut,
                    "adresse_ip": s.adresse_ip,
                    "agent": s.agent,
                    "courante": s.cle_session == request.session.session_key,
                }
                for s in SessionUtilisateur.objects.filter(utilisateur=utilisateur, fin__isnull=True)
            ],
            "delegations_donnees": [
                _delegation(d)
                for d in Delegation.objects.filter(delegant=utilisateur, revoquee_le__isnull=True, fin__gte=maintenant)
                .select_related("delegant", "delegataire")
                .prefetch_related("roles")
            ],
            "delegations_recues": [
                _delegation(d)
                for d in Delegation.objects.en_cours()
                .filter(delegataire=utilisateur)
                .select_related("delegant", "delegataire")
                .prefetch_related("roles")
            ],
            "mfa": {
                "active": utilisateur.mfa_active,
                "obligatoire": mfa.mfa_requise(utilisateur),
                "codes_restants": utilisateur.codes_secours.filter(utilise_le__isnull=True).count(),
            },
        }
    )


@documenter
@api_view(["POST"])
def changer_mot_de_passe(request):
    utilisateur = request.user
    ancien = str(request.data.get("ancien", ""))
    nouveau = str(request.data.get("nouveau", ""))
    if not utilisateur.check_password(ancien):
        return reponse_erreurs({"ancien": [_("Mot de passe actuel incorrect.")]})
    if nouveau != str(request.data.get("confirmation", "")):
        return reponse_erreurs({"confirmation": [_("Les deux mots de passe ne correspondent pas.")]})
    try:
        validate_password(nouveau, utilisateur)
    except ValidationError as erreur:
        return reponse_erreurs({"nouveau": list(erreur.messages)})
    with transaction.atomic():
        utilisateur.set_password(nouveau)
        utilisateur.doit_changer_mot_de_passe = False
        utilisateur.mot_de_passe_modifie_le = timezone.now()
        utilisateur.save(update_fields=["password", "doit_changer_mot_de_passe", "mot_de_passe_modifie_le"])
        update_session_auth_hash(request, utilisateur)
        services.revoquer_sessions(
            utilisateur, SessionUtilisateur.MotifFin.REVOCATION, sauf_cle=request.session.session_key
        )
        journaliser("compte.mot_de_passe.modification", acteur=utilisateur, objet=utilisateur, requete=request)
    return Response(etat_session(request))


@documenter
@api_view(["POST"])
def desactiver_mfa(request):
    if mfa.mfa_requise(request.user):
        return reponse_erreurs(
            {"__all__": [_("Votre rôle impose la double authentification : elle ne peut pas être désactivée.")]}
        )
    mfa.desactiver(request.user, requete=request)
    return Response(status=status.HTTP_204_NO_CONTENT)


@documenter
@api_view(["POST"])
def regenerer_codes(request):
    if not request.user.mfa_active:
        return reponse_erreurs({"__all__": [_("La double authentification n'est pas activée.")]})
    with transaction.atomic():
        codes = mfa.generer_codes_secours(request.user)
        journaliser("mfa.codes_secours_regeneres", acteur=request.user, objet=request.user, requete=request)
    return Response({"codes_secours": codes})


@documenter
@api_view(["POST"])
def fermer_autres_sessions(request):
    nombre = services.revoquer_sessions(
        request.user,
        SessionUtilisateur.MotifFin.REVOCATION,
        sauf_cle=request.session.session_key,
        acteur=request.user,
        requete=request,
    )
    return Response({"sessions_fermees": nombre})


def options_delegation(delegant):
    return {
        "delegataires": [
            {"uuid": str(u.uuid), "libelle": f"{u.get_full_name()} ({u.identifiant})"}
            for u in Utilisateur.objects.filter(institution_id=delegant.institution_id, is_active=True)
            .exclude(pk=delegant.pk)
            .order_by("nom", "prenom")
        ],
        "roles": [
            {"uuid": str(r.uuid), "libelle": r.libelle_fr, "libelle_ar": r.libelle_ar}
            for r in Role.objects.filter(pk__in=delegant.affectations.actives().values("role"))
        ],
    }


def creer_delegation_depuis(request, acteur, delegant):
    """Lecture et validation communes aux délégations créées par soi-même ou par un administrateur."""
    from django.utils.dateparse import parse_datetime

    donnees = request.data
    erreurs = {}
    delegataire = None
    if _uuid_valide(donnees.get("delegataire")):
        delegataire = Utilisateur.objects.filter(
            uuid=donnees["delegataire"], institution_id=delegant.institution_id, is_active=True
        ).first()
    if delegataire is None:
        erreurs["delegataire"] = [_("Choisissez un délégataire.")]
    debut = parse_datetime(str(donnees.get("debut", ""))) if donnees.get("debut") else None
    fin = parse_datetime(str(donnees.get("fin", ""))) if donnees.get("fin") else None
    if debut is None:
        erreurs["debut"] = [_("Date et heure attendues.")]
    if fin is None:
        erreurs["fin"] = [_("Date et heure attendues.")]
    motif = str(donnees.get("motif", "")).strip()
    if not motif:
        erreurs["motif"] = [_("Indiquez le motif.")]
    roles_uuid = [r for r in donnees.get("roles", []) if _uuid_valide(r)]
    roles = list(Role.objects.filter(uuid__in=roles_uuid, institution_id=delegant.institution_id))
    if erreurs:
        return reponse_erreurs(erreurs)
    if timezone.is_naive(debut):
        debut = timezone.make_aware(debut)
    if timezone.is_naive(fin):
        fin = timezone.make_aware(fin)
    try:
        delegation = services.creer_delegation(
            acteur,
            delegant=delegant,
            delegataire=delegataire,
            debut=debut,
            fin=fin,
            motif=motif,
            roles=roles,
            requete=request,
        )
    except ValidationError as erreur:
        return reponse_erreurs(erreurs_validation(erreur))
    return Response(_delegation(delegation), status=status.HTTP_201_CREATED)


def _uuid_valide(valeur):
    import uuid

    try:
        uuid.UUID(str(valeur))
    except ValueError:
        return False
    return True


@documenter
@api_view(["GET", "POST"])
def mes_delegations(request):
    if request.method == "GET":
        return Response(options_delegation(request.user))
    return creer_delegation_depuis(request, request.user, request.user)


@documenter
@api_view(["POST"])
def revoquer_ma_delegation(request, uuid):
    delegation = get_object_or_404(
        Delegation.objects.filter(delegant=request.user) | Delegation.objects.filter(delegataire=request.user),
        uuid=uuid,
    )
    services.revoquer_delegation(request.user, delegation, requete=request)
    return Response(status=status.HTTP_204_NO_CONTENT)
