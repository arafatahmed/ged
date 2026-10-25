"""Catalogue des permissions et rôles initiaux.

Les permissions sont des codes stables définis ici : l'application doit savoir
ce qu'elle contrôle. Les rôles qui les regroupent sont des données propres à
chaque institution ; ceux ci-dessous sont créés à l'installation comme modèle
(document 03 du cadrage) et restent modifiables.

Les fonctions acceptent les classes de modèles en paramètre pour pouvoir être
appelées depuis une migration (modèles historiques).
"""

from django.utils.translation import gettext_lazy as _

# Les permissions « administration.* » ne peuvent être ni déléguées, ni attribuées
# par quelqu'un qui ne les détient pas lui-même (règle anti-escalade).
PREFIXE_ADMINISTRATION = "administration."

PERMISSIONS = [
    # (code, groupe, description)
    ("administration.institution", _("Administration"), _("Paramètres de l'institution, types de documents, circuits")),
    ("administration.organisation", _("Administration"), _("Unités organisationnelles et postes")),
    ("administration.utilisateurs", _("Administration"), _("Comptes utilisateurs, affectations et délégations")),
    ("administration.roles", _("Administration"), _("Rôles et permissions")),
    ("administration.classement", _("Administration"), _("Plan de classement et règles de conservation")),
    ("audit.consulter", _("Audit"), _("Consulter le journal d'audit et le journal des connexions")),
    ("audit.exporter", _("Audit"), _("Exporter le journal d'audit")),
    ("courrier.enregistrer", _("Courrier"), _("Enregistrer un courrier entrant ou sortant")),
    ("document.creer", _("Documents"), _("Créer un document")),
    ("document.consulter", _("Documents"), _("Consulter les documents et leur contenu")),
    ("document.consulter_metadonnees", _("Documents"), _("Consulter les fiches descriptives sans le contenu")),
    ("document.telecharger", _("Documents"), _("Télécharger le fichier original")),
    ("document.modifier", _("Documents"), _("Modifier les métadonnées")),
    ("document.versionner", _("Documents"), _("Ajouter une version")),
    ("document.confidentialite", _("Documents"), _("Changer le niveau de confidentialité")),
    ("dossier.gerer", _("Dossiers"), _("Créer, alimenter et clôturer un dossier")),
    ("dossier.rouvrir", _("Dossiers"), _("Rouvrir un dossier clos")),
    ("transmission.emettre", _("Circuits"), _("Transmettre et affecter")),
    ("archives.gerer", _("Archives"), _("Gel, versement et élimination")),
    ("resultats.exporter", _("Recherche"), _("Exporter des résultats de recherche")),
]

CODES = {code for code, _groupe, _description in PERMISSIONS}

ROLES_INITIAUX = [
    {
        "code": "administrateur_fonctionnel",
        "libelle_fr": "Administrateur fonctionnel",
        "libelle_ar": "المدير الوظيفي",
        "mfa_requis": True,
        "permissions": [
            "administration.institution",
            "administration.organisation",
            "administration.utilisateurs",
            "administration.roles",
            "administration.classement",
            "audit.consulter",
            "audit.exporter",
            "resultats.exporter",
        ],
    },
    {
        "code": "administrateur_unite",
        "libelle_fr": "Administrateur d'unité",
        "libelle_ar": "مدير الوحدة",
        "mfa_requis": True,
        "permissions": ["administration.organisation", "administration.utilisateurs"],
    },
    {
        "code": "bureau_ordre",
        "libelle_fr": "Agent du bureau d'ordre",
        "libelle_ar": "عون مكتب الضبط",
        "mfa_requis": False,
        "permissions": [
            "courrier.enregistrer",
            "document.creer",
            "document.consulter",
            "document.telecharger",
            "document.modifier",
            "dossier.gerer",
            "transmission.emettre",
        ],
    },
    {
        "code": "producteur",
        "libelle_fr": "Agent producteur",
        "libelle_ar": "عون منتج للوثائق",
        "mfa_requis": False,
        "permissions": [
            "document.creer",
            "document.consulter",
            "document.telecharger",
            "document.modifier",
            "document.versionner",
            "document.confidentialite",
            "dossier.gerer",
            "transmission.emettre",
        ],
    },
    {
        "code": "traitant",
        "libelle_fr": "Agent traitant",
        "libelle_ar": "عون معالج",
        "mfa_requis": False,
        "permissions": ["document.creer"],
    },
    {
        "code": "validateur",
        "libelle_fr": "Responsable et validateur",
        "libelle_ar": "مسؤول ومصادق",
        "mfa_requis": False,
        "permissions": [
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
        ],
    },
    {
        "code": "archiviste",
        "libelle_fr": "Archiviste",
        "libelle_ar": "أمين الأرشيف",
        "mfa_requis": True,
        "permissions": [
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
        ],
    },
    {
        "code": "auditeur",
        "libelle_fr": "Auditeur ou contrôleur",
        "libelle_ar": "مدقق أو مراقب",
        "mfa_requis": True,
        "permissions": ["audit.consulter", "audit.exporter", "document.consulter_metadonnees", "resultats.exporter"],
    },
    {
        "code": "consultation",
        "libelle_fr": "Consultation seule",
        "libelle_ar": "اطلاع فقط",
        "mfa_requis": False,
        "permissions": ["document.consulter"],
    },
]

TYPES_UNITE_INITIAUX = [
    ("institution", "Institution", "المؤسسة"),
    ("direction-generale", "Direction générale", "مديرية عامة"),
    ("direction", "Direction", "مديرية"),
    ("departement", "Département", "قسم"),
    ("service", "Service", "مصلحة"),
    ("bureau", "Bureau", "مكتب"),
    ("agence", "Agence", "وكالة"),
]


def synchroniser_permissions(Permission):
    """Crée ou met à jour les permissions du catalogue ; désactive celles qui n'y sont plus."""
    for code, groupe, description in PERMISSIONS:
        Permission.objects.update_or_create(
            code=code, defaults={"groupe": str(groupe), "description": str(description), "actif": True}
        )
    Permission.objects.exclude(code__in=CODES).update(actif=False)


def creer_referentiels_initiaux(institution, Role, Permission, TypeUnite):
    """Rôles et types d'unité initiaux d'une institution (sans effet s'ils existent déjà)."""
    synchroniser_permissions(Permission)
    for ordre, (code, libelle_fr, libelle_ar) in enumerate(TYPES_UNITE_INITIAUX):
        TypeUnite.objects.get_or_create(
            institution=institution,
            code=code,
            defaults={"libelle_fr": libelle_fr, "libelle_ar": libelle_ar, "ordre": ordre},
        )
    for definition in ROLES_INITIAUX:
        role, cree = Role.objects.get_or_create(
            institution=institution,
            code=definition["code"],
            defaults={
                "libelle_fr": definition["libelle_fr"],
                "libelle_ar": definition["libelle_ar"],
                "mfa_requis": definition["mfa_requis"],
                "systeme": True,
            },
        )
        if cree:
            role.permissions.set(Permission.objects.filter(code__in=definition["permissions"]))
