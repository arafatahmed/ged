import uuid

from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q
from django.utils.translation import gettext_lazy as _

from noyau.langue import localise
from noyau.models import Horodatage


class TypeUnite(Horodatage):
    """Niveau d'organisation propre à l'institution : direction, service, agence…"""

    institution = models.ForeignKey(
        "noyau.Institution", on_delete=models.PROTECT, related_name="types_unite", verbose_name=_("institution")
    )
    code = models.SlugField(_("code"), max_length=30)
    libelle_fr = models.CharField(_("libellé en français"), max_length=100)
    libelle_ar = models.CharField(_("libellé en arabe"), max_length=100, blank=True)
    ordre = models.PositiveSmallIntegerField(_("ordre d'affichage"), default=0)
    actif = models.BooleanField(_("actif"), default=True)

    class Meta:
        verbose_name = _("type d'unité")
        verbose_name_plural = _("types d'unité")
        ordering = ["ordre", "libelle_fr"]
        constraints = [models.UniqueConstraint(fields=["institution", "code"], name="type_unite_unique_par_code")]

    def __str__(self):
        return localise(self.libelle_fr, self.libelle_ar)

    def libelle(self, langue):
        return self.libelle_ar if langue == "ar" and self.libelle_ar else self.libelle_fr


class UniteOrganisationnelle(Horodatage):
    """Unité de l'organisation (direction, service, agence…), organisée en arbre.

    `chemin` est le chemin matérialisé des identifiants depuis la racine
    (par exemple « /1/4/9/ ») : les sous-unités d'une unité sont celles dont le
    chemin commence par le sien. Il est tenu à jour par `organisation.services`.
    """

    institution = models.ForeignKey(
        "noyau.Institution", on_delete=models.PROTECT, related_name="unites", verbose_name=_("institution")
    )
    uuid = models.UUIDField(_("identifiant public"), default=uuid.uuid4, unique=True, editable=False)
    type = models.ForeignKey(TypeUnite, on_delete=models.PROTECT, related_name="unites", verbose_name=_("type"))
    parent = models.ForeignKey(
        "self",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="enfants",
        verbose_name=_("unité parente"),
    )
    code = models.SlugField(_("code"), max_length=30, help_text=_("Utilisé dans les références (jeton {UNITE})."))
    sigle = models.CharField(_("sigle"), max_length=30, blank=True)
    libelle_fr = models.CharField(_("libellé en français"), max_length=255)
    libelle_ar = models.CharField(_("libellé en arabe"), max_length=255, blank=True)
    chemin = models.CharField(_("chemin"), max_length=1000, editable=False)
    actif = models.BooleanField(_("active"), default=True)

    class Meta:
        verbose_name = _("unité organisationnelle")
        verbose_name_plural = _("unités organisationnelles")
        ordering = ["chemin"]
        constraints = [
            models.UniqueConstraint(fields=["institution", "code"], name="unite_unique_par_code"),
            models.CheckConstraint(condition=~Q(parent=models.F("id")), name="unite_pas_son_propre_parent"),
        ]
        indexes = [
            # Index adapté aux recherches par préfixe (chemin LIKE '/1/4/%').
            models.Index(fields=["chemin"], name="unite_chemin_prefixe", opclasses=["varchar_pattern_ops"]),
        ]

    def __str__(self):
        return f"{self.sigle or self.code} · {localise(self.libelle_fr, self.libelle_ar)}"

    @property
    def profondeur(self):
        return max(self.chemin.count("/") - 2, 0)

    @property
    def ids_ancetres(self):
        """Identifiants des unités du chemin, de la racine à l'unité elle-même."""
        return [int(i) for i in self.chemin.strip("/").split("/") if i]

    def libelle(self, langue):
        return self.libelle_ar if langue == "ar" and self.libelle_ar else self.libelle_fr

    def clean(self):
        if self.type_id and self.type.institution_id != self.institution_id:
            raise ValidationError({"type": _("Ce type d'unité appartient à une autre institution.")})
        if self.parent_id:
            if self.parent.institution_id != self.institution_id:
                raise ValidationError({"parent": _("L'unité parente appartient à une autre institution.")})
            if self.pk and (self.parent_id == self.pk or f"/{self.pk}/" in self.parent.chemin):
                raise ValidationError({"parent": _("Une unité ne peut pas être rattachée à l'une de ses sous-unités.")})
            if not self.parent.actif and self.actif:
                raise ValidationError({"parent": _("L'unité parente est désactivée.")})


class Poste(Horodatage):
    institution = models.ForeignKey(
        "noyau.Institution", on_delete=models.PROTECT, related_name="postes", verbose_name=_("institution")
    )
    unite = models.ForeignKey(
        UniteOrganisationnelle, on_delete=models.PROTECT, related_name="postes", verbose_name=_("unité")
    )
    intitule_fr = models.CharField(_("intitulé en français"), max_length=255)
    intitule_ar = models.CharField(_("intitulé en arabe"), max_length=255, blank=True)
    superieur = models.ForeignKey(
        "self",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="subordonnes",
        verbose_name=_("poste supérieur"),
        help_text=_("Sert à l'escalade hiérarchique."),
    )
    actif = models.BooleanField(_("actif"), default=True)

    class Meta:
        verbose_name = _("poste")
        verbose_name_plural = _("postes")
        ordering = ["unite__chemin", "intitule_fr"]

    def __str__(self):
        return f"{localise(self.intitule_fr, self.intitule_ar)} ({self.unite.sigle or self.unite.code})"

    def clean(self):
        if self.unite_id and self.unite.institution_id != self.institution_id:
            raise ValidationError({"unite": _("Cette unité appartient à une autre institution.")})
        if self.superieur_id:
            if self.superieur.institution_id != self.institution_id:
                raise ValidationError({"superieur": _("Ce poste appartient à une autre institution.")})
            poste = self.superieur
            while poste is not None:
                if self.pk and poste.pk == self.pk:
                    raise ValidationError({"superieur": _("La hiérarchie des postes ne peut pas former une boucle.")})
                poste = poste.superieur
