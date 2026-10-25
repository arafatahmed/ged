from django.contrib import admin

from .models import JournalAudit, ScellementAudit


class LectureSeuleAdmin(admin.ModelAdmin):
    """Consultation uniquement : le journal ne se modifie pas, même par un superadministrateur."""

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(JournalAudit)
class JournalAuditAdmin(LectureSeuleAdmin):
    list_display = ["horodatage", "action", "resultat", "acteur_libelle", "objet_type", "objet_id", "adresse_ip"]
    list_filter = ["resultat", "action", "institution"]
    search_fields = ["action", "acteur_libelle", "objet_id", "adresse_ip"]
    date_hierarchy = "horodatage"
    list_select_related = ["institution"]


@admin.register(ScellementAudit)
class ScellementAuditAdmin(LectureSeuleAdmin):
    list_display = ["date", "dernier_id", "nombre_evenements", "empreinte"]
