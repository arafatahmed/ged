from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from audit.services import journaliser
from noyau.admin import AuditAdminMixin

from .forms import FormulaireCreationUtilisateur, FormulaireModificationUtilisateur
from .models import Utilisateur


@admin.register(Utilisateur)
class UtilisateurAdmin(AuditAdminMixin, UserAdmin):
    """Administration technique des comptes. L'administration fonctionnelle arrive au lot 2."""

    form = FormulaireModificationUtilisateur
    add_form = FormulaireCreationUtilisateur
    ordering = ["nom", "prenom"]
    list_display = ["identifiant", "nom", "prenom", "institution", "is_active", "is_staff"]
    list_filter = ["is_active", "is_staff", "is_superuser", "institution"]
    search_fields = ["identifiant", "nom", "prenom", "courriel"]
    readonly_fields = [
        "last_login",
        "date_creation",
        "echecs_connexion",
        "verrouille_jusqu_a",
        "mot_de_passe_modifie_le",
    ]
    fieldsets = [
        (None, {"fields": ["identifiant", "password"]}),
        ("Identité", {"fields": ["nom", "prenom", "nom_ar", "courriel", "langue"]}),
        ("Rattachement", {"fields": ["institution", "niveau_habilitation"]}),
        (
            "Sécurité",
            {
                "fields": [
                    "doit_changer_mot_de_passe",
                    "echecs_connexion",
                    "verrouille_jusqu_a",
                    "mot_de_passe_modifie_le",
                ]
            },
        ),
        ("Droits", {"fields": ["is_active", "is_staff", "is_superuser", "groups", "user_permissions"]}),
        ("Dates", {"fields": ["last_login", "date_creation"]}),
    ]
    add_fieldsets = [
        (None, {"fields": ["identifiant", "nom", "prenom", "institution", "password1", "password2"]}),
    ]
    champs_audit_masques = {"password"}

    def user_change_password(self, request, id, form_url=""):
        reponse = super().user_change_password(request, id, form_url)
        if request.method == "POST" and reponse.status_code == 302:
            journaliser(
                "utilisateur.mot_de_passe.modification",
                objet=self.get_object(request, id),
                requete=request,
            )
        return reponse
