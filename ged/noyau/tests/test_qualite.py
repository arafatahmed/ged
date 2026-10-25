"""Contrôles de qualité du dépôt : traductions et dictionnaire de données.

En intégration continue, `makemessages` est lancé avant les tests : tout
nouveau texte non traduit en arabe fait alors échouer `test_traduction_arabe_complete`.
"""

import ast
from pathlib import Path

from django.conf import settings
from django.core.management import call_command

CATALOGUE_AR = settings.BASE_DIR / "locale" / "ar" / "LC_MESSAGES" / "django.po"
DICTIONNAIRE = settings.BASE_DIR.parent / "docs" / "ged" / "dictionnaire-donnees.md"


def entrees_po(chemin):
    """Renvoie (msgid, [traductions], flou) pour chaque entrée, formes plurielles comprises."""
    blocs = Path(chemin).read_text(encoding="utf-8").strip().split("\n\n")
    for bloc in blocs[1:]:  # le premier bloc est l'en-tête
        flou = any(ligne.startswith("#,") and "fuzzy" in ligne for ligne in bloc.splitlines())
        parties = {}
        courante = None
        for ligne in bloc.splitlines():
            if ligne.startswith(("msgid", "msgstr")):
                courante, _espace, valeur = ligne.partition(" ")
                parties[courante] = ast.literal_eval(valeur)
            elif ligne.startswith('"') and courante:
                parties[courante] += ast.literal_eval(ligne)
        traductions = [v for cle, v in parties.items() if cle.startswith("msgstr")]
        yield parties.get("msgid", ""), traductions, flou


def test_traduction_arabe_complete():
    manquantes = [msgid for msgid, traductions, flou in entrees_po(CATALOGUE_AR) if not all(traductions) or flou]
    assert manquantes == []


def test_variables_conservees_dans_les_traductions():
    import re

    variable = re.compile(r"%\(\w+\)[sd]|\{\w+(?::n)?\}")
    for msgid, traductions, _flou in entrees_po(CATALOGUE_AR):
        for traduction in traductions:
            assert sorted(variable.findall(msgid)) == sorted(variable.findall(traduction)), msgid


def test_dictionnaire_de_donnees_a_jour(db):
    call_command("dictionnaire_donnees", str(DICTIONNAIRE), "--verifier")
