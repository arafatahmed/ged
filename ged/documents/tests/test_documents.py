"""Documents et fichiers : critères d'acceptation du lot 3 et règles de la matrice 3.5."""

import hashlib
import os

import pytest
from django.utils import timezone

from audit.models import JournalAudit
from documents import analyse
from documents.formats import reconnaitre
from documents.models import Document, EtatAnalyse, FichierDocument, StatutDocument
from noyau.services import definir_parametre

from .conftest import EICAR, EXE, PDF, PNG, FauxAntivirus, docx, fichier, objets_stockes

API = "/api/v1/documents"


def analyser(capture, antivirus=None):
    with capture(execute=True):
        return analyse.analyser_en_attente(antivirus or FauxAntivirus())


def principal(document_json, version=None):
    versions = document_json["versions"]
    choisie = next(v for v in versions if v["numero"] == version) if version else versions[0]
    return next(f for f in choisie["fichiers"] if f["role"] == "principal")


def url_fichier(document_json, fichier_json, mode="telecharger"):
    return f"{API}/{document_json['uuid']}/fichiers/{fichier_json['uuid']}/{mode}/"


@pytest.mark.django_db
class TestDepot:
    def test_creation_avec_fichier_en_quarantaine(self, creer_document, stockage_de_test):
        document = creer_document()
        assert document["version"] == 1
        assert principal(document)["etat"] == "en_attente"
        assert principal(document)["sha256"] == hashlib.sha256(PDF).hexdigest()
        stockes = objets_stockes(stockage_de_test)
        assert len(stockes) == 1 and stockes[0].startswith("quarantaine/")
        assert JournalAudit.objects.filter(action="document.creation").exists()

    def test_la_cle_de_stockage_n_est_jamais_exposee(self, creer_document, clients):
        document = creer_document()
        cle = FichierDocument.objects.get().cle_objet
        brut = clients["producteur"].get(f"{API}/{document['uuid']}/").content.decode()
        assert cle not in brut and "quarantaine" not in brut and "cle_objet" not in brut
        assert len(cle.rsplit("/", 1)[-1]) == 32  # identifiant aléatoire, non devinable

    def test_executable_renomme_en_pdf_refuse_sans_rien_stocker(self, creer_document, clients, arbre, type_note):
        reponse = clients["producteur"].post(
            f"{API}/",
            {
                "type": str(type_note.uuid),
                "unite_proprietaire": str(arbre["daf"].uuid),
                "titre": "Piège",
                "fichier": fichier("facture.pdf", EXE),
            },
        )
        assert reponse.status_code == 400
        assert "fichier" in reponse.json()["erreurs"]
        assert not Document.objects.exists() and not FichierDocument.objects.exists()
        assert JournalAudit.objects.filter(action="fichier.refus", resultat="refus").exists()

    def test_extension_differente_du_contenu_refusee(self, clients, arbre, type_note):
        reponse = clients["producteur"].post(
            f"{API}/",
            {
                "type": str(type_note.uuid),
                "unite_proprietaire": str(arbre["daf"].uuid),
                "titre": "Image",
                "fichier": fichier("image.pdf", PNG),
            },
        )
        assert reponse.status_code == 400

    def test_format_non_admis_par_le_type(self, clients, arbre, type_facture):
        reponse = clients["producteur"].post(
            f"{API}/",
            {
                "type": str(type_facture.uuid),
                "unite_proprietaire": str(arbre["daf"].uuid),
                "titre": "Facture",
                "metadonnees": '{"nature": "achat"}',
                "fichier": fichier("scan.png", PNG, "image/png"),
            },
        )
        assert reponse.status_code == 400
        assert "PNG" in reponse.json()["detail"]

    def test_fichier_vide_ou_trop_gros(self, clients, arbre, type_note, institution):
        donnees = {"type": str(type_note.uuid), "unite_proprietaire": str(arbre["daf"].uuid), "titre": "T"}
        vide = clients["producteur"].post(f"{API}/", {**donnees, "fichier": fichier("vide.pdf", b"")})
        assert vide.status_code == 400
        definir_parametre(institution, "fichiers.taille_max_mo", 1)
        gros = clients["producteur"].post(f"{API}/", {**donnees, "fichier": fichier("gros.pdf", PDF + b"0" * 1100000)})
        assert gros.status_code == 400
        assert "1 Mo" in gros.json()["detail"]

    def test_formats_bureautiques_reconnus(self):
        assert reconnaitre(docx()).code == "docx"
        assert reconnaitre(PDF).code == "pdf"
        assert reconnaitre(EXE) is None

    def test_document_sans_fichier_puis_premier_fichier(self, creer_document, clients):
        document = creer_document(par="bureau", contenu=None)
        assert document["version"] is None
        reponse = clients["bureau"].post(f"{API}/{document['uuid']}/versions/", {"fichier": fichier()})
        assert reponse.status_code == 201
        assert reponse.json()["version"] == 1


@pytest.mark.django_db
class TestAnalyse:
    def test_fichier_sain_publie_et_empreinte_recalculee(
        self, creer_document, clients, stockage_de_test, django_capture_on_commit_callbacks
    ):
        document = creer_document()
        assert analyser(django_capture_on_commit_callbacks) == 1
        enregistre = FichierDocument.objects.get()
        assert enregistre.etat_analyse == EtatAnalyse.SAIN
        assert objets_stockes(stockage_de_test) == [enregistre.cle_objet]
        assert enregistre.cle_objet.startswith("documents/")
        with open(os.path.join(stockage_de_test, enregistre.cle_objet), "rb") as flux:
            assert hashlib.sha256(flux.read()).hexdigest() == enregistre.sha256
        reponse = clients["producteur"].get(url_fichier(document, principal(document)))
        assert reponse.status_code == 200
        assert b"".join(reponse.streaming_content) == PDF
        assert "attachment" in reponse["Content-Disposition"]
        assert JournalAudit.objects.filter(action="fichier.analyse").exists()
        assert JournalAudit.objects.filter(action="fichier.telechargement").exists()

    def test_fichier_eicar_refuse_et_efface(
        self, creer_document, clients, stockage_de_test, django_capture_on_commit_callbacks
    ):
        document = creer_document(contenu=PDF + EICAR)
        analyser(django_capture_on_commit_callbacks)
        enregistre = FichierDocument.objects.get()
        assert enregistre.etat_analyse == EtatAnalyse.INFECTE
        assert enregistre.motif == "Eicar-Test-Signature"
        assert objets_stockes(stockage_de_test) == []
        assert clients["producteur"].get(url_fichier(document, principal(document))).status_code == 400
        assert JournalAudit.objects.filter(action="fichier.infecte", resultat="refus").exists()

    def test_fichier_modifie_dans_le_stockage_refuse(
        self, creer_document, stockage_de_test, django_capture_on_commit_callbacks
    ):
        creer_document()
        enregistre = FichierDocument.objects.get()
        with open(os.path.join(stockage_de_test, enregistre.cle_objet), "ab") as flux:
            flux.write(b"%alteration")
        analyser(django_capture_on_commit_callbacks)
        enregistre.refresh_from_db()
        assert enregistre.etat_analyse == EtatAnalyse.REFUSE
        assert "empreinte" in enregistre.motif

    def test_antivirus_indisponible_le_fichier_reste_en_attente(
        self, creer_document, django_capture_on_commit_callbacks
    ):
        from documents.antivirus import AntivirusIndisponible

        creer_document()
        with pytest.raises(AntivirusIndisponible):
            analyser(django_capture_on_commit_callbacks, FauxAntivirus(disponible=False))
        enregistre = FichierDocument.objects.get()
        assert enregistre.etat_analyse == EtatAnalyse.EN_ATTENTE
        assert enregistre.tentatives == 1

    def test_telechargement_impossible_avant_analyse(self, creer_document, clients):
        document = creer_document()
        assert clients["producteur"].get(url_fichier(document, principal(document))).status_code == 400

    def test_nettoyage_des_objets_orphelins(self, creer_document, stockage_de_test):
        creer_document()
        orphelin = stockage_de_test / "quarantaine" / "orphelin"
        orphelin.write_bytes(b"envoi interrompu")
        ancien = (timezone.now() - timezone.timedelta(hours=25)).timestamp()
        os.utime(orphelin, (ancien, ancien))
        for chemin in (stockage_de_test / "quarantaine").iterdir():
            if chemin.name != "orphelin":
                os.utime(chemin, (ancien, ancien))
        assert analyse.nettoyer_quarantaine() == 1
        assert len(objets_stockes(stockage_de_test)) == 1  # le fichier enregistré est conservé


@pytest.mark.django_db
class TestVersions:
    def test_une_nouvelle_version_n_ecrase_pas_la_precedente(
        self, creer_document, clients, django_capture_on_commit_callbacks
    ):
        document = creer_document()
        reponse = clients["producteur"].post(
            f"{API}/{document['uuid']}/versions/",
            {"fichier": fichier("note-v2.pdf", PDF + b"%v2"), "commentaire": "v2"},
        )
        assert reponse.status_code == 201
        detail = reponse.json()
        assert detail["version"] == 2
        assert [v["numero"] for v in detail["versions"]] == [2, 1]
        analyser(django_capture_on_commit_callbacks)
        premiere = clients["producteur"].get(url_fichier(detail, principal(detail, 1)))
        assert b"".join(premiere.streaming_content) == PDF
        seconde = clients["producteur"].get(url_fichier(detail, principal(detail, 2)))
        assert b"".join(seconde.streaming_content) == PDF + b"%v2"
        assert JournalAudit.objects.filter(action="document.version").exists()

    def test_piece_jointe(self, creer_document, clients):
        document = creer_document()
        reponse = clients["producteur"].post(
            f"{API}/{document['uuid']}/pieces-jointes/", {"fichier": fichier("annexe.png", PNG, "image/png")}
        )
        assert reponse.status_code == 201
        roles = [f["role"] for f in reponse.json()["versions"][0]["fichiers"]]
        assert sorted(roles) == ["piece_jointe", "principal"]

    def test_versionner_le_document_d_un_collegue_refuse(self, creer_document, clients):
        document = creer_document()
        reponse = clients["collegue"].post(f"{API}/{document['uuid']}/versions/", {"fichier": fichier()})
        assert reponse.status_code == 403
        assert JournalAudit.objects.filter(action="acces.refus").exists()

    def test_document_valide_non_modifiable(self, creer_document, clients):
        document = creer_document()
        Document.objects.filter(uuid=document["uuid"]).update(statut=StatutDocument.VALIDE)
        assert (
            clients["validateur"].post(f"{API}/{document['uuid']}/versions/", {"fichier": fichier()}).status_code == 403
        )
        reponse = clients["validateur"].patch(
            f"{API}/{document['uuid']}/", {"titre": "X"}, content_type="application/json"
        )
        assert reponse.status_code == 403


@pytest.mark.django_db
class TestDroits:
    """Matrice 3.5 : O (périmètre), P (objets propres), métadonnées seules, hors périmètre."""

    @pytest.fixture
    def document(self, creer_document, django_capture_on_commit_callbacks):
        document = creer_document()
        analyser(django_capture_on_commit_callbacks)
        return document

    @pytest.mark.parametrize(
        "qui, fiche, apercu, telechargement",
        [
            ("producteur", 200, 200, 200),  # auteur
            ("collegue", 200, 200, 403),  # producteur : télécharger « P »
            ("validateur", 200, 200, 200),  # O sur le périmètre
            ("bureau", 200, 200, 200),
            ("lecteur", 200, 200, 403),  # consultation seule : pas de téléchargement
            ("auditeur", 200, 403, 403),  # métadonnées seulement
            ("traitant", 404, 404, 404),  # « A » : objets affectés seulement (lot 7)
            ("drh", 404, 404, 404),  # hors périmètre : indiscernable d'un document inexistant
        ],
    )
    def test_matrice(self, document, clients, qui, fiche, apercu, telechargement):
        f = principal(document)
        assert clients[qui].get(f"{API}/{document['uuid']}/").status_code == fiche
        assert clients[qui].get(url_fichier(document, f, "apercu")).status_code == apercu
        assert clients[qui].get(url_fichier(document, f)).status_code == telechargement

    def test_anonyme(self, document, client):
        assert client.get(f"{API}/{document['uuid']}/").status_code == 403

    def test_apercu_affiche_dans_le_navigateur(self, document, clients):
        reponse = clients["lecteur"].get(url_fichier(document, principal(document), "apercu"))
        assert reponse["Content-Type"] == "application/pdf"
        assert "inline" in reponse["Content-Disposition"]
        assert reponse["Cache-Control"] == "private, no-store"

    def test_fichier_d_un_autre_document_introuvable(self, document, creer_document, clients):
        autre = creer_document(titre="Autre")
        assert clients["producteur"].get(url_fichier(autre, principal(document))).status_code == 404

    def test_traitant_voit_ses_propres_documents(self, creer_document, clients):
        document = creer_document(par="traitant")
        assert clients["traitant"].get(f"{API}/{document['uuid']}/").status_code == 200
        assert clients["traitant"].get(f"{API}/").json()["nombre"] == 1

    def test_liste_filtree_par_les_droits(self, creer_document, clients):
        creer_document(titre="Budget DAF")
        creer_document(par="drh", unite="drh", titre="Budget DRH")
        assert [d["titre"] for d in clients["producteur"].get(f"{API}/").json()["resultats"]] == ["Budget DAF"]
        assert clients["validateur"].get(f"{API}/", {"q": "budget"}).json()["nombre"] == 1
        assert clients["drh"].get(f"{API}/", {"q": "DAF"}).json()["nombre"] == 0

    def test_sous_unites_couvertes_par_l_extension(self, creer_document, clients):
        document = creer_document(par="validateur", unite="compta")
        assert clients["validateur"].get(f"{API}/{document['uuid']}/").status_code == 200
        assert clients["producteur"].get(f"{API}/{document['uuid']}/").status_code == 404


@pytest.mark.django_db
class TestConfidentialite:
    def test_niveau_insuffisant_document_invisible(self, creer_document, clients):
        document = creer_document(par="validateur", confidentialite=2)
        assert clients["producteur"].get(f"{API}/{document['uuid']}/").status_code == 404
        assert clients["producteur"].get(f"{API}/").json()["nombre"] == 0

    def test_secret_reserve_a_l_auteur(self, creer_document, clients, personnes, affecter, arbre):
        document = creer_document(par="validateur", confidentialite=3)
        autre = personnes["drh"]
        affecter(autre, arbre["daf"], "validateur")
        from conftest import client_pour

        assert client_pour(autre).get(f"{API}/{document['uuid']}/").status_code == 404
        assert clients["validateur"].get(f"{API}/{document['uuid']}/").status_code == 200

    def test_consultation_d_un_document_confidentiel_journalisee(self, creer_document, clients):
        document = creer_document(par="validateur", confidentialite=2)
        clients["validateur"].get(f"{API}/{document['uuid']}/")
        assert JournalAudit.objects.filter(action="document.consultation", objet_id=document["uuid"]).exists()

    def test_niveau_superieur_a_son_habilitation_refuse(self, clients, arbre, type_note):
        reponse = clients["producteur"].post(
            f"{API}/",
            {
                "type": str(type_note.uuid),
                "unite_proprietaire": str(arbre["daf"].uuid),
                "titre": "T",
                "confidentialite": "2",
            },
        )
        assert reponse.status_code == 400
        assert "confidentialite" in reponse.json()["erreurs"]

    def test_producteur_releve_mais_n_abaisse_pas(self, creer_document, clients):
        document = creer_document()
        url = f"{API}/{document['uuid']}/"
        assert (
            clients["producteur"].patch(url, {"confidentialite": 1}, content_type="application/json").status_code == 200
        )
        assert (
            clients["producteur"].patch(url, {"confidentialite": 0}, content_type="application/json").status_code == 403
        )
        assert (
            clients["validateur"].patch(url, {"confidentialite": 0}, content_type="application/json").status_code == 200
        )
        evenement = JournalAudit.objects.filter(action="document.modification").order_by("-pk").first()
        assert evenement.details["confidentialite"] == {"avant": 1, "apres": 0}


@pytest.mark.django_db
class TestMetadonnees:
    def creer(self, clients, arbre, type_facture, metadonnees):
        return clients["producteur"].post(
            f"{API}/",
            {
                "type": str(type_facture.uuid),
                "unite_proprietaire": str(arbre["daf"].uuid),
                "titre": "Facture",
                "metadonnees": metadonnees,
            },
        )

    def test_valeurs_normalisees(self, clients, arbre, type_facture):
        reponse = self.creer(clients, arbre, type_facture, '{"nature": "achat", "montant": "1250"}')
        assert reponse.status_code == 201
        assert reponse.json()["metadonnees"] == {"nature": "achat", "montant": 1250}

    @pytest.mark.parametrize(
        "valeurs, champ",
        [
            ("{}", "metadonnees.nature"),
            ('{"nature": "don"}', "metadonnees.nature"),
            ('{"nature": "achat", "montant": "beaucoup"}', "metadonnees.montant"),
            ('{"nature": "achat", "inconnue": 1}', "metadonnees.inconnue"),
        ],
    )
    def test_valeurs_refusees(self, clients, arbre, type_facture, valeurs, champ):
        reponse = self.creer(clients, arbre, type_facture, valeurs)
        assert reponse.status_code == 400
        assert champ in reponse.json()["erreurs"]

    def test_modification_journalisee_sans_contenu(self, creer_document, clients):
        document = creer_document(mots_cles=["budget"])
        reponse = clients["producteur"].patch(
            f"{API}/{document['uuid']}/",
            {"titre": "Titre confidentiel", "mots_cles": ["budget", "2027", "Budget"]},
            content_type="application/json",
        )
        assert reponse.status_code == 200
        assert reponse.json()["mots_cles"] == ["budget", "2027"]
        evenement = JournalAudit.objects.filter(action="document.modification").order_by("-pk").first()
        assert evenement.details == {"champs": ["mots_cles", "titre"]}
        assert "Titre confidentiel" not in str(evenement.details)

    def test_modifier_le_document_d_un_collegue_refuse(self, creer_document, clients):
        document = creer_document()
        url = f"{API}/{document['uuid']}/"
        assert clients["collegue"].patch(url, {"titre": "X"}, content_type="application/json").status_code == 403
        assert clients["validateur"].patch(url, {"titre": "X"}, content_type="application/json").status_code == 200


@pytest.mark.django_db
class TestRelationsEtDoublons:
    def test_relations(self, creer_document, clients):
        source, cible = creer_document(titre="Réponse"), creer_document(titre="Demande")
        url = f"{API}/{source['uuid']}/relations/"
        reponse = clients["producteur"].post(url, {"cible": cible["uuid"], "nature": "reponse_a"})
        assert reponse.status_code == 201
        assert reponse.json()["relations"][0]["document"]["titre"] == "Demande"
        assert clients["producteur"].post(url, {"cible": cible["uuid"], "nature": "reponse_a"}).status_code == 400
        assert clients["producteur"].post(url, {"cible": source["uuid"], "nature": "voir_aussi"}).status_code == 400
        entrante = clients["producteur"].get(f"{API}/{cible['uuid']}/").json()["relations"]
        assert entrante[0]["sens"] == "entrante"
        suppression = clients["producteur"].delete(f"{url}{entrante[0]['id']}/")
        assert suppression.status_code == 200 and suppression.json()["relations"] == []
        assert JournalAudit.objects.filter(action="relation.suppression").exists()

    def test_relation_vers_un_document_invisible(self, creer_document, clients):
        source = creer_document()
        cache = creer_document(par="drh", unite="drh")
        reponse = clients["producteur"].post(
            f"{API}/{source['uuid']}/relations/", {"cible": cache["uuid"], "nature": "voir_aussi"}
        )
        assert reponse.status_code == 404
        clients["drh"].post(f"{API}/{cache['uuid']}/relations/", {"cible": source["uuid"], "nature": "voir_aussi"})
        assert clients["producteur"].get(f"{API}/{source['uuid']}/").json()["relations"] == []

    def test_doublons_signales_seulement_s_ils_sont_visibles(self, creer_document, clients):
        visible = creer_document(titre="Original")
        creer_document(par="drh", unite="drh", titre="Copie DRH")
        copie = creer_document(titre="Copie")
        doublons = clients["producteur"].get(f"{API}/{copie['uuid']}/").json()["doublons"]
        assert [d["uuid"] for d in doublons] == [visible["uuid"]]


@pytest.mark.django_db
class TestOptionsEtSession:
    def test_options(self, clients, type_note):
        options = clients["producteur"].get(f"{API}/options/").json()
        assert [t["code"] for t in options["types"]] == ["note"]
        assert [u["libelle_fr"] for u in options["unites"]] == ["Unité daf"]
        assert [n["valeur"] for n in options["niveaux"]] == [0, 1]
        assert options["taille_max_mo"] == 100

    def test_droits_de_session(self, clients, client_admin):
        assert clients["producteur"].get("/api/v1/session/").json()["documents"] == {"consulter": True, "creer": True}
        assert clients["auditeur"].get("/api/v1/session/").json()["documents"] == {"consulter": True, "creer": False}
        assert client_admin.get("/api/v1/session/").json()["documents"] == {"consulter": False, "creer": False}
        assert client_admin.get("/api/v1/session/").json()["droits"]["types_document"] is True


@pytest.mark.django_db
def test_commande_d_analyse(creer_document, django_capture_on_commit_callbacks, capsys):
    from django.core.management import call_command

    creer_document()
    with django_capture_on_commit_callbacks(execute=True):
        call_command("analyser_fichiers")
    sortie = capsys.readouterr()
    assert "1 fichier(s) analysé(s)." in sortie.out
    assert "Aucun antivirus configuré" in sortie.err
    assert FichierDocument.objects.get().etat_analyse == EtatAnalyse.SAIN
