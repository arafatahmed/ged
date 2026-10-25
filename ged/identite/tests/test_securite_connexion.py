import time

import pytest
from django.core.cache import cache
from django.test import Client
from django.utils import timezone

from audit.models import JournalAudit
from conftest import MOT_DE_PASSE, activer_mfa, appel, client_pour, connecter_api
from identite import mfa, totp
from identite.models import CodeSecours, SessionUtilisateur, Utilisateur

NOUVEAU = "nouveau-mot-de-passe-2027"


@pytest.fixture(autouse=True)
def vider_cache():
    cache.clear()
    yield
    cache.clear()


def code_courant(utilisateur):
    utilisateur.appareil_totp.refresh_from_db()
    return totp.code_hotp(utilisateur.appareil_totp.secret, totp.pas_courant())


def verifier(client, code):
    return appel(client, "POST", "/api/v1/session/verification/", {"code": code})


def changer(client, ancien=MOT_DE_PASSE, nouveau=NOUVEAU, confirmation=NOUVEAU):
    return appel(
        client,
        "POST",
        "/api/v1/compte/mot-de-passe/",
        {"ancien": ancien, "nouveau": nouveau, "confirmation": confirmation},
    )


@pytest.mark.django_db
class TestVerrouillage:
    def test_dix_echecs_verrouillent_le_compte(self, agent):
        client = Client()
        for _i in range(9):
            connecter_api(client, "agent", "mauvais")
        agent.refresh_from_db()
        assert agent.echecs_connexion == 9 and not agent.est_verrouille()
        connecter_api(client, "agent", "mauvais")
        agent.refresh_from_db()
        assert agent.est_verrouille()
        assert JournalAudit.objects.get(action="compte.verrouillage").details["echecs"] == 10
        assert JournalAudit.objects.filter(action="connexion.echec").count() == 10

    def test_bon_mot_de_passe_refuse_pendant_le_verrouillage(self, agent):
        agent.verrouille_jusqu_a = timezone.now() + timezone.timedelta(minutes=5)
        agent.save()
        reponse = connecter_api(Client(), "agent")
        assert reponse.status_code == 400
        assert "verrouillé" in reponse.json()["detail"]
        assert JournalAudit.objects.filter(action="connexion.refus_verrouille").exists()

    def test_verrouillage_expire(self, agent):
        agent.verrouille_jusqu_a = timezone.now() - timezone.timedelta(seconds=1)
        agent.echecs_connexion = 10
        agent.save()
        assert connecter_api(Client(), "agent").json()["authentifie"]
        agent.refresh_from_db()
        assert agent.echecs_connexion == 0

    def test_seuil_parametrable(self, agent, institution):
        from noyau.services import definir_parametre

        definir_parametre(institution, "connexion.seuil_verrouillage", 3)
        for _i in range(3):
            connecter_api(Client(), "agent", "mauvais")
        agent.refresh_from_db()
        assert agent.est_verrouille()

    def test_limitation_par_adresse_ip(self, agent, monkeypatch):
        from identite import backends

        monkeypatch.setattr(backends, "MAX_ECHECS_PAR_IP", 3)
        client = Client(REMOTE_ADDR="10.9.9.9")
        for _i in range(3):
            connecter_api(client, "inconnu", "x")
        assert connecter_api(client, "agent").status_code == 400
        assert JournalAudit.objects.filter(action="connexion.ip_bloquee").exists()
        assert connecter_api(Client(REMOTE_ADDR="10.9.9.10"), "agent").status_code == 200


@pytest.mark.django_db
class TestDoubleAuthentification:
    def test_connexion_en_deux_etapes(self, agent):
        activer_mfa(agent)
        client = Client()
        reponse = connecter_api(client, "agent")
        assert reponse.json() | {"institution": None} == {
            "authentifie": False,
            "etape": "mfa",
            "utilisateur": None,
            "institution": None,
        }
        assert client.get("/api/v1/compte/").status_code == 403  # pas encore connecté
        reponse = verifier(client, code_courant(agent))
        assert reponse.json()["authentifie"] is True
        assert client.get("/api/v1/compte/").status_code == 200
        assert JournalAudit.objects.filter(action="connexion.reussie", acteur=agent).exists()

    def test_code_faux_compte_comme_un_echec(self, agent, institution):
        from noyau.services import definir_parametre

        definir_parametre(institution, "connexion.seuil_verrouillage", 3)
        activer_mfa(agent)
        client = Client()
        connecter_api(client, "agent")
        for _i in range(2):
            assert verifier(client, "000000").status_code == 400
        reponse = verifier(client, "000000")
        assert reponse.status_code == 401 and reponse.json()["code"] == "etape_expiree"
        agent.refresh_from_db()
        assert agent.est_verrouille()
        assert JournalAudit.objects.filter(action="connexion.mfa_echec").count() == 3

    def test_code_rejoue_refuse(self, agent):
        activer_mfa(agent)
        client = Client()
        connecter_api(client, "agent")
        code = code_courant(agent)
        verifier(client, code)
        autre = Client()
        connecter_api(autre, "agent")
        assert verifier(autre, code).status_code == 400

    def test_etape_expiree(self, agent, monkeypatch):
        activer_mfa(agent)
        client = Client()
        connecter_api(client, "agent")
        depart = time.time()
        monkeypatch.setattr(time, "time", lambda: depart + 600)
        assert verifier(client, code_courant(agent)).status_code == 401

    def test_verification_sans_mot_de_passe_impossible(self, agent):
        activer_mfa(agent)
        assert verifier(Client(), "123456").status_code == 401

    def test_role_exigeant_la_mfa_impose_l_enrolement(self, creer_utilisateur, affecter, racine):
        archiviste = creer_utilisateur("archiviste")
        affecter(archiviste, racine, "archiviste")
        client = Client()
        assert connecter_api(client, "archiviste").json()["etape"] == "enrolement"
        page = client.get("/api/v1/session/enrolement/").json()
        assert page["qr_code"].startswith("data:image/svg+xml")
        assert page["obligatoire"] is True
        archiviste.refresh_from_db()
        reponse = appel(client, "POST", "/api/v1/session/enrolement/", {"code": code_courant(archiviste)})
        assert len(reponse.json()["codes_secours"]) == 10
        assert reponse.json()["session"]["authentifie"] is True
        assert CodeSecours.objects.filter(utilisateur=archiviste).count() == 10
        assert client.get("/api/v1/compte/").status_code == 200
        assert JournalAudit.objects.filter(action="mfa.activation").exists()

    def test_enrolement_code_faux(self, creer_utilisateur, affecter, racine):
        archiviste = creer_utilisateur("archiviste")
        affecter(archiviste, racine, "archiviste")
        client = Client()
        connecter_api(client, "archiviste")
        assert appel(client, "POST", "/api/v1/session/enrolement/", {"code": "000000"}).status_code == 400

    def test_code_de_secours_a_usage_unique(self, agent):
        activer_mfa(agent)
        codes = mfa.generer_codes_secours(agent)
        client = Client()
        connecter_api(client, "agent")
        assert verifier(client, codes[0].lower()).json()["authentifie"]
        autre = Client()
        connecter_api(autre, "agent")
        assert verifier(autre, codes[0]).status_code == 400

    def test_session_ouverte_bloquee_si_role_mfa(self, agent, affecter, racine):
        client = client_pour(agent)
        affecter(agent, racine, "auditeur")
        reponse = client.get("/api/v1/compte/")
        assert reponse.status_code == 403 and reponse.json()["code"] == "mfa_requise"
        assert client.get("/api/v1/session/").json()["exigences"]["activer_mfa"] is True
        assert client.get("/api/v1/session/enrolement/").status_code == 200

    def test_desactivation_refusee_si_role_mfa(self, admin_fonctionnel):
        assert appel(client_pour(admin_fonctionnel), "POST", "/api/v1/compte/mfa/desactiver/").status_code == 400
        admin_fonctionnel.refresh_from_db()
        assert admin_fonctionnel.mfa_active

    def test_desactivation_volontaire_et_codes(self, agent):
        activer_mfa(agent)
        client = client_pour(agent)
        assert len(appel(client, "POST", "/api/v1/compte/mfa/codes/").json()["codes_secours"]) == 10
        assert appel(client, "POST", "/api/v1/compte/mfa/desactiver/").status_code == 204
        assert not Utilisateur.objects.get(pk=agent.pk).mfa_active

    def test_administration_technique_passe_par_la_connexion_de_l_application(self, superadmin):
        reponse = Client().get("/administration-technique/login/?next=/administration-technique/")
        assert reponse["Location"].startswith("/connexion?suivant=")


@pytest.mark.django_db
class TestSessions:
    def test_expiration_apres_inactivite(self, agent, monkeypatch):
        client = Client()
        connecter_api(client, "agent")
        assert client.get("/api/v1/compte/").status_code == 200
        depart = time.time()
        monkeypatch.setattr(time, "time", lambda: depart + 31 * 60)
        reponse = client.get("/api/v1/compte/")
        assert reponse.status_code == 401 and reponse.json()["code"] == "session_expiree"
        assert SessionUtilisateur.objects.get(utilisateur=agent).motif_fin == "inactivite"
        assert JournalAudit.objects.filter(action="deconnexion.inactivite").exists()

    def test_changement_de_mot_de_passe_obligatoire(self, agent):
        agent.doit_changer_mot_de_passe = True
        agent.save()
        client = Client()
        connecter_api(client, "agent")
        reponse = client.get("/api/v1/compte/")
        assert reponse.status_code == 403 and reponse.json()["code"] == "changement_mot_de_passe_requis"
        assert changer(client, ancien="faux").status_code == 400
        assert changer(client, confirmation="autre").status_code == 400
        assert changer(client, nouveau="123", confirmation="123").status_code == 400
        reponse = changer(client)
        assert reponse.status_code == 200
        assert reponse.json()["exigences"]["changer_mot_de_passe"] is False
        assert client.get("/api/v1/compte/").status_code == 200
        assert JournalAudit.objects.filter(action="compte.mot_de_passe.modification").exists()

    def test_changement_de_mot_de_passe_ferme_les_autres_sessions(self, agent):
        premier, second = Client(), Client()
        connecter_api(premier, "agent")
        connecter_api(second, "agent")
        changer(premier)
        assert premier.get("/api/v1/compte/").status_code == 200
        assert second.get("/api/v1/compte/").status_code == 403

    def test_fermer_mes_autres_sessions(self, agent):
        premier, second = Client(), Client()
        connecter_api(premier, "agent")
        connecter_api(second, "agent")
        assert appel(premier, "POST", "/api/v1/compte/sessions/fermer/").json() == {"sessions_fermees": 1}
        assert premier.get("/api/v1/compte/").status_code == 200
        assert second.get("/api/v1/compte/").status_code == 403

    def test_mon_compte(self, agent, affecter, racine):
        affecter(agent, racine, "consultation")
        client = Client()
        connecter_api(client, "agent")
        donnees = client.get("/api/v1/compte/").json()
        assert donnees["affectations"][0]["role"] == "Consultation seule"
        assert donnees["sessions"][0]["courante"] is True
        assert appel(client, "PATCH", "/api/v1/compte/", {"langue": "xx"}).status_code == 400
        appel(client, "PATCH", "/api/v1/compte/", {"langue": "ar"})
        agent.refresh_from_db()
        assert agent.langue == "ar"


@pytest.mark.django_db
class TestMesDelegations:
    def test_creer_et_revoquer(self, agent, creer_utilisateur, affecter, racine):
        affecter(agent, racine, "validateur")
        collegue = creer_utilisateur("collegue")
        client = client_pour(agent)
        options = client.get("/api/v1/compte/delegations/").json()
        assert [r["libelle"] for r in options["roles"]] == ["Responsable et validateur"]
        assert any(d["uuid"] == str(collegue.uuid) for d in options["delegataires"])
        debut = timezone.now()
        reponse = appel(
            client,
            "POST",
            "/api/v1/compte/delegations/",
            {
                "delegataire": str(collegue.uuid),
                "debut": debut.isoformat(),
                "fin": (debut + timezone.timedelta(days=3)).isoformat(),
                "motif": "Mission",
                "roles": [],
            },
        )
        assert reponse.status_code == 201, reponse.json()
        uuid = reponse.json()["uuid"]
        assert appel(client, "POST", f"/api/v1/compte/delegations/{uuid}/revoquer/").status_code == 204

    def test_erreurs_de_saisie(self, agent):
        reponse = appel(client_pour(agent), "POST", "/api/v1/compte/delegations/", {"delegataire": "pas-un-uuid"})
        assert set(reponse.json()["erreurs"]) == {"delegataire", "debut", "fin", "motif"}

    def test_duree_excessive(self, agent, creer_utilisateur):
        collegue = creer_utilisateur("collegue")
        debut = timezone.now()
        reponse = appel(
            client_pour(agent),
            "POST",
            "/api/v1/compte/delegations/",
            {
                "delegataire": str(collegue.uuid),
                "debut": debut.isoformat(),
                "fin": (debut + timezone.timedelta(days=200)).isoformat(),
                "motif": "x",
            },
        )
        assert reponse.status_code == 400 and "fin" in reponse.json()["erreurs"]
