import pytest
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, override_settings

from audit.models import JournalAudit
from noyau.models import Institution, ParametreInstitution
from noyau.services import creer_institution, definir_parametre, lire_parametre

PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 32


@pytest.mark.django_db
class TestInstitution:
    def test_creation_journalisee(self):
        institution = creer_institution(code="min", nom_fr="Ministère", sigle="MIN")
        evenement = JournalAudit.objects.get(action="institution.creation")
        assert evenement.objet_id == str(institution.uuid)
        assert evenement.institution == institution

    def test_mono_institution_refuse_une_seconde(self, institution):
        with pytest.raises(ValidationError, match="mono-institution"):
            creer_institution(code="autre", nom_fr="Autre", sigle="AUT")
        assert JournalAudit.objects.filter(action="institution.creation").count() == 1

    @override_settings(GED_MULTI_INSTITUTIONS=True)
    def test_multi_institutions_autorise_plusieurs(self, institution):
        creer_institution(code="autre", nom_fr="Autre", sigle="AUT")
        assert Institution.objects.count() == 2

    @pytest.mark.parametrize("champ, valeur", [("couleur_primaire", "red"), ("fuseau_horaire", "Mars/Olympus")])
    def test_valeurs_invalides(self, champ, valeur):
        with pytest.raises(ValidationError):
            creer_institution(code="min", nom_fr="Ministère", sigle="MIN", **{champ: valeur})

    def test_logo_png_accepte_et_svg_refuse(self, institution):
        institution.logo = SimpleUploadedFile("logo.png", PNG)
        institution.full_clean()
        institution.logo = SimpleUploadedFile("logo.png", b"<svg onload='alert(1)'></svg>")
        with pytest.raises(ValidationError, match="PNG ou JPEG"):
            institution.full_clean()
        institution.logo = SimpleUploadedFile("logo.png", PNG + b"\x00" * (1024 * 1024))
        with pytest.raises(ValidationError, match="1 Mo"):
            institution.full_clean()

    def test_nom_selon_la_langue(self, institution):
        assert institution.nom("ar") == "مؤسسة تجريبية"
        assert institution.nom("fr") == "Institution de démonstration"


@pytest.mark.django_db
class TestParametres:
    def test_valeur_par_defaut(self, institution):
        assert lire_parametre(institution, "session.inactivite_minutes") == 30

    def test_modification_validee_et_journalisee(self, institution, agent):
        definir_parametre(institution, "session.inactivite_minutes", 15, acteur=agent)
        definir_parametre(institution, "session.inactivite_minutes", 20, acteur=agent)
        assert lire_parametre(institution, "session.inactivite_minutes") == 20
        assert ParametreInstitution.objects.count() == 1
        evenement = JournalAudit.objects.filter(action="parametre.modification").order_by("id").last()
        assert evenement.details == {"cle": "session.inactivite_minutes", "avant": 15, "apres": 20}
        assert evenement.acteur == agent

    @pytest.mark.parametrize(
        "cle, valeur",
        [
            ("session.inactivite_minutes", 1),
            ("session.inactivite_minutes", "30"),
            ("session.inactivite_minutes", True),
            ("interface.chiffres", "romains"),
            ("cle.inconnue", 1),
        ],
    )
    def test_valeurs_refusees(self, institution, cle, valeur):
        with pytest.raises(ValidationError):
            definir_parametre(institution, cle, valeur)
        assert not JournalAudit.objects.filter(action="parametre.modification").exists()


@pytest.mark.django_db
class TestPages:
    def test_sante(self, client):
        reponse = client.get("/sante/")
        assert reponse.status_code == 200
        assert reponse.json() == {"statut": "ok"}

    def test_routes_du_frontend_hors_de_django(self, client):
        # /, /connexion… sont servies par le frontend Angular (Nginx), pas par Django.
        assert client.get("/connexion/").status_code == 404

    def test_logo_absent(self, client, institution):
        assert client.get("/institution/logo/").status_code == 404

    def test_logo_servi_avec_son_type_reel(self, client, institution):
        institution.logo = SimpleUploadedFile("logo.png", PNG)
        institution.save()
        reponse = client.get("/institution/logo/")
        assert reponse.status_code == 200
        assert reponse["Content-Type"] == "image/png"
        assert reponse["X-Content-Type-Options"] == "nosniff"

    @override_settings(GED_MULTI_INSTITUTIONS=True)
    def test_multi_institutions_aucune_identite_avant_connexion(self, client, institution):
        assert client.get("/institution/logo/").status_code == 404
        assert client.get("/api/v1/session/").json()["institution"] is None


@pytest.mark.django_db
class TestLangue:
    def test_messages_de_l_api_dans_la_langue_demandee(self, client, institution):
        donnees = {"identifiant": "personne", "mot_de_passe": "x"}
        francais = client.post("/api/v1/session/connexion/", donnees, content_type="application/json")
        assert "incorrect" in francais.json()["detail"]
        arabe = client.post("/api/v1/session/connexion/", donnees, content_type="application/json", HTTP_X_LANGUE="ar")
        assert "غير صحيحة" in arabe.json()["detail"]
        assert arabe["Content-Language"] == "ar"

    def test_langue_par_defaut_de_l_institution(self, client, institution):
        institution.langue_defaut = "ar"
        institution.save()
        reponse = client.post("/api/v1/session/connexion/", {}, content_type="application/json")
        assert reponse["Content-Language"] == "ar"

    def test_preference_de_l_utilisateur(self, client_agent, agent):
        agent.langue = "ar"
        agent.save()
        assert client_agent.get("/api/v1/compte/")["Content-Language"] == "ar"


@pytest.mark.django_db
class TestApi:
    def test_api_exige_une_connexion(self, client, institution):
        assert client.get("/api/v1/institution/").status_code == 403

    def test_institution_courante(self, client_agent, institution):
        donnees = client_agent.get("/api/v1/institution/").json()
        assert donnees["uuid"] == str(institution.uuid)
        assert donnees["sigle"] == "DEMO"
        assert "id" not in donnees

    def test_superadmin_sans_institution(self, client_superadmin):
        assert client_superadmin.get("/api/v1/institution/").status_code == 404

    def test_schema_openapi_reserve_aux_utilisateurs_connectes(self, client, client_agent):
        assert client.get("/api/schema/").status_code == 403
        assert client_agent.get("/api/schema/").status_code == 200


@pytest.mark.django_db
class TestAdministration:
    def test_modification_journalisee_avec_avant_apres(self, client_superadmin, institution):
        url = f"/administration-technique/noyau/institution/{institution.pk}/change/"
        formulaire = {
            "code": "demo",
            "nom_fr": "Nouveau nom",
            "nom_ar": "",
            "sigle": "DEMO",
            "couleur_primaire": "#1f4e79",
            "couleur_secondaire": "#2e7d32",
            "adresse": "",
            "telephone": "",
            "courriel": "",
            "site_web": "",
            "fuseau_horaire": "Africa/Nouakchott",
            "langue_defaut": "fr",
            "format_date": "d/m/Y",
            "actif": "on",
        }
        reponse = client_superadmin.post(url, formulaire)
        assert reponse.status_code == 302, reponse.content.decode()[:2000]
        evenement = JournalAudit.objects.get(action="institution.modification")
        assert evenement.details["avant"]["nom_fr"] == "Institution de démonstration"
        assert evenement.details["apres"]["nom_fr"] == "Nouveau nom"
        assert evenement.acteur_libelle == "tech"

    def test_suppression_impossible(self, client_superadmin, institution):
        url = f"/administration-technique/noyau/institution/{institution.pk}/delete/"
        assert client_superadmin.post(url, {"post": "yes"}).status_code == 403
        assert Institution.objects.filter(pk=institution.pk).exists()

    def test_administration_refusee_aux_agents(self, client_agent):
        reponse = client_agent.get("/administration-technique/")
        assert reponse.status_code == 302
        assert Client().get("/administration-technique/").status_code == 302
