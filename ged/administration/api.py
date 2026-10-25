"""API d'administration fonctionnelle, utilisée par le frontend Angular.

Les points d'API ne décident d'aucun droit eux-mêmes : ils filtrent par le
moteur d'accès et agissent par les services, qui appliquent les règles
anti-escalade et journalisent. Un objet hors du périmètre répond 404.
"""

import csv
import secrets

from django.conf import settings
from django.db.models import Count, Q
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.utils.translation import gettext as _
from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.response import Response

from acces import moteur
from audit.models import JournalAudit
from audit.services import journaliser
from identite import services as identite
from identite.api import _delegation, creer_delegation_depuis, options_delegation
from identite.models import Affectation, Delegation, NiveauHabilitation, Permission, Role, SessionUtilisateur
from noyau.api_outils import documenter, erreurs_formulaire, paginer, permission_requise
from organisation import services as organisation
from organisation.models import Poste, TypeUnite

from .forms import (
    FormulaireAffectation,
    FormulaireCreationUtilisateur,
    FormulairePoste,
    FormulaireProfilUtilisateur,
    FormulaireRole,
    FormulaireTypeUnite,
    FormulaireUnite,
)

ORGANISATION = "administration.organisation"
UTILISATEURS = "administration.utilisateurs"
ROLES = "administration.roles"
AUDIT = "audit.consulter"


def _donnees(formulaire, noms):
    return {nom: formulaire.cleaned_data[nom] for nom in noms}


# --- Représentations -------------------------------------------------------------


def _unite(unite):
    return {
        "uuid": str(unite.uuid),
        "code": unite.code,
        "sigle": unite.sigle,
        "libelle_fr": unite.libelle_fr,
        "libelle_ar": unite.libelle_ar,
        "type": unite.type_id,
        "type_libelle": unite.type.libelle_fr,
        "type_libelle_ar": unite.type.libelle_ar,
        "parent": str(unite.parent.uuid) if unite.parent_id else None,
        "profondeur": unite.profondeur,
        "actif": unite.actif,
        "affectations": getattr(unite, "nombre_affectations", None),
    }


def _type_unite(type_unite):
    return {
        "id": type_unite.pk,
        "code": type_unite.code,
        "libelle_fr": type_unite.libelle_fr,
        "libelle_ar": type_unite.libelle_ar,
        "ordre": type_unite.ordre,
        "actif": type_unite.actif,
        "unites": getattr(type_unite, "nombre", None),
    }


def _poste(poste):
    return {
        "id": poste.pk,
        "intitule_fr": poste.intitule_fr,
        "intitule_ar": poste.intitule_ar,
        "unite": str(poste.unite.uuid),
        "unite_libelle": str(poste.unite),
        "superieur": poste.superieur_id,
        "superieur_libelle": poste.superieur.intitule_fr if poste.superieur_id else None,
        "actif": poste.actif,
    }


def _resume_utilisateur(compte, maintenant):
    return {
        "uuid": str(compte.uuid),
        "identifiant": compte.identifiant,
        "nom": compte.nom,
        "prenom": compte.prenom,
        "nom_ar": compte.nom_ar,
        "actif": compte.is_active,
        "verrouille": bool(compte.verrouille_jusqu_a and compte.verrouille_jusqu_a > maintenant),
        "mfa_active": compte.mfa_active,
        "derniere_connexion": compte.last_login,
    }


def _affectation(affectation):
    return {
        "uuid": str(affectation.uuid),
        "role": str(affectation.role.uuid),
        "role_libelle": affectation.role.libelle_fr,
        "role_libelle_ar": affectation.role.libelle_ar,
        "unite": str(affectation.unite.uuid),
        "unite_libelle": str(affectation.unite),
        "poste_libelle": affectation.poste.intitule_fr if affectation.poste_id else None,
        "etendue_sous_unites": affectation.etendue_sous_unites,
        "date_debut": affectation.date_debut,
        "date_fin": affectation.date_fin,
        "active": affectation.est_active(),
        "attribuee_par": affectation.attribuee_par.get_full_name() if affectation.attribuee_par_id else None,
    }


def _role(role):
    return {
        "uuid": str(role.uuid),
        "code": role.code,
        "libelle_fr": role.libelle_fr,
        "libelle_ar": role.libelle_ar,
        "description": role.description,
        "mfa_requis": role.mfa_requis,
        "actif": role.actif,
        "systeme": role.systeme,
        "permissions": sorted(p.code for p in role.permissions.all()),
        "titulaires": getattr(role, "titulaires", None),
    }


# --- Organisation -------------------------------------------------------------------


@documenter
@api_view(["GET", "POST"])
@permission_requise(ORGANISATION)
def unites(request):
    acteur = request.user
    if request.method == "POST":
        formulaire = FormulaireUnite(request.data, acteur=acteur)
        if not formulaire.is_valid():
            return erreurs_formulaire(formulaire)
        unite = organisation.creer_unite(acteur, requete=request, **_donnees(formulaire, FormulaireUnite.Meta.fields))
        return Response(_unite(unite), status=status.HTTP_201_CREATED)
    visibles = (
        moteur.unites_autorisees(acteur, ORGANISATION)
        .select_related("type", "parent")
        .annotate(nombre_affectations=Count("affectations", filter=Q(affectations__date_fin__isnull=True)))
        .order_by("chemin")
    )
    return Response(
        {
            "unites": [_unite(u) for u in visibles],
            "types": [
                _type_unite(t) for t in TypeUnite.objects.filter(institution_id=acteur.institution_id, actif=True)
            ],
        }
    )


def _unite_visible(request, uuid):
    return get_object_or_404(
        moteur.unites_autorisees(request.user, ORGANISATION).select_related("type", "parent"), uuid=uuid
    )


@documenter
@api_view(["GET", "PATCH"])
@permission_requise(ORGANISATION)
def unite(request, uuid):
    objet = _unite_visible(request, uuid)
    if request.method == "PATCH":
        formulaire = FormulaireUnite(request.data, instance=objet, acteur=request.user)
        if not formulaire.is_valid():
            return erreurs_formulaire(formulaire)
        champs = _donnees(formulaire, FormulaireUnite.Meta.fields)
        objet.refresh_from_db()
        objet = organisation.modifier_unite(request.user, objet, requete=request, **champs)
    return Response(_unite(objet))


@documenter
@api_view(["POST"])
@permission_requise(ORGANISATION)
def unite_desactiver(request, uuid):
    objet = organisation.desactiver_unite(request.user, _unite_visible(request, uuid), requete=request)
    return Response(_unite(objet))


@documenter
@api_view(["GET", "POST"])
@permission_requise(ORGANISATION, portee_institution=True)
def types_unite(request):
    if request.method == "POST":
        formulaire = FormulaireTypeUnite(request.data)
        if not formulaire.is_valid():
            return erreurs_formulaire(formulaire)
        objet = organisation.enregistrer_type_unite(request.user, formulaire.instance, requete=request)
        return Response(_type_unite(objet), status=status.HTTP_201_CREATED)
    types = TypeUnite.objects.filter(institution_id=request.user.institution_id).annotate(nombre=Count("unites"))
    return Response([_type_unite(t) for t in types])


@documenter
@api_view(["PATCH"])
@permission_requise(ORGANISATION, portee_institution=True)
def type_unite(request, pk):
    objet = get_object_or_404(TypeUnite, pk=pk, institution_id=request.user.institution_id)
    formulaire = FormulaireTypeUnite(request.data, instance=objet)
    if not formulaire.is_valid():
        return erreurs_formulaire(formulaire)
    return Response(
        _type_unite(organisation.enregistrer_type_unite(request.user, formulaire.instance, requete=request))
    )


@documenter
@api_view(["GET", "POST"])
@permission_requise(ORGANISATION)
def postes(request):
    if request.method == "POST":
        formulaire = FormulairePoste(request.data, acteur=request.user)
        if not formulaire.is_valid():
            return erreurs_formulaire(formulaire)
        objet = organisation.enregistrer_poste(request.user, formulaire.instance, requete=request)
        return Response(_poste(objet), status=status.HTTP_201_CREATED)
    liste = (
        organisation.postes_visibles(request.user).select_related("superieur").order_by("unite__chemin", "intitule_fr")
    )
    return Response([_poste(p) for p in liste])


@documenter
@api_view(["PATCH"])
@permission_requise(ORGANISATION)
def poste(request, pk):
    objet = get_object_or_404(organisation.postes_visibles(request.user), pk=pk)
    formulaire = FormulairePoste(request.data, instance=objet, acteur=request.user)
    if not formulaire.is_valid():
        return erreurs_formulaire(formulaire)
    return Response(_poste(organisation.enregistrer_poste(request.user, formulaire.instance, requete=request)))


# --- Utilisateurs ---------------------------------------------------------------------

TRIS = {"nom": ("nom", "prenom"), "identifiant": ("identifiant",), "connexion": ("-last_login",)}


@documenter
@api_view(["GET", "POST"])
@permission_requise(UTILISATEURS)
def utilisateurs(request):
    acteur = request.user
    if request.method == "POST":
        formulaire = FormulaireCreationUtilisateur(request.data, acteur=acteur)
        if not formulaire.is_valid():
            return erreurs_formulaire(formulaire)
        donnees = formulaire.cleaned_data
        affectation = {"unite": donnees["unite"], "role": donnees["role"]} if donnees.get("unite") else None
        compte = identite.creer_utilisateur(
            acteur,
            mot_de_passe_temporaire=donnees["mot_de_passe_temporaire"],
            affectation=affectation,
            requete=request,
            **_donnees(formulaire, FormulaireCreationUtilisateur.Meta.fields),
        )
        return Response(_resume_utilisateur(compte, timezone.now()), status=status.HTTP_201_CREATED)

    liste = identite.utilisateurs_geres(acteur).select_related("appareil_totp")
    parametres = request.query_params
    recherche = parametres.get("q", "").strip()
    if recherche:
        liste = liste.filter(
            Q(identifiant__icontains=recherche)
            | Q(nom__icontains=recherche)
            | Q(prenom__icontains=recherche)
            | Q(nom_ar__icontains=recherche)
            | Q(courriel__icontains=recherche)
        )
    statut = parametres.get("statut", "")
    if statut == "actifs":
        liste = liste.filter(is_active=True)
    elif statut == "inactifs":
        liste = liste.filter(is_active=False)
    elif statut == "verrouilles":
        liste = liste.filter(verrouille_jusqu_a__gt=timezone.now())
    if parametres.get("unite"):
        liste = liste.filter(
            pk__in=Affectation.objects.actives().filter(unite__uuid=parametres["unite"]).values("utilisateur")
        )
    liste = liste.order_by(*TRIS.get(parametres.get("tri", "nom"), TRIS["nom"]))
    maintenant = timezone.now()
    return Response(paginer(request, liste, lambda compte: _resume_utilisateur(compte, maintenant)))


@documenter
@api_view(["GET"])
@permission_requise(UTILISATEURS)
def utilisateurs_options(request):
    """Listes de choix des formulaires de compte et d'affectation, dans le périmètre de l'acteur."""
    acteur = request.user
    return Response(
        {
            "unites": [
                {"uuid": str(u.uuid), "libelle": str(u), "profondeur": u.profondeur}
                for u in moteur.unites_autorisees(acteur, UTILISATEURS).filter(actif=True).order_by("chemin")
            ],
            "roles": [
                {"uuid": str(r.uuid), "libelle": r.libelle_fr, "libelle_ar": r.libelle_ar, "mfa_requis": r.mfa_requis}
                for r in Role.objects.filter(institution_id=acteur.institution_id, actif=True)
            ],
            "postes": [
                {"id": p.pk, "libelle": str(p), "unite": str(p.unite.uuid)}
                for p in Poste.objects.filter(institution_id=acteur.institution_id, actif=True).select_related("unite")
            ],
            "niveaux": [
                {"valeur": valeur, "libelle": str(libelle)}
                for valeur, libelle in NiveauHabilitation.choices
                if valeur <= acteur.niveau_habilitation
            ],
            "langues": [{"valeur": code, "libelle": nom} for code, nom in settings.LANGUAGES],
            "mot_de_passe_suggere": secrets.token_urlsafe(12),
        }
    )


def _compte_gere(request, uuid):
    return get_object_or_404(identite.utilisateurs_geres(request.user), uuid=uuid)


def _detail_utilisateur(compte):
    maintenant = timezone.now()
    return {
        **_resume_utilisateur(compte, maintenant),
        "courriel": compte.courriel,
        "langue": compte.langue,
        "niveau_habilitation": compte.niveau_habilitation,
        "doit_changer_mot_de_passe": compte.doit_changer_mot_de_passe,
        "echecs_connexion": compte.echecs_connexion,
        "affectations": [
            _affectation(a)
            for a in compte.affectations.select_related("unite", "role", "poste", "attribuee_par").order_by(
                "-date_debut"
            )
        ],
        "sessions": [
            {"debut": s.debut, "fin": s.fin, "adresse_ip": s.adresse_ip, "motif_fin": s.get_motif_fin_display()}
            for s in SessionUtilisateur.objects.filter(utilisateur=compte)[:10]
        ],
        "delegations": [
            _delegation(d)
            for d in Delegation.objects.filter(Q(delegant=compte) | Q(delegataire=compte))
            .select_related("delegant", "delegataire")
            .prefetch_related("roles")[:10]
        ],
    }


@documenter
@api_view(["GET", "PATCH"])
@permission_requise(UTILISATEURS)
def utilisateur(request, uuid):
    compte = _compte_gere(request, uuid)
    if request.method == "PATCH":
        formulaire = FormulaireProfilUtilisateur(request.data, instance=compte)
        if not formulaire.is_valid():
            return erreurs_formulaire(formulaire)
        champs = _donnees(formulaire, FormulaireProfilUtilisateur.Meta.fields)
        compte.refresh_from_db()
        identite.modifier_utilisateur(request.user, compte, requete=request, **champs)
    return Response(_detail_utilisateur(compte))


@documenter
@api_view(["POST"])
@permission_requise(UTILISATEURS)
def utilisateur_action(request, uuid, action):
    compte = _compte_gere(request, uuid)
    acteur = request.user
    if action == "desactiver":
        motif = str(request.data.get("motif", "")).strip()
        if not motif:
            from noyau.api_outils import reponse_erreurs

            return reponse_erreurs({"motif": [_("Indiquez le motif de la désactivation.")]})
        identite.desactiver_utilisateur(acteur, compte, motif=motif, requete=request)
    elif action == "reactiver":
        identite.reactiver_utilisateur(acteur, compte, requete=request)
    elif action == "mot-de-passe":
        mot_de_passe = secrets.token_urlsafe(12)
        identite.reinitialiser_mot_de_passe(acteur, compte, mot_de_passe, requete=request)
        return Response({"mot_de_passe": mot_de_passe, "utilisateur": _detail_utilisateur(compte)})
    elif action == "deverrouiller":
        identite.deverrouiller(acteur, compte, requete=request)
    elif action == "mfa":
        identite.reinitialiser_mfa(acteur, compte, requete=request)
    elif action == "sessions":
        identite.revoquer_sessions_par_administrateur(acteur, compte, requete=request)
    else:
        return Response(status=status.HTTP_404_NOT_FOUND)
    compte.refresh_from_db()
    return Response(_detail_utilisateur(compte))


@documenter
@api_view(["POST"])
@permission_requise(UTILISATEURS)
def utilisateur_affectations(request, uuid):
    compte = _compte_gere(request, uuid)
    formulaire = FormulaireAffectation(request.data, acteur=request.user)
    if not formulaire.is_valid():
        return erreurs_formulaire(formulaire)
    identite.creer_affectation(
        request.user, compte, requete=request, **_donnees(formulaire, FormulaireAffectation.Meta.fields)
    )
    return Response(_detail_utilisateur(compte), status=status.HTTP_201_CREATED)


@documenter
@api_view(["GET", "POST"])
@permission_requise(UTILISATEURS)
def utilisateur_delegations(request, uuid):
    compte = _compte_gere(request, uuid)
    if request.method == "GET":
        return Response(options_delegation(compte))
    return creer_delegation_depuis(request, request.user, compte)


@documenter
@api_view(["POST"])
@permission_requise(UTILISATEURS)
def affectation_cloturer(request, uuid):
    affectation = get_object_or_404(
        Affectation.objects.filter(utilisateur__in=identite.utilisateurs_geres(request.user)).select_related(
            "utilisateur", "unite", "role"
        ),
        uuid=uuid,
    )
    identite.cloturer_affectation(request.user, affectation, requete=request)
    return Response(_detail_utilisateur(affectation.utilisateur))


@documenter
@api_view(["GET"])
@permission_requise(UTILISATEURS)
def revue_habilitations(request):
    """Export CSV des comptes du périmètre et de leurs affectations en cours, pour revue périodique."""
    reponse = HttpResponse(content_type="text/csv; charset=utf-8")
    reponse["Content-Disposition"] = f'attachment; filename="habilitations-{timezone.localdate():%Y-%m-%d}.csv"'
    reponse.write("﻿")  # BOM : ouverture correcte des accents et de l'arabe dans un tableur
    ecrivain = csv.writer(reponse, delimiter=";")
    ecrivain.writerow(
        [
            _("Identifiant"),
            _("Nom"),
            _("Prénom"),
            _("Actif"),
            _("Niveau d'habilitation"),
            _("Double authentification"),
            _("Dernière connexion"),
            _("Rôle"),
            _("Unité"),
            _("Sous-unités"),
            _("Début"),
            _("Fin"),
        ]
    )
    oui, non = _("oui"), _("non")
    nombre = 0
    for compte in identite.utilisateurs_geres(request.user).select_related("appareil_totp").order_by("nom", "prenom"):
        affectations = list(compte.affectations.actives().select_related("role", "unite")) or [None]
        for a in affectations:
            ecrivain.writerow(
                [
                    compte.identifiant,
                    compte.nom,
                    compte.prenom,
                    oui if compte.is_active else non,
                    compte.get_niveau_habilitation_display(),
                    oui if compte.mfa_active else non,
                    compte.last_login.isoformat() if compte.last_login else "",
                    a.role.libelle_fr if a else "",
                    a.unite.code if a else "",
                    (oui if a.etendue_sous_unites else non) if a else "",
                    a.date_debut.isoformat() if a else "",
                    a.date_fin.isoformat() if a and a.date_fin else "",
                ]
            )
        nombre += 1
    journaliser("habilitations.export", acteur=request.user, requete=request, details={"comptes": nombre})
    return reponse


# --- Rôles -------------------------------------------------------------------------------


@documenter
@api_view(["GET", "POST"])
@permission_requise(ROLES, portee_institution=True)
def roles(request):
    if request.method == "POST":
        return _enregistrer_role(request, Role(), status.HTTP_201_CREATED)
    liste = identite.roles_visibles(request.user).annotate(
        titulaires=Count("affectations", filter=Q(affectations__date_fin__isnull=True), distinct=True)
    )
    return Response(
        {
            "roles": [_role(r) for r in liste],
            "permissions": [
                {"code": p.code, "groupe": p.groupe, "description": p.description}
                for p in Permission.objects.filter(actif=True)
            ],
        }
    )


def _enregistrer_role(request, objet, code_http):
    formulaire = FormulaireRole(request.data, instance=objet if objet.pk else None)
    if not formulaire.is_valid():
        return erreurs_formulaire(formulaire)
    objet = identite.enregistrer_role(
        request.user, formulaire.instance, formulaire.cleaned_data["permissions"], requete=request
    )
    return Response(_role(objet), status=code_http)


@documenter
@api_view(["GET", "PATCH"])
@permission_requise(ROLES, portee_institution=True)
def role(request, uuid):
    objet = get_object_or_404(Role, uuid=uuid, institution_id=request.user.institution_id)
    if request.method == "PATCH":
        return _enregistrer_role(request, objet, status.HTTP_200_OK)
    return Response(_role(objet))


# --- Journal des connexions -------------------------------------------------------------

ACTIONS_CONNEXION = [
    "connexion.reussie",
    "connexion.echec",
    "connexion.mfa_echec",
    "connexion.refus_verrouille",
    "connexion.ip_bloquee",
    "compte.verrouillage",
    "deconnexion",
    "deconnexion.inactivite",
]


@documenter
@api_view(["GET"])
@permission_requise(AUDIT, portee_institution=True)
def connexions(request):
    perimetre = Q(institution_id=request.user.institution_id)
    if not settings.GED_MULTI_INSTITUTIONS:
        # Tentatives sur des identifiants inconnus : rattachables à la seule institution de l'installation.
        perimetre |= Q(institution__isnull=True, acteur__isnull=True)
    evenements = JournalAudit.objects.filter(action__in=ACTIONS_CONNEXION).filter(perimetre).order_by("-id")
    filtre = request.query_params.get("action", "")
    if filtre in ACTIONS_CONNEXION:
        evenements = evenements.filter(action=filtre)
    resultat = paginer(
        request,
        evenements,
        lambda e: {
            "horodatage": e.horodatage,
            "action": e.action,
            "compte": e.acteur_libelle,
            "adresse_ip": e.adresse_ip,
            "resultat": e.resultat,
        },
    )
    resultat["actions"] = ACTIONS_CONNEXION
    return Response(resultat)


@documenter
@api_view(["GET"])
def tableau_de_bord(request):
    """Indicateurs de la page d'accueil, limités au périmètre de l'utilisateur."""
    acteur = request.user
    indicateurs = {}
    if moteur.a_permission(acteur, UTILISATEURS):
        geres = identite.utilisateurs_geres(acteur)
        indicateurs["comptes_actifs"] = geres.filter(is_active=True).count()
        indicateurs["comptes_verrouilles"] = geres.filter(verrouille_jusqu_a__gt=timezone.now()).count()
        indicateurs["comptes_sans_mfa"] = geres.filter(is_active=True, appareil_totp__isnull=True).count()
    if moteur.a_permission(acteur, ORGANISATION):
        indicateurs["unites"] = moteur.unites_autorisees(acteur, ORGANISATION).filter(actif=True).count()
    if moteur.portee_institution(acteur, ROLES):
        indicateurs["roles"] = Role.objects.filter(institution_id=acteur.institution_id, actif=True).count()
    if moteur.portee_institution(acteur, AUDIT):
        depuis = timezone.now() - timezone.timedelta(days=1)
        indicateurs["echecs_24h"] = JournalAudit.objects.filter(
            institution_id=acteur.institution_id, action="connexion.echec", horodatage__gte=depuis
        ).count()
    return Response({"indicateurs": indicateurs})
