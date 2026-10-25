"""Catalogue des paramètres fonctionnels admis pour une institution.

Une clé absente de ce catalogue est refusée : l'application doit savoir ce
qu'elle sait interpréter. Les valeurs sont stockées dans ParametreInstitution.
"""

from dataclasses import dataclass
from typing import Any

from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _


def entier_entre(minimum, maximum):
    def valider(valeur):
        if isinstance(valeur, bool) or not isinstance(valeur, int) or not minimum <= valeur <= maximum:
            raise ValidationError(
                _("Entier attendu entre %(min)d et %(max)d."), params={"min": minimum, "max": maximum}
            )

    return valider


def parmi(*valeurs):
    def valider(valeur):
        if valeur not in valeurs:
            raise ValidationError(_("Valeur attendue parmi : %(valeurs)s."), params={"valeurs": ", ".join(valeurs)})

    return valider


@dataclass(frozen=True)
class DefinitionParametre:
    cle: str
    defaut: Any
    description: str
    valider: Any


CATALOGUE = {
    d.cle: d
    for d in [
        DefinitionParametre(
            "session.inactivite_minutes",
            30,
            _("Durée d'inactivité avant déconnexion, en minutes."),
            entier_entre(5, 480),
        ),
        DefinitionParametre(
            "fichiers.taille_max_mo",
            100,
            _("Taille maximale d'un fichier envoyé, en mégaoctets."),
            entier_entre(1, 2048),
        ),
        DefinitionParametre(
            "traitement.alerte_jours_avant_echeance",
            2,
            _("Nombre de jours avant l'échéance où le titulaire d'une tâche est alerté."),
            entier_entre(0, 30),
        ),
        DefinitionParametre(
            "connexion.seuil_verrouillage",
            10,
            _("Nombre d'échecs de connexion consécutifs qui verrouillent un compte."),
            entier_entre(3, 50),
        ),
        DefinitionParametre(
            "connexion.duree_verrouillage_minutes",
            30,
            _("Durée du verrouillage d'un compte après trop d'échecs, en minutes."),
            entier_entre(1, 1440),
        ),
        DefinitionParametre(
            "delegation.duree_max_jours",
            90,
            _("Durée maximale d'une délégation, en jours."),
            entier_entre(1, 365),
        ),
        DefinitionParametre(
            "interface.chiffres",
            "occidentaux",
            _("Chiffres affichés en arabe : occidentaux (0-9) ou orientaux."),
            parmi("occidentaux", "orientaux"),
        ),
    ]
}
