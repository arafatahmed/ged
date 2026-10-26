import io
import json
import os
import zipfile

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile

from conftest import activer_mfa, client_pour
from documents.antivirus import Verdict
from documents.models import DefinitionMetadonnee, TypeDocument

PDF = b"%PDF-1.4\n1 0 obj << /Type /Catalog >> endobj\ntrailer << /Root 1 0 R >>\n%%EOF\n"
PNG = bytes.fromhex("89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c489") + b"\x00" * 32
EXE = b"MZ\x90\x00\x03\x00\x00\x00\x04\x00\x00\x00\xff\xff\x00\x00" + b"\x00" * 48 + b"PE\x00\x00"
# Fichier de test antivirus normalisé (EICAR), reconstitué à l'exécution : écrit en clair, il ferait
# mettre ce fichier source en quarantaine par l'antivirus du poste de développement.
EICAR = ("X5O!P%@AP[4\\PZX54(P^)7CC)7}$" + "EICAR-STANDARD-ANTIVIRUS-TEST-FILE!$H+H*").encode()


def docx():
    tampon = io.BytesIO()
    with zipfile.ZipFile(tampon, "w") as archive:
        archive.writestr("[Content_Types].xml", '<?xml version="1.0"?><Types/>')
        archive.writestr("_rels/.rels", '<?xml version="1.0"?><Relationships/>')
        archive.writestr("word/document.xml", '<?xml version="1.0"?><w:document/>')
    return tampon.getvalue()


def fichier(nom="note.pdf", contenu=PDF, type_mime="application/pdf"):
    return SimpleUploadedFile(nom, contenu, content_type=type_mime)


class FauxAntivirus:
    """Antivirus de test : détecte la chaîne EICAR, ou se déclare indisponible."""

    nom = "faux"

    def __init__(self, disponible=True):
        self.disponible = disponible

    def analyser(self, morceaux):
        from documents.antivirus import AntivirusIndisponible

        contenu = b"".join(morceaux)
        if not self.disponible:
            raise AntivirusIndisponible("hors service")
        if EICAR in contenu:
            return Verdict(sain=False, signature="Eicar-Test-Signature")
        return Verdict(sain=True)


@pytest.fixture
def arbre(creer_unite):
    daf = creer_unite("daf")
    return {"daf": daf, "compta": creer_unite("compta", parent=daf, type_code="service"), "drh": creer_unite("drh")}


@pytest.fixture
def type_facture(institution):
    type_document = TypeDocument.objects.create(
        institution=institution, code="facture", libelle_fr="Facture", libelle_ar="فاتورة", formats_autorises=["pdf"]
    )
    DefinitionMetadonnee.objects.create(
        type_document=type_document, code="montant", libelle_fr="Montant", nature="nombre"
    )
    DefinitionMetadonnee.objects.create(
        type_document=type_document,
        code="nature",
        libelle_fr="Nature",
        nature="liste",
        valeurs_liste=["achat", "vente"],
        obligatoire=True,
    )
    return type_document


@pytest.fixture
def type_note(institution):
    return TypeDocument.objects.create(institution=institution, code="note", libelle_fr="Note")


@pytest.fixture
def personnes(creer_utilisateur, affecter, arbre):
    """Un compte par rôle modèle utile au lot 3, dans la DAF sauf mention contraire."""

    def creer(identifiant, role, unite="daf", niveau=1, etendue=False):
        utilisateur = creer_utilisateur(identifiant, niveau=niveau)
        affecter(utilisateur, arbre[unite], role, etendue=etendue)
        return utilisateur

    personnes = {
        "producteur": creer("producteur", "producteur"),
        "collegue": creer("collegue", "producteur"),
        "validateur": creer("validateur", "validateur", niveau=3, etendue=True),
        "bureau": creer("bureau", "bureau_ordre"),
        "traitant": creer("traitant", "traitant"),
        "lecteur": creer("lecteur", "consultation"),
        "auditeur": creer("auditeur", "auditeur"),
        "drh": creer("agent.drh", "validateur", unite="drh", niveau=3),
    }
    activer_mfa(personnes["auditeur"])  # rôle à double authentification obligatoire
    return personnes


@pytest.fixture
def clients(personnes):
    return {nom: client_pour(utilisateur) for nom, utilisateur in personnes.items()}


@pytest.fixture
def creer_document(clients, arbre, type_note):
    """Crée un document par l'API, avec un fichier PDF par défaut."""

    def _creer(par="producteur", unite="daf", type_document=None, contenu=PDF, nom="note.pdf", **champs):
        donnees = {
            "type": str((type_document or type_note).uuid),
            "unite_proprietaire": str(arbre[unite].uuid),
            "titre": champs.pop("titre", "Note de service"),
            **{cle: json.dumps(v) if isinstance(v, dict | list) else v for cle, v in champs.items()},
        }
        if contenu is not None:
            donnees["fichier"] = fichier(nom, contenu)
        reponse = clients[par].post("/api/v1/documents/", donnees)
        assert reponse.status_code == 201, reponse.json()
        return reponse.json()

    return _creer


@pytest.fixture(autouse=True)
def stockage_de_test(settings, tmp_path):
    """Un répertoire de stockage neuf par test."""
    settings.STORAGES = {
        **settings.STORAGES,
        "default": {"BACKEND": "django.core.files.storage.FileSystemStorage", "OPTIONS": {"location": str(tmp_path)}},
    }
    yield tmp_path


def objets_stockes(racine):
    return sorted(
        os.path.relpath(os.path.join(dossier, nom), racine).replace(os.sep, "/")
        for dossier, _sous, noms in os.walk(racine)
        for nom in noms
    )
