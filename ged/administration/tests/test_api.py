import pytest

from audit.models import JournalAudit
from conftest import activer_mfa, appel, client_pour
from identite.models import Affectation, Role, Utilisateur
from organisation.models import Poste, TypeUnite

API = "/api/v1/administration"


@pytest.fixture
def arbre(creer_unite):
    daf = creer_unite("daf")
    return {"daf": daf, "compta": creer_unite("compta", parent=daf, type_code="service"), "drh": creer_unite("drh")}


@pytest.fixture
def admin_daf(creer_utilisateur, affecter, arbre):
    utilisateur = creer_utilisateur("admin.daf", niveau=1)
    affecter(utilisateur, arbre["daf"], "administrateur_unite", etendue=True)
    activer_mfa(utilisateur)
    return utilisateur


def role_uuid(institution, code):
    return str(Role.objects.get(institution=institution, code=code).uuid)


LECTURES = [
    "/unites/",
    "/types-unite/",
    "/postes/",
    "/utilisateurs/",
    "/utilisateurs/options/",
    "/roles/",
    "/connexions/",
]


@pytest.mark.django_db
class TestDroits:
    @pytest.mark.parametrize("chemin", LECTURES)
    def test_administrateur_fonctionnel(self, client_admin, chemin, arbre):
        assert client_admin.get(API + chemin).status_code == 200

    @pytest.mark.parametrize("chemin", LECTURES)
    def test_agent_refuse_et_journalise(self, client_agent, chemin):
        assert client_agent.get(API + chemin).status_code == 403
        assert JournalAudit.objects.filter(action="acces.refus").exists()

    def test_anonyme_refuse(self, client):
        assert client.get(API + "/utilisateurs/").status_code == 403

    @pytest.mark.parametrize(
        "chemin, attendu",
        [("/unites/", 200), ("/utilisateurs/", 200), ("/roles/", 403), ("/types-unite/", 403), ("/connexions/", 403)],
    )
    def test_administrateur_d_unite(self, admin_daf, chemin, attendu):
        assert client_pour(admin_daf).get(API + chemin).status_code == attendu

    def test_droits_du_menu_dans_la_session(self, client_admin, client_agent):
        assert client_admin.get("/api/v1/session/").json()["droits"] == {
            "organisation": True,
            "types_unite": True,
            "utilisateurs": True,
            "roles": True,
            "connexions": True,
        }
        assert not any(client_agent.get("/api/v1/session/").json()["droits"].values())


@pytest.mark.django_db
class TestOrganisation:
    def test_liste_limitee_au_perimetre(self, admin_daf, arbre):
        codes = [u["code"] for u in client_pour(admin_daf).get(API + "/unites/").json()["unites"]]
        assert codes == ["daf", "compta"]

    def test_unite_hors_perimetre_introuvable(self, admin_daf, arbre):
        assert client_pour(admin_daf).get(f"{API}/unites/{arbre['drh'].uuid}/").status_code == 404

    def test_creer_modifier_desactiver(self, client_admin, racine, institution):
        type_direction = TypeUnite.objects.get(institution=institution, code="direction").pk
        reponse = appel(
            client_admin,
            "POST",
            API + "/unites/",
            {"type": type_direction, "parent": str(racine.uuid), "code": "dsi", "libelle_fr": "DSI"},
        )
        assert reponse.status_code == 201, reponse.json()
        uuid = reponse.json()["uuid"]
        assert reponse.json()["profondeur"] == 1
        reponse = appel(
            client_admin,
            "PATCH",
            f"{API}/unites/{uuid}/",
            {
                "type": type_direction,
                "parent": str(racine.uuid),
                "code": "dsi",
                "libelle_fr": "Direction SI",
                "libelle_ar": "مديرية النظم",
            },
        )
        assert reponse.json()["libelle_ar"] == "مديرية النظم"
        assert appel(client_admin, "POST", f"{API}/unites/{uuid}/desactiver/").json()["actif"] is False

    def test_erreurs_de_formulaire(self, client_admin, racine):
        reponse = appel(client_admin, "POST", API + "/unites/", {"code": "pas valide"})
        assert reponse.status_code == 400
        assert {"type", "code", "libelle_fr"} <= set(reponse.json()["erreurs"])

    def test_erreur_metier(self, client_admin, arbre, agent, affecter):
        affecter(agent, arbre["compta"], "consultation")
        reponse = appel(client_admin, "POST", f"{API}/unites/{arbre['compta'].uuid}/desactiver/")
        assert reponse.status_code == 400 and "affectations" in reponse.json()["detail"]

    def test_types_et_postes(self, client_admin, arbre):
        reponse = appel(
            client_admin,
            "POST",
            API + "/types-unite/",
            {"code": "antenne", "libelle_fr": "Antenne", "ordre": 9, "actif": True},
        )
        assert reponse.status_code == 201
        appel(
            client_admin,
            "PATCH",
            f"{API}/types-unite/{reponse.json()['id']}/",
            {"code": "antenne", "libelle_fr": "Antenne régionale", "ordre": 9, "actif": True},
        )
        assert TypeUnite.objects.get(code="antenne").libelle_fr == "Antenne régionale"
        reponse = appel(
            client_admin,
            "POST",
            API + "/postes/",
            {"unite": str(arbre["daf"].uuid), "intitule_fr": "Directeur", "actif": True},
        )
        assert reponse.status_code == 201, reponse.json()
        reponse = appel(
            client_admin,
            "PATCH",
            f"{API}/postes/{reponse.json()['id']}/",
            {"unite": str(arbre["daf"].uuid), "intitule_fr": "Directeur financier", "actif": True},
        )
        assert Poste.objects.get().intitule_fr == "Directeur financier"


@pytest.mark.django_db
class TestUtilisateurs:
    def test_creer_un_compte_affecte(self, client_admin, arbre, institution):
        options = client_admin.get(API + "/utilisateurs/options/").json()
        assert len(options["mot_de_passe_suggere"]) >= 12
        assert [n["valeur"] for n in options["niveaux"]] == [0, 1, 2, 3]
        reponse = appel(
            client_admin,
            "POST",
            API + "/utilisateurs/",
            {
                "identifiant": "khadija.ba",
                "nom": "Ba",
                "prenom": "Khadija",
                "niveau_habilitation": 1,
                "mot_de_passe_temporaire": options["mot_de_passe_suggere"],
                "unite": str(arbre["daf"].uuid),
                "role": role_uuid(institution, "bureau_ordre"),
            },
        )
        assert reponse.status_code == 201, reponse.json()
        compte = Utilisateur.objects.get(identifiant="khadija.ba")
        assert compte.doit_changer_mot_de_passe
        assert compte.affectations.get().role.code == "bureau_ordre"

    def test_niveau_trop_eleve(self, admin_daf, arbre, institution):
        client = client_pour(admin_daf)
        assert [n["valeur"] for n in client.get(API + "/utilisateurs/options/").json()["niveaux"]] == [0, 1]
        reponse = appel(
            client,
            "POST",
            API + "/utilisateurs/",
            {
                "identifiant": "x.y",
                "nom": "Y",
                "prenom": "X",
                "niveau_habilitation": 3,
                "mot_de_passe_temporaire": "Temporaire-Solide-2026",
                "unite": str(arbre["daf"].uuid),
                "role": role_uuid(institution, "consultation"),
            },
        )
        assert reponse.status_code == 400 and "niveau_habilitation" in reponse.json()["erreurs"]

    def test_liste_filtree_et_paginee(self, client_admin, creer_utilisateur):
        creer_utilisateur("mariem.ould", nom="Ould", prenom="Mariem")
        creer_utilisateur("ahmed.salem", nom="Salem", prenom="Ahmed", is_active=False)
        donnees = client_admin.get(API + "/utilisateurs/?q=mariem").json()
        assert [c["identifiant"] for c in donnees["resultats"]] == ["mariem.ould"]
        assert donnees["nombre"] == 1 and donnees["pages"] == 1
        donnees = client_admin.get(API + "/utilisateurs/?statut=inactifs").json()
        assert [c["identifiant"] for c in donnees["resultats"]] == ["ahmed.salem"]

    def test_perimetre(self, admin_daf, creer_utilisateur, affecter, arbre):
        dehors = creer_utilisateur("dehors")
        affecter(dehors, arbre["drh"], "consultation")
        dedans = creer_utilisateur("dedans")
        affecter(dedans, arbre["compta"], "consultation")
        client = client_pour(admin_daf)
        identifiants = [c["identifiant"] for c in client.get(API + "/utilisateurs/").json()["resultats"]]
        assert identifiants == ["dedans"]
        assert client.get(f"{API}/utilisateurs/{dehors.uuid}/").status_code == 404
        assert appel(client, "POST", f"{API}/utilisateurs/{dehors.uuid}/desactiver/", {"motif": "x"}).status_code == 404

    def test_fiche_profil_et_affectations(self, client_admin, agent, arbre, institution):
        url = f"{API}/utilisateurs/{agent.uuid}/"
        assert client_admin.get(url).json()["identifiant"] == "agent"
        reponse = appel(client_admin, "PATCH", url, {"nom": "Diallo", "prenom": "Awa Mint", "niveau_habilitation": 2})
        assert reponse.json()["prenom"] == "Awa Mint"
        reponse = appel(
            client_admin,
            "POST",
            url + "affectations/",
            {
                "unite": str(arbre["daf"].uuid),
                "role": role_uuid(institution, "validateur"),
                "date_debut": "2026-01-01",
            },
        )
        assert reponse.status_code == 201, reponse.json()
        affectation = Affectation.objects.get(utilisateur=agent)
        reponse = appel(client_admin, "POST", f"{API}/affectations/{affectation.uuid}/cloturer/")
        assert reponse.json()["affectations"][0]["date_fin"] is not None

    def test_auto_affectation_refusee(self, client_admin, admin_fonctionnel, racine, institution):
        reponse = appel(
            client_admin,
            "POST",
            f"{API}/utilisateurs/{admin_fonctionnel.uuid}/affectations/",
            {"unite": str(racine.uuid), "role": role_uuid(institution, "validateur"), "date_debut": "2026-01-01"},
        )
        assert reponse.status_code == 404  # son propre compte n'est pas dans la liste des comptes gérés

    def test_actions(self, client_admin, agent):
        base = f"{API}/utilisateurs/{agent.uuid}"
        assert appel(client_admin, "POST", f"{base}/desactiver/", {"motif": ""}).status_code == 400
        assert appel(client_admin, "POST", f"{base}/desactiver/", {"motif": "Départ"}).json()["actif"] is False
        assert appel(client_admin, "POST", f"{base}/reactiver/").json()["actif"] is True
        reponse = appel(client_admin, "POST", f"{base}/mot-de-passe/").json()
        agent.refresh_from_db()
        assert agent.check_password(reponse["mot_de_passe"]) and agent.doit_changer_mot_de_passe
        for action in ("deverrouiller", "mfa", "sessions"):
            assert appel(client_admin, "POST", f"{base}/{action}/").status_code == 200
        assert appel(client_admin, "POST", f"{base}/inconnue/").status_code == 404

    def test_delegation_par_l_administrateur(self, client_admin, agent, creer_utilisateur, affecter, racine):
        affecter(agent, racine, "validateur")
        collegue = creer_utilisateur("collegue")
        from django.utils import timezone

        debut = timezone.now()
        reponse = appel(
            client_admin,
            "POST",
            f"{API}/utilisateurs/{agent.uuid}/delegations/",
            {
                "delegataire": str(collegue.uuid),
                "debut": debut.isoformat(),
                "fin": (debut + timezone.timedelta(days=2)).isoformat(),
                "motif": "Congé",
            },
        )
        assert reponse.status_code == 201, reponse.json()

    def test_revue_des_habilitations(self, client_admin, agent, affecter, racine):
        affecter(agent, racine, "consultation")
        reponse = client_admin.get(API + "/utilisateurs/revue-habilitations.csv")
        assert reponse["Content-Type"].startswith("text/csv")
        assert "Consultation seule" in reponse.content.decode("utf-8-sig")
        assert JournalAudit.objects.filter(action="habilitations.export").exists()


@pytest.mark.django_db
class TestRoles:
    def test_liste_et_catalogue(self, client_admin):
        donnees = client_admin.get(API + "/roles/").json()
        assert len(donnees["roles"]) == 9 and len(donnees["permissions"]) == 20

    def test_creer_un_role(self, client_admin):
        reponse = appel(
            client_admin,
            "POST",
            API + "/roles/",
            {
                "code": "secretariat",
                "libelle_fr": "Secrétariat",
                "actif": True,
                "permissions": ["courrier.enregistrer", "document.creer"],
            },
        )
        assert reponse.status_code == 201, reponse.json()
        assert reponse.json()["permissions"] == ["courrier.enregistrer", "document.creer"]

    def test_modifier_son_propre_role_refuse(self, client_admin, institution):
        role = Role.objects.get(institution=institution, code="administrateur_fonctionnel")
        reponse = appel(
            client_admin,
            "PATCH",
            f"{API}/roles/{role.uuid}/",
            {
                "code": role.code,
                "libelle_fr": role.libelle_fr,
                "actif": True,
                "mfa_requis": True,
                "permissions": ["document.consulter", "administration.roles"],
            },
        )
        assert reponse.status_code == 403


@pytest.mark.django_db
class TestJournalEtTableauDeBord:
    def test_journal_des_connexions(self, client_admin, client):
        appel(client, "POST", "/api/v1/session/connexion/", {"identifiant": "agent", "mot_de_passe": "x"})
        donnees = client_admin.get(API + "/connexions/?action=connexion.echec").json()
        assert donnees["resultats"][0]["action"] == "connexion.echec"
        assert "connexion.reussie" in donnees["actions"]

    def test_tableau_de_bord_selon_les_droits(self, client_admin, client_agent, arbre):
        indicateurs = client_admin.get("/api/v1/tableau-de-bord/").json()["indicateurs"]
        assert {"comptes_actifs", "unites", "roles", "echecs_24h"} <= set(indicateurs)
        assert client_agent.get("/api/v1/tableau-de-bord/").json() == {"indicateurs": {}}
