import datetime
import threading
from concurrent.futures import ThreadPoolExecutor

import pytest
from django.core.exceptions import ValidationError
from django.db import connections, transaction

from noyau import numerotation
from noyau.models import CompteurSerie, Institution, SerieNumerotation
from noyau.services import attribuer_numero


class TestGabarit:
    @pytest.mark.parametrize(
        "gabarit, portee",
        [
            ("{SEQ:5}", {"par_annee": False}),
            ("{SIGLE}/{AAAA}/{SEQ:5}", {"par_annee": True}),
            ("CE-{AA}{MM}-{SEQ:3}", {"par_annee": True}),
            ("{UNITE}/{CATEGORIE}/{AAAA}/{SEQ:4}", {"par_annee": True, "par_unite": True, "par_categorie": True}),
        ],
    )
    def test_gabarits_valides(self, gabarit, portee):
        numerotation.analyser_gabarit(gabarit, **portee)

    @pytest.mark.parametrize(
        "gabarit, portee, extrait",
        [
            ("{AAAA}", {}, "exactement un jeton"),
            ("{SEQ:3}-{SEQ:3}", {}, "exactement un jeton"),
            ("{SEQ}", {}, "longueur"),
            ("{SEQ:13}", {}, "longueur"),
            ("{INCONNU}/{SEQ:3}", {}, "Jeton inconnu"),
            ("{AAAA:2}/{SEQ:3}", {}, "Jeton inconnu"),
            ("{SEQ:3}}", {}, "Accolade"),
            ("{seq:3}", {}, "Accolade"),
            ("{SEQ:4}", {"par_annee": True}, "annuelle"),
            ("{AAAA}/{SEQ:4}", {"par_annee": True, "par_unite": True}, "par unité"),
            ("{AAAA}/{SEQ:4}", {"par_annee": True, "par_categorie": True}, "par catégorie"),
        ],
    )
    def test_gabarits_invalides(self, gabarit, portee, extrait):
        with pytest.raises(ValidationError) as erreur:
            numerotation.analyser_gabarit(gabarit, **portee)
        assert any(extrait in message for message in erreur.value.messages)

    def test_formatage(self):
        reference = numerotation.formater(
            "{SIGLE}/{UNITE}/{CATEGORIE}/{AA}{MM}/{AAAA}/{SEQ:5}",
            sequence=42,
            date=datetime.date(2026, 3, 9),
            sigle="MIN",
            unite="DAF",
            categorie="NOTE",
        )
        assert reference == "MIN/DAF/NOTE/2603/2026/00042"

    def test_la_sequence_deborde_sans_tronquer(self):
        assert numerotation.formater("{SEQ:2}", sequence=123, date=datetime.date(2026, 1, 1)) == "123"


@pytest.fixture
def serie(institution):
    return SerieNumerotation.objects.create(
        institution=institution, code="ce", libelle_fr="Courrier entrant", gabarit="CE/{AAAA}/{SEQ:5}"
    )


@pytest.mark.django_db
class TestAttribution:
    def test_numeros_successifs(self, serie):
        date = datetime.date(2026, 5, 1)
        numeros = [attribuer_numero(serie, date=date) for _ in range(3)]
        assert numeros == ["CE/2026/00001", "CE/2026/00002", "CE/2026/00003"]

    def test_remise_a_un_chaque_annee(self, serie):
        assert attribuer_numero(serie, date=datetime.date(2026, 12, 31)) == "CE/2026/00001"
        assert attribuer_numero(serie, date=datetime.date(2027, 1, 1)) == "CE/2027/00001"
        assert attribuer_numero(serie, date=datetime.date(2026, 12, 31)) == "CE/2026/00002"

    def test_serie_continue_sans_remise_annuelle(self, institution):
        serie = SerieNumerotation.objects.create(
            institution=institution, code="dossier", libelle_fr="Dossiers", gabarit="D-{SEQ:4}", par_annee=False
        )
        attribuer_numero(serie, date=datetime.date(2026, 12, 31))
        assert attribuer_numero(serie, date=datetime.date(2027, 1, 1)) == "D-0002"

    def test_compteur_distinct_par_unite(self, institution):
        serie = SerieNumerotation.objects.create(
            institution=institution,
            code="cs",
            libelle_fr="Courrier sortant",
            gabarit="{SIGLE}/{UNITE}/{AAAA}/{SEQ:3}",
            par_unite=True,
        )
        date = datetime.date(2026, 2, 1)
        assert attribuer_numero(serie, unite="DAF", date=date) == "DEMO/DAF/2026/001"
        assert attribuer_numero(serie, unite="DRH", date=date) == "DEMO/DRH/2026/001"
        assert attribuer_numero(serie, unite="DAF", date=date) == "DEMO/DAF/2026/002"

    def test_code_unite_obligatoire_et_controle(self, institution):
        serie = SerieNumerotation.objects.create(
            institution=institution,
            code="cs",
            libelle_fr="Sortant",
            gabarit="{UNITE}/{SEQ:3}",
            par_annee=False,
            par_unite=True,
        )
        for invalide in ["", "DAF/../x", "a" * 31, "D A F"]:
            with pytest.raises(ValidationError):
                attribuer_numero(serie, unite=invalide)

    def test_date_par_defaut_dans_le_fuseau_de_l_institution(self, serie):
        assert attribuer_numero(serie).startswith("CE/")

    def test_serie_inactive_refusee(self, serie):
        serie.actif = False
        serie.save()
        with pytest.raises(ValidationError):
            attribuer_numero(serie)

    def test_annulation_de_la_transaction_rend_le_numero(self, serie):
        date = datetime.date(2026, 5, 1)
        with pytest.raises(RuntimeError), transaction.atomic():
            attribuer_numero(serie, date=date)
            raise RuntimeError("échec de l'enregistrement")
        assert attribuer_numero(serie, date=date) == "CE/2026/00001"

    def test_gabarit_fige_apres_premiere_attribution(self, serie):
        serie.full_clean()
        attribuer_numero(serie, date=datetime.date(2026, 1, 1))
        serie.gabarit = "X/{AAAA}/{SEQ:5}"
        with pytest.raises(ValidationError, match="nouvelle série"):
            serie.full_clean()
        serie.refresh_from_db()
        serie.libelle_fr = "Nouveau libellé"
        serie.full_clean()


@pytest.mark.django_db(transaction=True)
def test_hors_transaction_refuse():
    institution = Institution.objects.create(code="i", nom_fr="I", sigle="I")
    serie = SerieNumerotation.objects.create(
        institution=institution, code="s", libelle_fr="S", gabarit="{SEQ:3}", par_annee=False
    )
    with pytest.raises(RuntimeError, match="transaction"):
        attribuer_numero(serie)


@pytest.mark.django_db(transaction=True)
def test_attributions_simultanees_sans_doublon_ni_trou():
    """Critère d'acceptation du lot 1 : 50 demandes simultanées, 50 numéros distincts et consécutifs."""
    institution = Institution.objects.create(code="i", nom_fr="I", sigle="I")
    serie = SerieNumerotation.objects.create(
        institution=institution, code="s", libelle_fr="S", gabarit="{AAAA}/{SEQ:4}"
    )
    nombre = 50
    depart = threading.Barrier(nombre)
    date = datetime.date(2026, 6, 1)

    def demander(_index):
        try:
            depart.wait(timeout=30)
            with transaction.atomic():
                return attribuer_numero(SerieNumerotation.objects.get(pk=serie.pk), date=date)
        finally:
            connections.close_all()

    with ThreadPoolExecutor(max_workers=nombre) as executeur:
        numeros = list(executeur.map(demander, range(nombre)))

    assert len(set(numeros)) == nombre
    assert sorted(numeros) == [f"2026/{i:04d}" for i in range(1, nombre + 1)]
    assert CompteurSerie.objects.get(serie=serie).valeur == nombre
