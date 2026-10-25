import datetime

import pytest
from django.core.exceptions import PermissionDenied
from django.utils import timezone

from acces import moteur
from audit.models import JournalAudit
from identite.models import Delegation, Role, Utilisateur
from noyau.models import Institution


@pytest.fixture
def arbre(creer_unite):
    """racine ─ daf ─ compta ; racine ─ drh"""
    daf = creer_unite("daf")
    compta = creer_unite("compta", parent=daf, type_code="service")
    drh = creer_unite("drh")
    return {"daf": daf, "compta": compta, "drh": drh}


@pytest.mark.django_db
class TestPermissions:
    def test_sans_affectation_aucun_droit(self, agent, arbre):
        assert not moteur.a_permission(agent, "document.consulter")
        assert list(moteur.unites_autorisees(agent, "document.consulter")) == []

    def test_affectation_directe_limitee_a_l_unite(self, agent, arbre, affecter):
        affecter(agent, arbre["daf"], "consultation")
        assert moteur.a_permission(agent, "document.consulter", arbre["daf"])
        assert not moteur.a_permission(agent, "document.consulter", arbre["compta"])
        assert not moteur.a_permission(agent, "document.consulter", arbre["drh"])
        assert not moteur.a_permission(agent, "document.telecharger", arbre["daf"])
        assert set(moteur.unites_autorisees(agent, "document.consulter")) == {arbre["daf"]}

    def test_etendue_aux_sous_unites(self, agent, arbre, affecter):
        affecter(agent, arbre["daf"], "consultation", etendue=True)
        assert moteur.a_permission(agent, "document.consulter", arbre["compta"])
        assert not moteur.a_permission(agent, "document.consulter", arbre["drh"])
        assert set(moteur.unites_autorisees(agent, "document.consulter")) == {arbre["daf"], arbre["compta"]}
        assert moteur.couvre_sous_arbre(agent, "document.consulter", arbre["daf"])

    def test_prefixe_de_chemin_sans_confusion(self, agent, creer_unite, affecter, racine):
        # Unités d'identifiants 1x et 1xy : le chemin « /1/12/ » ne doit pas couvrir « /1/123/ ».
        unites = [creer_unite(f"u{i}") for i in range(12)]
        affecter(agent, unites[0], "consultation", etendue=True)
        for autre in unites[1:]:
            assert not moteur.a_permission(agent, "document.consulter", autre)

    @pytest.mark.parametrize(
        "debut, fin, attendu",
        [(-10, None, True), (-10, -1, False), (1, None, False), (-10, 0, True)],
    )
    def test_periode_de_l_affectation(self, agent, arbre, affecter, debut, fin, attendu):
        aujourd_hui = timezone.localdate()
        affecter(
            agent,
            arbre["daf"],
            "consultation",
            date_debut=aujourd_hui + datetime.timedelta(days=debut),
            date_fin=None if fin is None else aujourd_hui + datetime.timedelta(days=fin),
        )
        assert moteur.a_permission(agent, "document.consulter", arbre["daf"]) is attendu

    def test_role_ou_unite_desactives(self, agent, arbre, affecter):
        affectation = affecter(agent, arbre["daf"], "consultation")
        affectation.role.actif = False
        affectation.role.save()
        assert not moteur.a_permission(agent, "document.consulter", arbre["daf"])

    def test_compte_desactive(self, agent, arbre, affecter):
        affecter(agent, arbre["daf"], "consultation")
        agent.is_active = False
        assert not moteur.a_permission(agent, "document.consulter", arbre["daf"])

    def test_superadministrateur_technique_sans_droit_metier(self, superadmin, arbre):
        assert not moteur.a_permission(superadmin, "document.consulter")
        assert not moteur.a_permission(superadmin, "administration.utilisateurs")

    def test_isolation_entre_institutions(self, agent, arbre, affecter, settings):
        settings.GED_MULTI_INSTITUTIONS = True
        affecter(agent, arbre["daf"], "consultation")
        autre = Institution.objects.create(code="autre", nom_fr="Autre", sigle="AUT")
        arbre["daf"].institution = autre  # objet d'une autre institution présenté au moteur
        assert not moteur.a_permission(agent, "document.consulter", arbre["daf"])

    def test_portee_institution(self, agent, admin_fonctionnel, arbre, affecter):
        affecter(agent, arbre["daf"], "administrateur_unite", etendue=True)
        assert moteur.portee_institution(admin_fonctionnel, "administration.utilisateurs")
        assert not moteur.portee_institution(agent, "administration.utilisateurs")

    def test_filtrer_par_unite(self, agent, arbre, affecter):
        affecter(agent, arbre["daf"], "administrateur_unite", etendue=True)
        from organisation.models import Poste

        Poste.objects.create(institution=agent.institution, unite=arbre["compta"], intitule_fr="Comptable")
        Poste.objects.create(institution=agent.institution, unite=arbre["drh"], intitule_fr="Gestionnaire RH")
        postes = moteur.filtrer_par_unite(agent, Poste.objects.all(), "administration.organisation")
        assert [p.intitule_fr for p in postes] == ["Comptable"]

    def test_niveau_habilitation(self, creer_utilisateur):
        utilisateur = creer_utilisateur("confidentiel", niveau=2)
        assert moteur.niveau_suffisant(utilisateur, 2)
        assert not moteur.niveau_suffisant(utilisateur, 3)

    def test_refus_journalise(self, agent, arbre):
        with pytest.raises(PermissionDenied):
            moteur.exiger(agent, "document.consulter", arbre["daf"])
        refus = JournalAudit.objects.get(action="acces.refus")
        assert refus.resultat == "refus"
        assert refus.details["permission"] == "document.consulter"
        assert refus.acteur == agent


@pytest.mark.django_db
class TestDelegations:
    def _deleguer(self, delegant, delegataire, roles=(), debut=-1, fin=24):
        maintenant = timezone.now()
        delegation = Delegation.objects.create(
            delegant=delegant,
            delegataire=delegataire,
            creee_par=delegant,
            motif="congé",
            debut=maintenant + datetime.timedelta(hours=debut),
            fin=maintenant + datetime.timedelta(hours=fin),
        )
        delegation.roles.set(roles)
        return delegation

    def test_delegation_en_cours(self, agent, creer_utilisateur, arbre, affecter):
        chef = creer_utilisateur("chef")
        affecter(chef, arbre["daf"], "validateur")
        self._deleguer(chef, agent)
        assert moteur.a_permission(agent, "dossier.rouvrir", arbre["daf"])

    def test_delegation_sans_permission_d_administration(self, agent, creer_utilisateur, arbre, affecter):
        chef = creer_utilisateur("chef")
        affecter(chef, arbre["daf"], "administrateur_unite", etendue=True)
        affecter(chef, arbre["daf"], "validateur")
        self._deleguer(chef, agent)
        assert not moteur.a_permission(agent, "administration.utilisateurs", arbre["daf"])
        assert moteur.a_permission(agent, "transmission.emettre", arbre["daf"])

    def test_delegation_limitee_aux_roles_choisis(self, agent, creer_utilisateur, arbre, affecter, institution):
        chef = creer_utilisateur("chef")
        affecter(chef, arbre["daf"], "validateur")
        affecter(chef, arbre["drh"], "archiviste")
        self._deleguer(chef, agent, roles=[Role.objects.get(institution=institution, code="validateur")])
        assert moteur.a_permission(agent, "transmission.emettre", arbre["daf"])
        assert not moteur.a_permission(agent, "archives.gerer", arbre["drh"])

    @pytest.mark.parametrize("debut, fin", [(-48, -24), (24, 48)])
    def test_delegation_hors_periode(self, agent, creer_utilisateur, arbre, affecter, debut, fin):
        chef = creer_utilisateur("chef")
        affecter(chef, arbre["daf"], "validateur")
        self._deleguer(chef, agent, debut=debut, fin=fin)
        assert not moteur.a_permission(agent, "transmission.emettre", arbre["daf"])

    def test_delegation_revoquee_ou_delegant_desactive(self, agent, creer_utilisateur, arbre, affecter):
        chef = creer_utilisateur("chef")
        affecter(chef, arbre["daf"], "validateur")
        delegation = self._deleguer(chef, agent)
        Utilisateur.objects.filter(pk=chef.pk).update(is_active=False)
        assert not moteur.a_permission(agent, "transmission.emettre", arbre["daf"])
        Utilisateur.objects.filter(pk=chef.pk).update(is_active=True)
        moteur.oublier(agent)
        delegation.revoquee_le = timezone.now()
        delegation.save()
        assert not moteur.a_permission(agent, "transmission.emettre", arbre["daf"])
