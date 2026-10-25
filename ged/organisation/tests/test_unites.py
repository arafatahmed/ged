import pytest
from django.core.exceptions import PermissionDenied, ValidationError

from audit.models import JournalAudit
from organisation import services
from organisation.models import Poste, TypeUnite, UniteOrganisationnelle


def type_unite(institution, code="direction"):
    return TypeUnite.objects.get(institution=institution, code=code)


@pytest.mark.django_db
class TestArbre:
    def test_creation_et_chemin(self, admin_fonctionnel, racine, institution):
        daf = services.creer_unite(
            admin_fonctionnel, parent=racine, type=type_unite(institution), code="daf", libelle_fr="DAF"
        )
        compta = services.creer_unite(
            admin_fonctionnel, parent=daf, type=type_unite(institution, "service"), code="compta", libelle_fr="Compta"
        )
        assert compta.chemin == f"/{racine.pk}/{daf.pk}/{compta.pk}/"
        assert compta.profondeur == 2
        assert compta.ids_ancetres == [racine.pk, daf.pk, compta.pk]
        assert JournalAudit.objects.filter(action="unite.creation", objet_id=str(compta.uuid)).exists()

    def test_deplacement_du_sous_arbre(self, admin_fonctionnel, creer_unite):
        daf = creer_unite("daf")
        compta = creer_unite("compta", parent=daf)
        paie = creer_unite("paie", parent=compta)
        drh = creer_unite("drh")
        services.modifier_unite(admin_fonctionnel, compta, parent=drh)
        paie.refresh_from_db()
        assert paie.chemin == f"{drh.chemin}{compta.pk}/{paie.pk}/"
        assert UniteOrganisationnelle.objects.filter(chemin__startswith=daf.chemin).count() == 1

    def test_une_seule_racine(self, admin_fonctionnel, racine, institution, creer_unite):
        with pytest.raises(ValidationError, match="parente"):
            services.creer_unite(
                admin_fonctionnel, parent=None, type=type_unite(institution), code="r2", libelle_fr="R"
            )
        daf = creer_unite("daf")
        with pytest.raises(ValidationError, match="parente"):
            services.modifier_unite(admin_fonctionnel, daf, parent=None)
        with pytest.raises(ValidationError, match="racine"):
            services.modifier_unite(admin_fonctionnel, racine, parent=daf)

    def test_cycle_refuse(self, admin_fonctionnel, creer_unite):
        daf = creer_unite("daf")
        compta = creer_unite("compta", parent=daf)
        with pytest.raises(ValidationError, match="sous-unités"):
            services.modifier_unite(admin_fonctionnel, daf, parent=compta)

    def test_code_unique(self, admin_fonctionnel, racine, institution, creer_unite):
        creer_unite("daf")
        with pytest.raises(ValidationError):
            services.creer_unite(
                admin_fonctionnel, parent=racine, type=type_unite(institution), code="daf", libelle_fr="X"
            )

    def test_desactivation_bloquee_si_l_unite_est_utilisee(self, admin_fonctionnel, creer_unite, agent, affecter):
        daf = creer_unite("daf")
        compta = creer_unite("compta", parent=daf)
        affectation = affecter(agent, compta, "consultation")
        with pytest.raises(ValidationError):
            services.desactiver_unite(admin_fonctionnel, daf)
        with pytest.raises(ValidationError, match="affectations"):
            services.desactiver_unite(admin_fonctionnel, compta)
        affectation.delete()
        services.desactiver_unite(admin_fonctionnel, compta)
        services.desactiver_unite(admin_fonctionnel, daf)
        assert not UniteOrganisationnelle.objects.get(pk=daf.pk).actif

    def test_administrateur_d_unite_limite_a_son_sous_arbre(
        self, creer_utilisateur, affecter, creer_unite, institution
    ):
        daf = creer_unite("daf")
        drh = creer_unite("drh")
        admin = creer_utilisateur("admin.daf")
        affecter(admin, daf, "administrateur_unite", etendue=True)
        services.creer_unite(admin, parent=daf, type=type_unite(institution, "service"), code="compta", libelle_fr="C")
        with pytest.raises(PermissionDenied):
            services.creer_unite(
                admin, parent=drh, type=type_unite(institution, "service"), code="paie", libelle_fr="P"
            )
        with pytest.raises(ValidationError, match="parente"):
            services.creer_unite(admin, parent=None, type=type_unite(institution), code="racine2", libelle_fr="R")
        with pytest.raises(PermissionDenied):
            services.modifier_unite(admin, daf, parent=drh)
        with pytest.raises(PermissionDenied):
            services.enregistrer_type_unite(admin, TypeUnite(code="antenne", libelle_fr="Antenne"))


@pytest.mark.django_db
class TestPostes:
    def test_hierarchie_sans_boucle(self, admin_fonctionnel, creer_unite, institution):
        daf = creer_unite("daf")
        directeur = services.enregistrer_poste(admin_fonctionnel, Poste(unite=daf, intitule_fr="Directeur"))
        chef = services.enregistrer_poste(admin_fonctionnel, Poste(unite=daf, intitule_fr="Chef", superieur=directeur))
        directeur.superieur = chef
        with pytest.raises(ValidationError, match="boucle"):
            services.enregistrer_poste(admin_fonctionnel, directeur)

    def test_type_d_unite(self, admin_fonctionnel, institution):
        nouveau = services.enregistrer_type_unite(admin_fonctionnel, TypeUnite(code="antenne", libelle_fr="Antenne"))
        assert nouveau.institution == institution
        assert JournalAudit.objects.filter(action="typeunite.creation").exists()
