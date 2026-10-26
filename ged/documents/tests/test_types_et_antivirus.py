import os
import socket
import struct
import threading

import pytest

from audit.models import JournalAudit
from documents.antivirus import AntivirusIndisponible, ClientClamd, Verdict
from documents.models import DefinitionMetadonnee, TypeDocument

from .conftest import EICAR, PDF

API = "/api/v1/administration/types-document/"

TYPE = {
    "code": "courrier-entrant",
    "libelle_fr": "Courrier entrant",
    "libelle_ar": "بريد وارد",
    "categorie": "courrier",
    "formats_autorises": ["pdf", "jpeg"],
    "confidentialite_defaut": 0,
    "actif": True,
    "metadonnees": [
        {
            "code": "expediteur",
            "libelle_fr": "Expéditeur",
            "libelle_ar": "المرسل",
            "nature": "texte",
            "obligatoire": True,
            "valeurs_liste": [],
            "ordre": 1,
            "actif": True,
        },
        {
            "code": "mode",
            "libelle_fr": "Mode",
            "libelle_ar": "",
            "nature": "liste",
            "obligatoire": False,
            "valeurs_liste": ["poste", "porteur"],
            "ordre": 2,
            "actif": True,
        },
    ],
}


@pytest.mark.django_db
class TestTypesDocument:
    def test_creation_et_desactivation_d_une_metadonnee(self, client_admin):
        reponse = client_admin.post(API, TYPE, content_type="application/json")
        assert reponse.status_code == 201, reponse.json()
        cree = reponse.json()
        assert [d["code"] for d in cree["metadonnees"]] == ["expediteur", "mode"]
        modification = {**TYPE, "metadonnees": TYPE["metadonnees"][:1]}
        reponse = client_admin.patch(f"{API}{cree['uuid']}/", modification, content_type="application/json")
        assert reponse.status_code == 200
        assert DefinitionMetadonnee.objects.get(code="mode").actif is False
        assert JournalAudit.objects.filter(action="typedocument.modification").exists()

    def test_format_inconnu_et_liste_vide_refuses(self, client_admin):
        assert (
            client_admin.post(API, {**TYPE, "formats_autorises": ["exe"]}, content_type="application/json").status_code
            == 400
        )
        definition = {**TYPE["metadonnees"][1], "valeurs_liste": []}
        reponse = client_admin.post(API, {**TYPE, "metadonnees": [definition]}, content_type="application/json")
        assert reponse.status_code == 400
        assert not TypeDocument.objects.exists()

    def test_codes_de_metadonnees_en_double(self, client_admin):
        reponse = client_admin.post(
            API, {**TYPE, "metadonnees": [TYPE["metadonnees"][0]] * 2}, content_type="application/json"
        )
        assert reponse.status_code == 400

    def test_reserve_a_l_administration_de_toute_l_institution(self, client_agent):
        assert client_agent.get(API).status_code == 403
        assert client_agent.post(API, TYPE, content_type="application/json").status_code == 403
        assert JournalAudit.objects.filter(action="acces.refus").exists()


class FauxClamd:
    """Serveur clamd minimal sur un port local, pour tester le protocole INSTREAM."""

    def __init__(self, reponse_pour):
        self.reponse_pour = reponse_pour
        self.serveur = socket.create_server(("127.0.0.1", 0))
        self.port = self.serveur.getsockname()[1]
        threading.Thread(target=self._servir, daemon=True).start()

    def _servir(self):
        connexion, _adresse = self.serveur.accept()
        with connexion:
            commande = connexion.recv(len(b"zINSTREAM\0"))
            assert commande == b"zINSTREAM\0"
            contenu = b""
            while True:
                taille = struct.unpack("!L", self._lire(connexion, 4))[0]
                if not taille:
                    break
                contenu += self._lire(connexion, taille)
            connexion.sendall(self.reponse_pour(contenu).encode() + b"\0")

    @staticmethod
    def _lire(connexion, taille):
        donnees = b""
        while len(donnees) < taille:
            donnees += connexion.recv(taille - len(donnees))
        return donnees


class TestClientClamd:
    def test_protocole_instream(self):
        serveur = FauxClamd(lambda c: "stream: Eicar-Test-Signature FOUND" if EICAR in c else "stream: OK")
        client = ClientClamd("127.0.0.1", serveur.port, 5)
        assert client.analyser([PDF[:10], PDF[10:]]) == Verdict(sain=True)
        serveur = FauxClamd(lambda c: "stream: Eicar-Test-Signature FOUND" if EICAR in c else "stream: OK")
        verdict = ClientClamd("127.0.0.1", serveur.port, 5).analyser([EICAR])
        assert verdict == Verdict(sain=False, signature="Eicar-Test-Signature")

    @pytest.mark.parametrize(
        "reponse, attendu",
        [
            ("stream: OK", Verdict(sain=True)),
            ("stream: Win.Test.EICAR_HDB-1 FOUND", Verdict(sain=False, signature="Win.Test.EICAR_HDB-1")),
            ("INSTREAM size limit exceeded. ERROR", Verdict(sain=False, trop_volumineux=True)),
        ],
    )
    def test_interpretation(self, reponse, attendu):
        assert ClientClamd.interpreter(reponse) == attendu

    def test_erreur_et_serveur_absent(self):
        with pytest.raises(AntivirusIndisponible):
            ClientClamd.interpreter("Can't allocate memory ERROR")
        port_libre = socket.create_server(("127.0.0.1", 0))
        port = port_libre.getsockname()[1]
        port_libre.close()
        with pytest.raises(AntivirusIndisponible):
            ClientClamd("127.0.0.1", port, 2).analyser([PDF])


@pytest.mark.skipif(not os.environ.get("GED_TEST_CLAMAV"), reason="ClamAV réel non disponible (GED_TEST_CLAMAV=hôte)")
def test_eicar_detecte_par_clamav_reel():
    client = ClientClamd(os.environ["GED_TEST_CLAMAV"], 3310, 30)
    assert client.analyser([PDF]).sain
    verdict = client.analyser([EICAR])
    assert not verdict.sain and "Eicar" in verdict.signature
