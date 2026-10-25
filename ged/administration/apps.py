from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class AdministrationConfig(AppConfig):
    name = "administration"
    verbose_name = _("Administration fonctionnelle")
