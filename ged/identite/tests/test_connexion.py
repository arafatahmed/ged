import pytest
from django.db import IntegrityError, transaction
from django.test import Client

from audit.models import JournalAudit
from conftest import appel, connecter_api
from identite.models import Utilisateur


@pytest.mark.django_db
class TestModele:
    def test_creation(self, agent, institution):
        assert agent.institution == institution
        assert agent.check_password("mot-de-passe-solide-2026")
        assert not agent.is_staff
        assert str(agent) == "Awa Diallo (agent)"
        assert agent.get_full_name() == "Awa Diallo"
        assert agent.get_short_name() == "Awa"

    def test_superadmin_hors_institution(self, superadmin):
        assert superadmin.institution is None
        assert superadmin.is_superuser and superadmin.is_staff

    def test_utilisateur_ordinaire_rattache_a_une_institution(self, db):
        with pytest.raises(IntegrityError), transaction.atomic():
            Utilisateur.objects.create(identifiant="orphelin", nom="X", prenom="Y")

    def test_identifiant_obligatoire(self, db):
        with pytest.raises(ValueError):
            Utilisateur.objects.create_user("", "x")

    def test_mot_de_passe_hache(self, agent):
        assert "mot-de-passe" not in agent.password


@pytest.mark.django_db
class TestConnexion:
    def test_connexion_reussie_journalisee(self, agent):
        client = Client(REMOTE_ADDR="10.1.2.3")
        reponse = connecter_api(client, "agent")
        assert reponse.status_code == 200
        assert reponse.json()["authentifie"] is True
        assert reponse.json()["utilisateur"]["identifiant"] == "agent"
        evenement = JournalAudit.objects.get(action="connexion.reussie")
        assert evenement.acteur == agent
        assert evenement.adresse_ip == "10.1.2.3"

    def test_echec_journalise_sans_mot_de_passe(self, agent):
        reponse = connecter_api(Client(), "agent", "faux-mot-de-passe")
        assert reponse.status_code == 400
        assert reponse.json()["detail"] == "Identifiant ou mot de passe incorrect, ou compte temporairement verrouillé."
        evenement = JournalAudit.objects.get(action="connexion.echec")
        assert evenement.resultat == "refus"
        assert evenement.details == {"identifiant_saisi": "agent"}
        assert "faux-mot-de-passe" not in str(evenement.details)

    def test_champs_obligatoires(self, db):
        assert appel(Client(), "POST", "/api/v1/session/connexion/", {}).status_code == 400

    def test_compte_desactive_refuse(self, agent):
        agent.is_active = False
        agent.save()
        assert connecter_api(Client(), "agent").status_code == 400
        assert not JournalAudit.objects.filter(action="connexion.reussie").exists()

    def test_deconnexion(self, client_agent, agent):
        assert client_agent.get("/api/v1/session/deconnexion/").status_code == 405
        reponse = appel(client_agent, "POST", "/api/v1/session/deconnexion/")
        assert reponse.json()["authentifie"] is False
        assert JournalAudit.objects.filter(action="deconnexion", acteur=agent).exists()
        assert client_agent.get("/api/v1/compte/").status_code == 403

    def test_cookies_de_session_proteges(self, agent):
        client = Client()
        connecter_api(client, "agent")
        cookie = client.cookies["sessionid"]
        assert cookie["httponly"]
        assert cookie["samesite"] == "Strict"

    def test_session_anonyme_et_cookie_csrf(self, client, institution):
        reponse = client.get("/api/v1/session/")
        assert reponse.json() == {
            "authentifie": False,
            "etape": None,
            "utilisateur": None,
            "institution": {
                "nom_fr": "Institution de démonstration",
                "nom_ar": "مؤسسة تجريبية",
                "sigle": "DEMO",
                "couleur_primaire": "#1f4e79",
                "couleur_secondaire": "#2e7d32",
                "langue_defaut": "fr",
                "format_date": "d/m/Y",
                "logo": False,
            },
        }
        assert "csrftoken" in reponse.cookies

    def test_connexion_protegee_contre_le_csrf(self, agent):
        client = Client(enforce_csrf_checks=True)
        assert connecter_api(client, "agent").status_code == 403
        jeton = client.get("/api/v1/session/").cookies["csrftoken"].value
        assert connecter_api(client, "agent", HTTP_X_CSRFTOKEN=jeton).status_code == 200
        # Une fois connecté, toute écriture exige aussi le jeton.
        assert appel(client, "PATCH", "/api/v1/compte/", {"langue": "ar"}).status_code == 403
        assert (
            appel(
                client, "PATCH", "/api/v1/compte/", {"langue": "ar"}, HTTP_X_CSRFTOKEN=client.cookies["csrftoken"].value
            ).status_code
            == 200
        )


@pytest.mark.django_db
class TestAdministrationComptes:
    def test_creation_depuis_l_administration_journalisee(self, client_superadmin, institution):
        reponse = client_superadmin.post(
            "/administration-technique/identite/utilisateur/add/",
            {
                "identifiant": "nouvel.agent",
                "nom": "Ba",
                "prenom": "Moussa",
                "institution": institution.pk,
                "password1": "un-mot-de-passe-robuste-42",
                "password2": "un-mot-de-passe-robuste-42",
            },
        )
        assert reponse.status_code == 302, reponse.content.decode()[:3000]
        evenement = JournalAudit.objects.get(action="utilisateur.creation")
        assert "password1" not in json_texte(evenement.details)
        assert "un-mot-de-passe-robuste-42" not in json_texte(evenement.details)

    def test_changement_de_mot_de_passe_journalise(self, client_superadmin, agent):
        reponse = client_superadmin.post(
            f"/administration-technique/identite/utilisateur/{agent.pk}/password/",
            {"password1": "autre-mot-de-passe-robuste", "password2": "autre-mot-de-passe-robuste"},
        )
        assert reponse.status_code == 302
        assert JournalAudit.objects.filter(action="utilisateur.mot_de_passe.modification").exists()


def json_texte(donnees):
    import json

    return json.dumps(donnees, ensure_ascii=False)
