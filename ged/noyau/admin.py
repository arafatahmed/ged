from django.contrib import admin
from django.db import models, transaction

from audit.services import journaliser

from .models import CompteurSerie, Institution, ParametreInstitution, SerieNumerotation


class AuditAdminMixin:
    """Journalise chaque création ou modification faite depuis l'administration technique.

    Aucune suppression n'est possible depuis l'administration : les objets se désactivent.
    """

    champs_audit_masques: set = set()

    def _valeurs(self, obj, noms):
        valeurs = {}
        for nom in noms:
            if nom in self.champs_audit_masques:
                valeurs[nom] = "***"
                continue
            valeurs[nom] = obj._meta.get_field(nom).value_to_string(obj)
        return valeurs

    def save_model(self, request, obj, form, change):
        noms_colonnes = {f.name for f in obj._meta.concrete_fields}
        champs = sorted(nom for nom in form.changed_data if nom in noms_colonnes)
        avant = self._valeurs(type(obj).objects.get(pk=obj.pk), champs) if change else {}
        with transaction.atomic():
            super().save_model(request, obj, form, change)
            journaliser(
                f"{obj._meta.model_name}.{'modification' if change else 'creation'}",
                objet=obj,
                requete=request,
                details={"champs": champs, "avant": avant, "apres": self._valeurs(obj, champs)},
            )

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(Institution)
class InstitutionAdmin(AuditAdminMixin, admin.ModelAdmin):
    list_display = ["code", "nom_fr", "sigle", "langue_defaut", "actif"]
    formfield_overrides = {models.URLField: {"assume_scheme": "https"}}
    readonly_fields = ["uuid", "cree_le", "modifie_le"]


@admin.register(ParametreInstitution)
class ParametreInstitutionAdmin(admin.ModelAdmin):
    """Consultation seule : les paramètres se modifient par le service, qui valide et journalise."""

    list_display = ["institution", "cle", "valeur", "modifie_le", "modifie_par"]
    list_filter = ["institution"]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


class CompteurSerieInline(admin.TabularInline):
    model = CompteurSerie
    readonly_fields = ["cle_portee", "valeur"]
    extra = 0
    can_delete = False

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(SerieNumerotation)
class SerieNumerotationAdmin(AuditAdminMixin, admin.ModelAdmin):
    list_display = ["code", "institution", "gabarit", "par_annee", "par_unite", "par_categorie", "actif"]
    list_filter = ["institution", "actif"]
    inlines = [CompteurSerieInline]
