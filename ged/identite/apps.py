from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class IdentiteConfig(AppConfig):
    name = "identite"
    verbose_name = _("Identités")

    def ready(self):
        from django.db.models.signals import post_migrate

        from . import signals  # noqa: F401

        post_migrate.connect(signals.synchroniser_catalogue, sender=self)
