from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError

from noyau.models import Institution
from noyau.services import creer_institution


class Command(BaseCommand):
    help = (
        "Crée l'institution de l'installation (à lancer une fois après les migrations). Sans effet si elle existe déjà."
    )

    def add_arguments(self, parser):
        parser.add_argument("--code", required=True, help="Code court, par exemple « ministere-x ».")
        parser.add_argument("--nom-fr", required=True)
        parser.add_argument("--nom-ar", default="")
        parser.add_argument("--sigle", required=True)
        parser.add_argument("--fuseau", default="UTC", help="Fuseau IANA, par exemple Africa/Nouakchott.")
        parser.add_argument("--langue", default="fr", choices=["fr", "ar"])

    def handle(self, *args, **options):
        existante = Institution.objects.filter(code=options["code"]).first()
        if existante:
            self.stdout.write(f"L'institution {existante.code} existe déjà ; rien n'est modifié.")
            return
        try:
            institution = creer_institution(
                code=options["code"],
                nom_fr=options["nom_fr"],
                nom_ar=options["nom_ar"],
                sigle=options["sigle"],
                fuseau_horaire=options["fuseau"],
                langue_defaut=options["langue"],
            )
        except ValidationError as exc:
            raise CommandError("; ".join(exc.messages)) from exc
        self.stdout.write(self.style.SUCCESS(f"Institution créée : {institution.nom_fr} ({institution.code})."))
