"""Fixtures communes.

Les tests `transaction=True` ne doivent pas écrire dans le journal d'audit :
le nettoyage vide les tables par TRUNCATE, que le déclencheur d'audit refuse
sur une table non vide.
"""

import pytest
from django.test import Client
from django.utils import timezone

from identite import totp
from identite.models import Affectation, AppareilTotp, Role, Utilisateur
from noyau.services import creer_institution
from organisation.models import TypeUnite, UniteOrganisationnelle

MOT_DE_PASSE = "mot-de-passe-solide-2026"


@pytest.fixture
def institution(db):
    return creer_institution(
        code="demo",
        nom_fr="Institution de démonstration",
        nom_ar="مؤسسة تجريبية",
        sigle="DEMO",
        fuseau_horaire="Africa/Nouakchott",
    )


@pytest.fixture
def racine(institution):
    return UniteOrganisationnelle.objects.get(institution=institution, parent__isnull=True)


@pytest.fixture
def creer_unite(institution, racine):
    """Crée une unité sans contrôle de droits (préparation des tests)."""

    def _creer(code, parent=None, type_code="direction"):
        from organisation.services import _enregistrer_chemin

        unite = UniteOrganisationnelle.objects.create(
            institution=institution,
            type=TypeUnite.objects.get(institution=institution, code=type_code),
            parent=parent or racine,
            code=code,
            sigle=code.upper(),
            libelle_fr=f"Unité {code}",
        )
        _enregistrer_chemin(unite)
        return unite

    return _creer


@pytest.fixture
def creer_utilisateur(institution):
    def _creer(identifiant, niveau=0, **champs):
        return Utilisateur.objects.create_user(
            identifiant,
            MOT_DE_PASSE,
            nom=champs.pop("nom", identifiant.capitalize()),
            prenom=champs.pop("prenom", "Test"),
            institution=institution,
            niveau_habilitation=niveau,
            **champs,
        )

    return _creer


@pytest.fixture
def affecter(institution):
    """Affecte un rôle (par son code) dans une unité, sans contrôle de droits."""

    def _affecter(utilisateur, unite, code_role, etendue=False, **champs):
        role = Role.objects.get(institution=institution, code=code_role)
        return Affectation.objects.create(
            utilisateur=utilisateur, unite=unite, role=role, etendue_sous_unites=etendue, **champs
        )

    return _affecter


def activer_mfa(utilisateur):
    return AppareilTotp.objects.create(
        utilisateur=utilisateur, secret=totp.nouveau_secret(), confirme=True, confirme_le=timezone.now()
    )


@pytest.fixture
def agent(creer_utilisateur):
    return creer_utilisateur("agent", nom="Diallo", prenom="Awa")


@pytest.fixture
def superadmin(db):
    utilisateur = Utilisateur.objects.create_superuser("tech", MOT_DE_PASSE, nom="Tech", prenom="Admin")
    activer_mfa(utilisateur)
    return utilisateur


@pytest.fixture
def admin_fonctionnel(creer_utilisateur, affecter, racine):
    utilisateur = creer_utilisateur("admin", niveau=3, nom="Sow", prenom="Fatimata")
    affecter(utilisateur, racine, "administrateur_fonctionnel", etendue=True)
    activer_mfa(utilisateur)
    return utilisateur


def client_pour(utilisateur):
    client = Client()
    client.force_login(utilisateur)
    return client


@pytest.fixture
def client_agent(agent):
    return client_pour(agent)


@pytest.fixture
def client_superadmin(superadmin):
    return client_pour(superadmin)


@pytest.fixture
def client_admin(admin_fonctionnel):
    return client_pour(admin_fonctionnel)


def appel(client, methode, url, donnees=None, **entetes):
    """Appel JSON de l'API avec le client de test Django."""
    fonction = getattr(client, methode.lower())
    if methode.upper() == "GET":
        return fonction(url, donnees or {}, **entetes)
    return fonction(url, donnees or {}, content_type="application/json", **entetes)


def connecter_api(client, identifiant, mot_de_passe=MOT_DE_PASSE, **entetes):
    return appel(
        client,
        "POST",
        "/api/v1/session/connexion/",
        {"identifiant": identifiant, "mot_de_passe": mot_de_passe},
        **entetes,
    )
