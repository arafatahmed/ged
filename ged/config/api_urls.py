from django.urls import path

from administration import api as administration
from documents import api as documents
from identite import api as identite
from noyau.api import InstitutionCouranteView

session = [
    path("session/", identite.session, name="api_session"),
    path("session/connexion/", identite.connexion, name="api_connexion"),
    path("session/verification/", identite.verification, name="api_verification"),
    path("session/enrolement/", identite.enrolement, name="api_enrolement"),
    path("session/deconnexion/", identite.deconnexion, name="api_deconnexion"),
]

compte = [
    path("compte/", identite.compte, name="api_compte"),
    path("compte/mot-de-passe/", identite.changer_mot_de_passe, name="api_mot_de_passe"),
    path("compte/mfa/desactiver/", identite.desactiver_mfa, name="api_mfa_desactiver"),
    path("compte/mfa/codes/", identite.regenerer_codes, name="api_mfa_codes"),
    path("compte/sessions/fermer/", identite.fermer_autres_sessions, name="api_fermer_sessions"),
    path("compte/delegations/", identite.mes_delegations, name="api_mes_delegations"),
    path("compte/delegations/<uuid:uuid>/revoquer/", identite.revoquer_ma_delegation, name="api_revoquer_delegation"),
]

prefixe = "administration/"
administration_urls = [
    path(f"{prefixe}unites/", administration.unites),
    path(f"{prefixe}unites/<uuid:uuid>/", administration.unite),
    path(f"{prefixe}unites/<uuid:uuid>/desactiver/", administration.unite_desactiver),
    path(f"{prefixe}types-unite/", administration.types_unite),
    path(f"{prefixe}types-unite/<int:pk>/", administration.type_unite),
    path(f"{prefixe}postes/", administration.postes),
    path(f"{prefixe}postes/<int:pk>/", administration.poste),
    path(f"{prefixe}utilisateurs/", administration.utilisateurs),
    path(f"{prefixe}utilisateurs/options/", administration.utilisateurs_options),
    path(f"{prefixe}utilisateurs/revue-habilitations.csv", administration.revue_habilitations),
    path(f"{prefixe}utilisateurs/<uuid:uuid>/", administration.utilisateur),
    path(f"{prefixe}utilisateurs/<uuid:uuid>/affectations/", administration.utilisateur_affectations),
    path(f"{prefixe}utilisateurs/<uuid:uuid>/delegations/", administration.utilisateur_delegations),
    path(f"{prefixe}utilisateurs/<uuid:uuid>/<slug:action>/", administration.utilisateur_action),
    path(f"{prefixe}affectations/<uuid:uuid>/cloturer/", administration.affectation_cloturer),
    path(f"{prefixe}roles/", administration.roles),
    path(f"{prefixe}roles/<uuid:uuid>/", administration.role),
    path(f"{prefixe}connexions/", administration.connexions),
    path(f"{prefixe}types-document/", documents.types_document),
    path(f"{prefixe}types-document/<uuid:uuid>/", documents.type_document),
]

documents_urls = [
    path("documents/", documents.documents, name="api_documents"),
    path("documents/options/", documents.options, name="api_documents_options"),
    path("documents/<uuid:uuid>/", documents.document, name="api_document"),
    path("documents/<uuid:uuid>/versions/", documents.versions),
    path("documents/<uuid:uuid>/pieces-jointes/", documents.pieces_jointes),
    path("documents/<uuid:uuid>/relations/", documents.relations),
    path("documents/<uuid:uuid>/relations/<int:pk>/", documents.relation),
    path(
        "documents/<uuid:uuid>/fichiers/<uuid:fichier_uuid>/<str:mode>/",
        documents.fichier,
        name="api_document_fichier",
    ),
]

urlpatterns = [
    *session,
    *compte,
    *administration_urls,
    *documents_urls,
    path("institution/", InstitutionCouranteView.as_view(), name="api_institution"),
    path("tableau-de-bord/", administration.tableau_de_bord, name="api_tableau_de_bord"),
]
