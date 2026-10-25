import secrets

from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from audit.services import journaliser
from identite.models import Affectation, Role, Utilisateur
from noyau.models import Institution
from organisation.models import UniteOrganisationnelle


class Command(BaseCommand):
    help = (
        "Crée le premier administrateur fonctionnel d'une institution : rôle « administrateur_fonctionnel » "
        "sur l'unité racine, étendu à toute l'organisation. Un mot de passe temporaire est affiché une seule fois ; "
        "il devra être changé à la première connexion, puis la double authentification activée."
    )

    def add_arguments(self, parser):
        parser.add_argument("--institution", required=True, help="Code de l'institution.")
        parser.add_argument("--identifiant", required=True)
        parser.add_argument("--nom", required=True)
        parser.add_argument("--prenom", required=True)
        parser.add_argument("--courriel", default="")
        parser.add_argument(
            "--niveau",
            type=int,
            default=3,
            choices=[0, 1, 2, 3],
            help="Niveau d'habilitation (il borne les niveaux qu'il pourra attribuer).",
        )

    def handle(self, *args, **options):
        institution = Institution.objects.filter(code=options["institution"]).first()
        if institution is None:
            raise CommandError(f"Institution inconnue : {options['institution']}")
        racines = list(UniteOrganisationnelle.objects.filter(institution=institution, parent__isnull=True, actif=True))
        role = Role.objects.filter(institution=institution, code="administrateur_fonctionnel").first()
        if not racines or role is None:
            raise CommandError("Référentiels initiaux absents : relancez initialiser_ged.")
        mot_de_passe = secrets.token_urlsafe(12)
        utilisateur = Utilisateur(
            institution=institution,
            identifiant=options["identifiant"],
            nom=options["nom"],
            prenom=options["prenom"],
            courriel=options["courriel"],
            niveau_habilitation=options["niveau"],
            doit_changer_mot_de_passe=True,
        )
        try:
            utilisateur.full_clean(exclude=["password"])
            validate_password(mot_de_passe, utilisateur)
        except ValidationError as exc:
            raise CommandError("; ".join(exc.messages)) from exc
        utilisateur.set_password(mot_de_passe)
        with transaction.atomic():
            utilisateur.save()
            for racine in racines:
                Affectation.objects.create(utilisateur=utilisateur, unite=racine, role=role, etendue_sous_unites=True)
            journaliser(
                "utilisateur.creation",
                objet=utilisateur,
                acteur_libelle="systeme",
                details={"identifiant": utilisateur.identifiant, "role": role.code, "commande": "creer_administrateur"},
            )
        self.stdout.write(self.style.SUCCESS(f"Administrateur créé : {utilisateur.identifiant}"))
        self.stdout.write(f"Mot de passe temporaire (à changer à la première connexion) : {mot_de_passe}")
