from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _


class Resultat(models.TextChoices):
    SUCCES = "succes", _("succès")
    REFUS = "refus", _("refus")
    ERREUR = "erreur", _("erreur")


class JournalAudit(models.Model):
    """Événement du journal d'audit.

    Table en ajout seul : un déclencheur PostgreSQL refuse UPDATE, DELETE et
    TRUNCATE (migration 0003). Chaque ligne contient l'empreinte de la
    précédente : supprimer ou modifier une ligne rompt la chaîne, ce que
    détecte `audit.services.verifier_chaine`.
    """

    horodatage = models.DateTimeField(_("horodatage"))
    institution = models.ForeignKey(
        "noyau.Institution",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="+",
        verbose_name=_("institution"),
    )
    acteur = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="+",
        verbose_name=_("compte de l'acteur"),
    )
    acteur_libelle = models.CharField(_("acteur"), max_length=150, blank=True)
    agissant_pour = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="+",
        verbose_name=_("agissant pour (délégation)"),
    )
    adresse_ip = models.CharField(_("adresse IP"), max_length=45, blank=True)
    action = models.CharField(_("action"), max_length=100)
    objet_type = models.CharField(_("type d'objet"), max_length=100, blank=True)
    objet_id = models.CharField(_("identifiant de l'objet"), max_length=64, blank=True)
    resultat = models.CharField(_("résultat"), max_length=10, choices=Resultat.choices)
    details = models.JSONField(_("détails"), default=dict, blank=True)
    empreinte_precedente = models.CharField(_("empreinte précédente"), max_length=64)
    empreinte = models.CharField(_("empreinte"), max_length=64, unique=True)

    class Meta:
        verbose_name = _("événement d'audit")
        verbose_name_plural = _("journal d'audit")
        ordering = ["-id"]
        indexes = [
            models.Index(fields=["institution", "horodatage"], name="audit_inst_horodatage"),
            models.Index(fields=["objet_type", "objet_id"], name="audit_objet"),
            models.Index(fields=["acteur", "horodatage"], name="audit_acteur"),
            models.Index(fields=["action"], name="audit_action"),
        ]

    def __str__(self):
        return f"{self.horodatage:%Y-%m-%d %H:%M:%S} {self.action} {self.resultat}"


class ScellementAudit(models.Model):
    """Empreinte de la dernière ligne du journal à la fin d'une journée.

    Une copie est exportée hors de la base : si la chaîne entière était
    recalculée après coup, elle ne correspondrait plus aux copies exportées.
    """

    date = models.DateField(_("date"), unique=True)
    dernier_id = models.BigIntegerField(_("dernier événement scellé"))
    empreinte = models.CharField(_("empreinte"), max_length=64)
    nombre_evenements = models.BigIntegerField(_("nombre d'événements depuis l'origine"))
    cree_le = models.DateTimeField(_("créé le"), auto_now_add=True)

    class Meta:
        verbose_name = _("scellement du journal")
        verbose_name_plural = _("scellements du journal")
        ordering = ["-date"]

    def __str__(self):
        return f"{self.date} #{self.dernier_id} {self.empreinte[:12]}…"
