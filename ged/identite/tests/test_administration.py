import datetime

import pytest
from django.contrib.sessions.models import Session
from django.core.exceptions import PermissionDenied, ValidationError
from django.test import Client
from django.utils import timezone

from audit.models import JournalAudit
from conftest import connecter_api
from identite import services
from identite.models import Affectation, Permission, Role, SessionUtilisateur

MDP_TEMPORAIRE = "temporaire-robuste-2026"


@pytest.fixture
def arbre(creer_unite):
    daf = creer_unite("daf")
    return {"daf": daf, "compta": creer_unite("compta", parent=daf, type_code="service"), "drh": creer_unite("drh")}


@pytest.fixture
def admin_daf(creer_utilisateur, affecter, arbre):
    """Administrateur d'unité de la DAF (sous-unités comprises), niveau 1."""
    utilisateur = creer_utilisateur("admin.daf", niveau=1)
    affecter(utilisateur, arbre["daf"], "administrateur_unite", etendue=True)
    return utilisateur


def role(institution, code):
    return Role.objects.get(institution=institution, code=code)


@pytest.mark.django_db
class TestComptes:
    def test_creation_par_l_administrateur_fonctionnel(self, admin_fonctionnel):
        utilisateur = services.creer_utilisateur(
            admin_fonctionnel,
            mot_de_passe_temporaire=MDP_TEMPORAIRE,
            identifiant="moussa.ba",
            nom="Ba",
            prenom="Moussa",
        )
        assert utilisateur.doit_changer_mot_de_passe
        assert utilisateur.institution == admin_fonctionnel.institution
        evenement = JournalAudit.objects.get(action="utilisateur.creation", objet_id=str(utilisateur.uuid))
        assert MDP_TEMPORAIRE not in str(evenement.details)

    def test_mot_de_passe_temporaire_faible_refuse(self, admin_fonctionnel):
        with pytest.raises(ValidationError):
            services.creer_utilisateur(
                admin_fonctionnel, mot_de_passe_temporaire="123", identifiant="x", nom="X", prenom="Y"
            )

    def test_agent_sans_droit(self, agent):
        with pytest.raises(PermissionDenied):
            services.creer_utilisateur(
                agent, mot_de_passe_temporaire=MDP_TEMPORAIRE, identifiant="x", nom="X", prenom="Y"
            )
        assert JournalAudit.objects.filter(action="acces.refus", acteur=agent).exists()

    def test_administrateur_d_unite_doit_affecter_dans_son_perimetre(self, admin_daf, arbre, institution):
        with pytest.raises(ValidationError):
            services.creer_utilisateur(
                admin_daf, mot_de_passe_temporaire=MDP_TEMPORAIRE, identifiant="x", nom="X", prenom="Y"
            )
        with pytest.raises(PermissionDenied):
            services.creer_utilisateur(
                admin_daf,
                mot_de_passe_temporaire=MDP_TEMPORAIRE,
                identifiant="x",
                nom="X",
                prenom="Y",
                affectation={"unite": arbre["drh"], "role": role(institution, "bureau_ordre")},
            )
        utilisateur = services.creer_utilisateur(
            admin_daf,
            mot_de_passe_temporaire=MDP_TEMPORAIRE,
            identifiant="x",
            nom="X",
            prenom="Y",
            affectation={"unite": arbre["compta"], "role": role(institution, "bureau_ordre")},
        )
        assert utilisateur.affectations.get().unite == arbre["compta"]

    def test_niveau_superieur_au_sien_refuse(self, admin_daf, arbre, institution):
        with pytest.raises(ValidationError, match="supérieur"):
            services.creer_utilisateur(
                admin_daf,
                mot_de_passe_temporaire=MDP_TEMPORAIRE,
                identifiant="x",
                nom="X",
                prenom="Y",
                niveau_habilitation=2,
                affectation={"unite": arbre["daf"], "role": role(institution, "consultation")},
            )

    def test_perimetre_de_l_administrateur_d_unite(self, admin_daf, creer_utilisateur, affecter, arbre):
        dans = creer_utilisateur("dans")
        affecter(dans, arbre["compta"], "consultation")
        a_cheval = creer_utilisateur("a.cheval")
        affecter(a_cheval, arbre["daf"], "consultation")
        affecter(a_cheval, arbre["drh"], "consultation")
        sans = creer_utilisateur("sans.affectation")
        geres = set(services.utilisateurs_geres(admin_daf))
        assert dans in geres
        assert a_cheval not in geres  # une de ses affectations est hors périmètre
        assert sans not in geres
        assert admin_daf not in geres
        with pytest.raises(PermissionDenied):
            services.desactiver_utilisateur(admin_daf, a_cheval, motif="test")

    def test_l_administrateur_fonctionnel_gere_tout_le_monde_sauf_lui(self, admin_fonctionnel, agent, superadmin):
        geres = set(services.utilisateurs_geres(admin_fonctionnel))
        assert agent in geres
        assert admin_fonctionnel not in geres
        assert superadmin not in geres

    def test_modification_de_son_propre_compte_refusee(self, admin_fonctionnel):
        with pytest.raises(PermissionDenied):
            services.modifier_utilisateur(admin_fonctionnel, admin_fonctionnel, niveau_habilitation=3)

    def test_desactivation_ferme_les_sessions_immediatement(self, admin_fonctionnel, agent):
        client = Client()
        connecter_api(client, "agent")
        assert client.get("/api/v1/compte/").status_code == 200
        assert SessionUtilisateur.objects.filter(utilisateur=agent, fin__isnull=True).exists()

        services.desactiver_utilisateur(admin_fonctionnel, agent, motif="départ")

        assert client.get("/api/v1/compte/").status_code == 403
        assert not SessionUtilisateur.objects.filter(utilisateur=agent, fin__isnull=True).exists()
        session = SessionUtilisateur.objects.filter(utilisateur=agent).first()
        assert session.motif_fin == "desactivation"
        assert not Session.objects.filter(session_key=session.cle_session).exists()
        assert JournalAudit.objects.filter(action="utilisateur.desactivation").exists()

    def test_reactivation(self, admin_fonctionnel, agent):
        services.desactiver_utilisateur(admin_fonctionnel, agent, motif="test")
        services.reactiver_utilisateur(admin_fonctionnel, agent)
        agent.refresh_from_db()
        assert agent.is_active

    def test_reinitialisation_du_mot_de_passe(self, admin_fonctionnel, agent):
        services.reinitialiser_mot_de_passe(admin_fonctionnel, agent, MDP_TEMPORAIRE)
        agent.refresh_from_db()
        assert agent.check_password(MDP_TEMPORAIRE)
        assert agent.doit_changer_mot_de_passe

    def test_deverrouillage(self, admin_fonctionnel, agent):
        agent.echecs_connexion = 10
        agent.verrouille_jusqu_a = timezone.now() + datetime.timedelta(minutes=30)
        agent.save()
        services.deverrouiller(admin_fonctionnel, agent)
        agent.refresh_from_db()
        assert not agent.est_verrouille() and agent.echecs_connexion == 0


@pytest.mark.django_db
class TestAffectations:
    def test_auto_affectation_refusee(self, admin_fonctionnel, racine, institution):
        with pytest.raises(PermissionDenied):
            services.creer_affectation(
                admin_fonctionnel, admin_fonctionnel, unite=racine, role=role(institution, "validateur")
            )
        assert JournalAudit.objects.filter(action="acces.refus", details__operation="auto_affectation").exists()

    def test_affectation_par_l_administrateur_fonctionnel(self, admin_fonctionnel, agent, arbre, institution):
        affectation = services.creer_affectation(
            admin_fonctionnel, agent, unite=arbre["daf"], role=role(institution, "validateur"), etendue_sous_unites=True
        )
        assert affectation.attribuee_par == admin_fonctionnel
        assert JournalAudit.objects.filter(action="affectation.creation", objet_id=str(affectation.uuid)).exists()

    def test_hors_perimetre_refuse(self, admin_daf, agent, arbre, institution):
        with pytest.raises(PermissionDenied):
            services.creer_affectation(admin_daf, agent, unite=arbre["drh"], role=role(institution, "consultation"))

    def test_escalade_par_role_d_administration_refusee(self, admin_daf, agent, arbre, institution):
        # L'administrateur d'unité ne détient pas administration.roles : il ne peut pas l'attribuer.
        with pytest.raises(PermissionDenied):
            services.creer_affectation(
                admin_daf, agent, unite=arbre["compta"], role=role(institution, "administrateur_fonctionnel")
            )
        # Il peut en revanche attribuer son propre rôle dans son périmètre.
        services.creer_affectation(
            admin_daf, agent, unite=arbre["compta"], role=role(institution, "administrateur_unite")
        )

    def test_etendue_plus_large_que_son_droit_refusee(self, creer_utilisateur, affecter, agent, arbre, institution):
        admin_sans_etendue = creer_utilisateur("admin.local")
        affecter(admin_sans_etendue, arbre["daf"], "administrateur_unite", etendue=False)
        with pytest.raises(PermissionDenied):
            services.creer_affectation(
                admin_sans_etendue,
                agent,
                unite=arbre["daf"],
                role=role(institution, "consultation"),
                etendue_sous_unites=True,
            )
        services.creer_affectation(
            admin_sans_etendue, agent, unite=arbre["daf"], role=role(institution, "consultation")
        )

    def test_poste_d_une_autre_unite_refuse(self, admin_fonctionnel, agent, arbre, institution):
        from organisation.models import Poste

        poste = Poste.objects.create(institution=institution, unite=arbre["drh"], intitule_fr="Chef")
        with pytest.raises(ValidationError):
            services.creer_affectation(
                admin_fonctionnel, agent, unite=arbre["daf"], role=role(institution, "consultation"), poste=poste
            )

    def test_cloture(self, admin_fonctionnel, agent, arbre, affecter):
        affectation = affecter(
            agent, arbre["daf"], "consultation", date_debut=timezone.localdate() - datetime.timedelta(days=5)
        )
        services.cloturer_affectation(admin_fonctionnel, affectation)
        assert (
            not Affectation.objects.actives(timezone.localdate() + datetime.timedelta(days=1))
            .filter(pk=affectation.pk)
            .exists()
        )
        with pytest.raises(ValidationError):
            services.cloturer_affectation(admin_fonctionnel, affectation)


@pytest.mark.django_db
class TestRoles:
    def test_creation_d_un_role(self, admin_fonctionnel, institution):
        nouveau = services.enregistrer_role(
            admin_fonctionnel,
            Role(code="secretaire", libelle_fr="Secrétaire"),
            Permission.objects.filter(code__in=["courrier.enregistrer", "document.creer"]),
        )
        assert set(nouveau.permissions.values_list("code", flat=True)) == {"courrier.enregistrer", "document.creer"}
        evenement = JournalAudit.objects.get(action="role.creation")
        assert evenement.details["permissions_ajoutees"] == ["courrier.enregistrer", "document.creer"]

    def test_modifier_un_role_que_l_on_detient_refuse(self, admin_fonctionnel, institution):
        propre = role(institution, "administrateur_fonctionnel")
        with pytest.raises(PermissionDenied):
            services.enregistrer_role(
                admin_fonctionnel,
                propre,
                list(propre.permissions.all()) + [Permission.objects.get(code="document.consulter")],
            )

    def test_administrateur_d_unite_ne_gere_pas_les_roles(self, creer_utilisateur, affecter, racine):
        admin = creer_utilisateur("admin.unite")
        affecter(admin, racine, "administrateur_unite", etendue=True)
        with pytest.raises(PermissionDenied):
            services.enregistrer_role(admin, Role(code="x", libelle_fr="X"), [])


@pytest.mark.django_db
class TestDelegations:
    def _periode(self, jours=7):
        debut = timezone.now()
        return debut, debut + datetime.timedelta(days=jours)

    def test_delegation_par_le_delegant(self, creer_utilisateur, affecter, agent, arbre):
        chef = creer_utilisateur("chef")
        affecter(chef, arbre["daf"], "validateur")
        debut, fin = self._periode()
        delegation = services.creer_delegation(
            chef, delegant=chef, delegataire=agent, debut=debut, fin=fin, motif="Mission"
        )
        assert JournalAudit.objects.filter(action="delegation.creation", objet_id=str(delegation.uuid)).exists()
        services.revoquer_delegation(agent, delegation)
        delegation.refresh_from_db()
        assert delegation.revoquee_par == agent

    def test_duree_maximale(self, creer_utilisateur, agent):
        chef = creer_utilisateur("chef")
        debut, fin = self._periode(jours=120)
        with pytest.raises(ValidationError, match="90"):
            services.creer_delegation(chef, delegant=chef, delegataire=agent, debut=debut, fin=fin, motif="x")

    def test_role_non_detenu_refuse(self, creer_utilisateur, agent, institution):
        chef = creer_utilisateur("chef")
        debut, fin = self._periode()
        with pytest.raises(ValidationError):
            services.creer_delegation(
                chef,
                delegant=chef,
                delegataire=agent,
                debut=debut,
                fin=fin,
                motif="x",
                roles=[role(institution, "archiviste")],
            )

    def test_delegation_pour_autrui_exige_l_administration(self, creer_utilisateur, agent):
        chef = creer_utilisateur("chef")
        debut, fin = self._periode()
        with pytest.raises(PermissionDenied):
            services.creer_delegation(agent, delegant=chef, delegataire=agent, debut=debut, fin=fin, motif="x")
