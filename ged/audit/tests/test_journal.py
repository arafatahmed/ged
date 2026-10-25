import datetime
import json

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import connection, transaction
from django.db.utils import DatabaseError
from django.test import RequestFactory, override_settings

from audit.models import JournalAudit, ScellementAudit
from audit.services import EMPREINTE_ORIGINE, adresse_ip, journaliser, sceller, verifier_chaine


def modifier_en_contournant_le_declencheur(sql, parametres=()):
    """Simule un attaquant disposant des droits du propriétaire du schéma."""
    with connection.cursor() as curseur:
        # Les clés étrangères de Django sont différées : on les vérifie d'abord,
        # PostgreSQL refusant ALTER TABLE tant que des vérifications sont en attente.
        curseur.execute("SET CONSTRAINTS ALL IMMEDIATE")
        curseur.execute("ALTER TABLE audit_journalaudit DISABLE TRIGGER audit_journalaudit_ajout_seul")
        curseur.execute(sql, parametres)
        curseur.execute("ALTER TABLE audit_journalaudit ENABLE TRIGGER audit_journalaudit_ajout_seul")


@pytest.fixture
def evenements(institution, agent):
    return [
        journaliser(f"test.action{i}", acteur=agent, details={"rang": i, "taux": 0.1, "liste": [1, 2]})
        for i in range(5)
    ]


@pytest.mark.django_db
class TestChaine:
    def test_chainage(self, evenements):
        premier = JournalAudit.objects.order_by("id").first()
        assert premier.empreinte_precedente == EMPREINTE_ORIGINE
        for precedent, suivant in zip(evenements, evenements[1:], strict=False):
            assert suivant.empreinte_precedente == precedent.empreinte
        assert len({e.empreinte for e in evenements}) == 5

    def test_attributs_deduits(self, evenements, agent, institution):
        evenement = evenements[0]
        assert evenement.acteur == agent
        assert evenement.acteur_libelle == "agent"
        assert evenement.institution == institution

    def test_chaine_intacte_apres_relecture(self, evenements):
        rapport = verifier_chaine()
        assert rapport.integre
        assert rapport.nombre == JournalAudit.objects.count()

    def test_valeurs_decimales_stables(self, institution):
        journaliser("test", details={"grand": 1e20, "petit": 0.000001, "imbrique": {"x": [1.5]}})
        assert verifier_chaine().integre

    def test_modification_detectee(self, evenements):
        cible = evenements[2]
        modifier_en_contournant_le_declencheur(
            "UPDATE audit_journalaudit SET action = 'falsifie' WHERE id = %s", [cible.id]
        )
        rapport = verifier_chaine()
        assert not rapport.integre
        assert rapport.anomalies == [(cible.id, "contenu modifié")]

    def test_suppression_detectee(self, evenements):
        cible = evenements[2]
        modifier_en_contournant_le_declencheur("DELETE FROM audit_journalaudit WHERE id = %s", [cible.id])
        rapport = verifier_chaine()
        assert rapport.anomalies == [(evenements[3].id, "lien rompu avec l'événement précédent")]

    def test_recalcul_complet_detecte_par_les_scellements(self, evenements, tmp_path):
        sceller(datetime.date.today(), tmp_path)
        # L'attaquant modifie une ligne et recalcule toute la chaîne de façon cohérente.
        from audit.services import calculer_empreinte

        modifier_en_contournant_le_declencheur(
            "UPDATE audit_journalaudit SET action = 'falsifie' WHERE id = %s", [evenements[1].id]
        )
        precedente = EMPREINTE_ORIGINE
        for evenement in JournalAudit.objects.order_by("id"):
            evenement.empreinte_precedente = precedente
            evenement.empreinte = calculer_empreinte(evenement)
            modifier_en_contournant_le_declencheur(
                "UPDATE audit_journalaudit SET empreinte_precedente = %s, empreinte = %s WHERE id = %s",
                [evenement.empreinte_precedente, evenement.empreinte, evenement.id],
            )
            precedente = evenement.empreinte
        rapport = verifier_chaine(tmp_path)
        assert not rapport.integre
        assert any("scellement" in raison for _id, raison in rapport.anomalies)
        assert any("copie" in raison for _id, raison in rapport.anomalies)


@pytest.mark.django_db
class TestProtectionBase:
    @pytest.mark.parametrize(
        "sql",
        [
            "UPDATE audit_journalaudit SET action = 'x'",
            "DELETE FROM audit_journalaudit",
            "TRUNCATE audit_journalaudit CASCADE",
        ],
    )
    def test_ecritures_refusees_par_le_declencheur(self, evenements, sql):
        nombre = JournalAudit.objects.count()
        with pytest.raises(DatabaseError, match="ajout seul"), transaction.atomic(), connection.cursor() as curseur:
            curseur.execute("SET CONSTRAINTS ALL IMMEDIATE")
            curseur.execute(sql)
        assert JournalAudit.objects.count() == nombre

    def test_orm_refuse_aussi(self, evenements):
        with pytest.raises(DatabaseError), transaction.atomic():
            JournalAudit.objects.filter(pk=evenements[0].pk).delete()

    def test_scellements_proteges(self, evenements, tmp_path):
        sceller(datetime.date.today(), tmp_path)
        with pytest.raises(DatabaseError, match="ajout seul"), transaction.atomic():
            ScellementAudit.objects.update(empreinte="0" * 64)

    def test_role_applicatif_sans_droit_de_modification(self, settings):
        role = settings.GED_DB_ROLE_APPLICATIF
        if not role:
            pytest.skip("GED_DB_ROLE_APPLICATIF non défini dans cet environnement")
        with connection.cursor() as curseur:
            for privilege, attendu in [("SELECT", True), ("INSERT", True), ("UPDATE", False), ("DELETE", False)]:
                curseur.execute("SELECT has_table_privilege(%s, 'audit_journalaudit', %s)", [role, privilege])
                assert curseur.fetchone()[0] is attendu, privilege


@pytest.mark.django_db
class TestTransactions:
    def test_evenement_annule_avec_l_operation(self, institution):
        with pytest.raises(RuntimeError), transaction.atomic():
            journaliser("test.annule")
            raise RuntimeError
        assert not JournalAudit.objects.filter(action="test.annule").exists()
        journaliser("test.suivant")
        assert verifier_chaine().integre


class TestAdresseIp:
    def test_adresse_directe(self):
        requete = RequestFactory().get("/", REMOTE_ADDR="10.0.0.5", HTTP_X_FORWARDED_FOR="1.2.3.4")
        assert adresse_ip(requete) == "10.0.0.5"

    @override_settings(GED_PROXY_DE_CONFIANCE=True)
    def test_derriere_le_proxy_seule_la_derniere_adresse_compte(self):
        requete = RequestFactory().get("/", REMOTE_ADDR="172.18.0.2", HTTP_X_FORWARDED_FOR="6.6.6.6, 41.188.1.7")
        assert adresse_ip(requete) == "41.188.1.7"

    def test_adresse_invalide_ignoree(self):
        assert adresse_ip(RequestFactory().get("/", REMOTE_ADDR="pas-une-ip")) == ""
        assert adresse_ip(None) == ""


@pytest.mark.django_db
class TestCommandes:
    def test_scellement_et_verification(self, evenements, tmp_path, capsys):
        jour = datetime.date.today()
        call_command("sceller_audit", "--date", jour.isoformat(), "--repertoire", str(tmp_path))
        copie = json.loads((tmp_path / f"scellement-{jour.isoformat()}.json").read_text())
        assert copie["dernier_id"] == evenements[-1].id
        assert copie["empreinte"] == evenements[-1].empreinte
        assert copie["nombre_evenements"] == JournalAudit.objects.filter(id__lte=evenements[-1].id).count()
        assert JournalAudit.objects.filter(action="audit.scellement").exists()

        call_command("verifier_audit", "--scellements", str(tmp_path))
        assert "Chaîne intègre" in capsys.readouterr().out
        assert JournalAudit.objects.filter(action="audit.verification", resultat="succes").exists()

    def test_double_scellement_refuse(self, evenements, tmp_path):
        jour = datetime.date.today().isoformat()
        call_command("sceller_audit", "--date", jour, "--repertoire", str(tmp_path))
        with pytest.raises(CommandError, match="déjà scellée"):
            call_command("sceller_audit", "--date", jour, "--repertoire", str(tmp_path))

    def test_journee_sans_evenement(self, db, tmp_path, capsys):
        call_command("sceller_audit", "--date", "2000-01-01", "--repertoire", str(tmp_path))
        assert "Aucun événement" in capsys.readouterr().out

    def test_verification_en_echec(self, evenements):
        modifier_en_contournant_le_declencheur(
            "UPDATE audit_journalaudit SET action = 'x' WHERE id = %s", [evenements[0].id]
        )
        with pytest.raises(CommandError, match="altérée"):
            call_command("verifier_audit")
        assert JournalAudit.objects.filter(action="audit.verification", resultat="erreur").exists()


@pytest.mark.django_db
class TestAdministration:
    def test_journal_en_lecture_seule(self, client_superadmin, evenements):
        assert client_superadmin.get("/administration-technique/audit/journalaudit/").status_code == 200
        url = f"/administration-technique/audit/journalaudit/{evenements[0].pk}/delete/"
        assert client_superadmin.post(url, {"post": "yes"}).status_code == 403
        assert client_superadmin.get("/administration-technique/audit/journalaudit/add/").status_code == 403
