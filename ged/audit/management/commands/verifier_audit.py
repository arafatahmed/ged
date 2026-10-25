from django.core.management.base import BaseCommand, CommandError

from audit.services import journaliser, verifier_chaine


class Command(BaseCommand):
    help = "Vérifie l'intégrité de la chaîne du journal d'audit et ses scellements."

    def add_arguments(self, parser):
        parser.add_argument(
            "--scellements",
            help="Répertoire des copies exportées des scellements, à comparer avec la base.",
        )

    def handle(self, *args, **options):
        rapport = verifier_chaine(options.get("scellements"))
        journaliser(
            "audit.verification",
            acteur_libelle="systeme",
            resultat="succes" if rapport.integre else "erreur",
            details={"evenements": rapport.nombre, "anomalies": len(rapport.anomalies)},
        )
        if rapport.integre:
            self.stdout.write(self.style.SUCCESS(f"Chaîne intègre : {rapport.nombre} événements vérifiés."))
            return
        for identifiant, raison in rapport.anomalies:
            self.stderr.write(f"Événement {identifiant} : {raison}")
        raise CommandError(f"Chaîne d'audit altérée : {len(rapport.anomalies)} anomalie(s).")
