import datetime

from django.core.management.base import BaseCommand, CommandError
from django.db import IntegrityError
from django.utils import timezone

from audit.services import sceller


class Command(BaseCommand):
    help = (
        "Scelle le journal d'audit à la fin d'une journée (par défaut la veille) et exporte "
        "l'empreinte dans GED_AUDIT_SCELLEMENT_DIR. À planifier chaque nuit."
    )

    def add_arguments(self, parser):
        parser.add_argument("--date", help="Journée à sceller, au format AAAA-MM-JJ.")
        parser.add_argument("--repertoire", help="Répertoire d'export (remplace GED_AUDIT_SCELLEMENT_DIR).")

    def handle(self, *args, **options):
        if options["date"]:
            date = datetime.date.fromisoformat(options["date"])
        else:
            date = timezone.localdate() - datetime.timedelta(days=1)
        try:
            scellement = sceller(date, options.get("repertoire"))
        except IntegrityError as exc:
            raise CommandError(f"La journée {date} est déjà scellée.") from exc
        if scellement is None:
            self.stdout.write(f"Aucun événement à sceller pour le {date}.")
        else:
            self.stdout.write(
                self.style.SUCCESS(
                    f"Journée {date} scellée : événement {scellement.dernier_id}, {scellement.empreinte}."
                )
            )
