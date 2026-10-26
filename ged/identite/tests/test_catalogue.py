"""Matrice des rôles initiaux (document 03, tableau 3.5).

Les cases « O » (autorisé dans le périmètre) sont des permissions de rôle ; les
cases « P » (objets propres) sont les permissions suffixées « _propres » (lot 3).
Les cases « A » (objets affectés) relèvent des accès explicites (lot 7).
Cette matrice est écrite indépendamment du catalogue : toute divergence entre
le document et le code fait échouer le test.
"""

import pytest

from identite.models import Permission, Role

MATRICE = {
    "administrateur_fonctionnel": {
        "administration.institution",
        "administration.organisation",
        "administration.utilisateurs",
        "administration.roles",
        "administration.classement",
        "audit.consulter",
        "audit.exporter",
        "resultats.exporter",
    },
    "administrateur_unite": {"administration.organisation", "administration.utilisateurs"},
    "bureau_ordre": {
        "courrier.enregistrer",
        "document.creer",
        "document.consulter",
        "document.telecharger",
        "document.modifier_propres",
        "dossier.gerer",
        "transmission.emettre",
    },
    "producteur": {
        "document.creer",
        "document.consulter",
        "document.telecharger_propres",
        "document.modifier_propres",
        "document.versionner_propres",
        "document.confidentialite",
        "dossier.gerer",
        "transmission.emettre",
    },
    "traitant": {"document.creer"},
    "validateur": {
        "document.creer",
        "document.consulter",
        "document.telecharger",
        "document.modifier",
        "document.versionner",
        "document.confidentialite",
        "dossier.gerer",
        "dossier.rouvrir",
        "transmission.emettre",
        "resultats.exporter",
    },
    "archiviste": {
        "administration.classement",
        "document.consulter",
        "document.telecharger",
        "document.modifier",
        "document.confidentialite",
        "dossier.gerer",
        "dossier.rouvrir",
        "archives.gerer",
        "audit.consulter",
        "resultats.exporter",
    },
    "auditeur": {"audit.consulter", "audit.exporter", "document.consulter_metadonnees", "resultats.exporter"},
    "consultation": {"document.consulter"},
}
MFA_REQUIS = {"administrateur_fonctionnel", "administrateur_unite", "archiviste", "auditeur"}


@pytest.mark.django_db
def test_roles_initiaux_conformes_a_la_matrice(institution):
    roles = {role.code: role for role in Role.objects.filter(institution=institution)}
    assert set(roles) == set(MATRICE)
    for code, attendues in MATRICE.items():
        assert set(roles[code].permissions.values_list("code", flat=True)) == attendues, code
        assert roles[code].mfa_requis is (code in MFA_REQUIS), code
        assert roles[code].systeme


@pytest.mark.django_db
def test_aucun_role_d_administration_ne_donne_acces_au_contenu(institution):
    for code in ("administrateur_fonctionnel", "administrateur_unite", "auditeur"):
        permissions = set(
            Role.objects.get(institution=institution, code=code).permissions.values_list("code", flat=True)
        )
        assert not permissions & {"document.consulter", "document.telecharger"}, code


@pytest.mark.django_db
def test_catalogue_synchronise(institution):
    Permission.objects.create(code="obsolete.permission", groupe="x", description="x")
    from identite.catalogue import synchroniser_permissions

    synchroniser_permissions(Permission)
    assert not Permission.objects.get(code="obsolete.permission").actif
    assert Permission.objects.filter(actif=True).count() == 23


@pytest.mark.django_db
def test_referentiels_crees_avec_l_institution(institution, racine):
    assert racine.chemin == f"/{racine.pk}/"
    assert racine.type.code == "institution"
    assert institution.types_unite.count() == 7
