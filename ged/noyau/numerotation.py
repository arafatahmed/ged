"""Gabarits de référence des séries de numérotation.

Un gabarit est un texte contenant des jetons entre accolades, par exemple
`{SIGLE}/{UNITE}/{AAAA}/{SEQ:5}` qui produit `MIN/DAF/2026/00042`.

Jetons reconnus :
- `{SEQ:n}` : numéro d'ordre complété par des zéros sur n chiffres (obligatoire, une seule fois) ;
- `{AAAA}`, `{AA}`, `{MM}` : année sur 4 ou 2 chiffres, mois ;
- `{SIGLE}` : sigle de l'institution ;
- `{UNITE}` : code de l'unité concernée ;
- `{CATEGORIE}` : code de la catégorie concernée.
"""

import re

from django.core.exceptions import ValidationError
from django.utils.translation import gettext as _

JETON = re.compile(r"\{([A-Z]+)(?::(\d+))?\}")
JETONS_SIMPLES = {"AAAA", "AA", "MM", "SIGLE", "UNITE", "CATEGORIE"}
CODE_CONTEXTE = re.compile(r"^[A-Za-z0-9_-]{1,30}$")
LONGUEUR_SEQ_MAX = 12


def analyser_gabarit(gabarit, *, par_annee=False, par_unite=False, par_categorie=False):
    """Vérifie un gabarit et sa cohérence avec la portée des compteurs.

    Si le compteur repart à zéro par année, par unité ou par catégorie, la
    dimension correspondante doit figurer dans le gabarit, sinon deux objets
    différents recevraient la même référence.
    """
    erreurs = []
    jetons = JETON.findall(gabarit)
    reste = JETON.sub("", gabarit)
    if "{" in reste or "}" in reste:
        erreurs.append(_("Accolade isolée ou jeton mal formé dans le gabarit."))
    noms = [nom for nom, _longueur in jetons]
    for nom, longueur in jetons:
        if nom == "SEQ":
            if not longueur or not 1 <= int(longueur) <= LONGUEUR_SEQ_MAX:
                erreurs.append(_("Le jeton {SEQ:n} exige une longueur entre 1 et %(max)d.") % {"max": LONGUEUR_SEQ_MAX})
        elif nom not in JETONS_SIMPLES or longueur:
            erreurs.append(_("Jeton inconnu : %(jeton)s.") % {"jeton": nom})
    if noms.count("SEQ") != 1:
        erreurs.append(_("Le gabarit doit contenir exactement un jeton {SEQ:n}."))
    if par_annee and not ({"AAAA", "AA"} & set(noms)):
        erreurs.append(_("Une numérotation annuelle exige {AAAA} ou {AA} dans le gabarit."))
    if par_unite and "UNITE" not in noms:
        erreurs.append(_("Une numérotation par unité exige {UNITE} dans le gabarit."))
    if par_categorie and "CATEGORIE" not in noms:
        erreurs.append(_("Une numérotation par catégorie exige {CATEGORIE} dans le gabarit."))
    if erreurs:
        raise ValidationError(erreurs)


def verifier_code_contexte(valeur, libelle):
    if not CODE_CONTEXTE.match(valeur or ""):
        raise ValidationError(
            _("Code %(libelle)s invalide : lettres, chiffres, tiret ou souligné, 30 caractères au plus.")
            % {"libelle": libelle}
        )


def formater(gabarit, *, sequence, date, sigle="", unite="", categorie=""):
    valeurs = {
        "AAAA": f"{date.year:04d}",
        "AA": f"{date.year % 100:02d}",
        "MM": f"{date.month:02d}",
        "SIGLE": sigle,
        "UNITE": unite,
        "CATEGORIE": categorie,
    }

    def remplacer(correspondance):
        nom, longueur = correspondance.groups()
        if nom == "SEQ":
            return str(sequence).zfill(int(longueur))
        return valeurs[nom]

    return JETON.sub(remplacer, gabarit)
