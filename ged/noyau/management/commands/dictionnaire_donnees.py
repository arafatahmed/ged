from pathlib import Path

from django.apps import apps
from django.core.management.base import BaseCommand, CommandError
from django.db import connection, models

APPLICATIONS = ["noyau", "organisation", "identite", "audit"]


def generer():
    lignes = [
        "# Dictionnaire de données de la GED",
        "",
        "Généré par `python manage.py dictionnaire_donnees` à partir des modèles ; ne pas modifier à la main.",
        "",
    ]
    for application in APPLICATIONS:
        for modele in sorted(apps.get_app_config(application).get_models(), key=lambda m: m._meta.db_table):
            meta = modele._meta
            lignes += [f"## `{meta.db_table}` ({meta.verbose_name})", ""]
            if modele.__doc__ and not modele.__doc__.startswith(f"{modele.__name__}("):
                lignes += [" ".join(modele.__doc__.split()), ""]
            lignes += ["| Colonne | Type | Nul | Unique | Référence | Description |", "|---|---|---|---|---|---|"]
            for champ in meta.concrete_fields:
                reference = ""
                if isinstance(champ, models.ForeignKey):
                    cible = champ.related_model._meta.db_table
                    reference = f"`{cible}` ({champ.remote_field.on_delete.__name__})"
                description = str(champ.verbose_name)
                if champ.help_text:
                    description += f" : {champ.help_text}"
                lignes.append(
                    f"| `{champ.column}` | {champ.db_type(connection)} | {'oui' if champ.null else 'non'} "
                    f"| {'oui' if champ.unique else ''} | {reference} | {description} |"
                )
            contraintes = [c.name for c in meta.constraints]
            if contraintes:
                lignes += ["", "Contraintes : " + ", ".join(f"`{c}`" for c in contraintes) + "."]
            lignes.append("")
    return "\n".join(lignes)


class Command(BaseCommand):
    help = "Génère le dictionnaire de données en Markdown, ou vérifie qu'il est à jour."

    def add_arguments(self, parser):
        parser.add_argument("chemin", help="Fichier Markdown à écrire ou à vérifier.")
        parser.add_argument("--verifier", action="store_true", help="Échoue si le fichier n'est pas à jour.")

    def handle(self, *args, **options):
        chemin = Path(options["chemin"])
        contenu = generer()
        if options["verifier"]:
            if not chemin.exists() or chemin.read_text(encoding="utf-8") != contenu:
                raise CommandError(f"{chemin} n'est pas à jour : relancez la commande sans --verifier.")
            self.stdout.write("Dictionnaire de données à jour.")
            return
        chemin.write_text(contenu, encoding="utf-8")
        self.stdout.write(self.style.SUCCESS(f"Dictionnaire écrit dans {chemin}."))
