import uuid
import zoneinfo

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import RegexValidator
from django.db import models
from django.utils.translation import gettext_lazy as _

from . import numerotation
from .langue import localise
from .validators import valider_logo

couleur_hexa = RegexValidator(r"^#[0-9a-fA-F]{6}$", _("Couleur attendue au format #RRGGBB."))


def valider_fuseau(valeur):
    if valeur not in zoneinfo.available_timezones():
        raise ValidationError(_("Fuseau horaire inconnu : %(valeur)s."), params={"valeur": valeur})


class Horodatage(models.Model):
    cree_le = models.DateTimeField(_("créé le"), auto_now_add=True)
    modifie_le = models.DateTimeField(_("modifié le"), auto_now=True)

    class Meta:
        abstract = True


class Institution(Horodatage):
    FORMATS_DATE = [
        ("d/m/Y", "JJ/MM/AAAA"),
        ("d-m-Y", "JJ-MM-AAAA"),
        ("Y-m-d", "AAAA-MM-JJ"),
    ]

    uuid = models.UUIDField(_("identifiant public"), default=uuid.uuid4, unique=True, editable=False)
    code = models.SlugField(_("code"), max_length=30, unique=True)
    nom_fr = models.CharField(_("nom en français"), max_length=255)
    nom_ar = models.CharField(_("nom en arabe"), max_length=255, blank=True)
    sigle = models.CharField(_("sigle"), max_length=30)
    logo = models.FileField(_("logo"), upload_to="institutions/logos/", blank=True, validators=[valider_logo])
    couleur_primaire = models.CharField(
        _("couleur principale"), max_length=7, default="#1f4e79", validators=[couleur_hexa]
    )
    couleur_secondaire = models.CharField(
        _("couleur secondaire"), max_length=7, default="#2e7d32", validators=[couleur_hexa]
    )
    adresse = models.TextField(_("adresse"), blank=True)
    telephone = models.CharField(_("téléphone"), max_length=50, blank=True)
    courriel = models.EmailField(_("courriel"), blank=True)
    site_web = models.URLField(_("site web"), blank=True)
    fuseau_horaire = models.CharField(_("fuseau horaire"), max_length=64, default="UTC", validators=[valider_fuseau])
    langue_defaut = models.CharField(_("langue par défaut"), max_length=5, choices=settings.LANGUAGES, default="fr")
    format_date = models.CharField(_("format de date"), max_length=10, choices=FORMATS_DATE, default="d/m/Y")
    actif = models.BooleanField(_("active"), default=True)

    class Meta:
        verbose_name = _("institution")
        verbose_name_plural = _("institutions")
        ordering = ["nom_fr"]

    def __str__(self):
        return localise(self.nom_fr, self.nom_ar)

    def clean(self):
        if not settings.GED_MULTI_INSTITUTIONS:
            autres = Institution.objects.exclude(pk=self.pk)
            if autres.exists():
                raise ValidationError(_("Cette installation est mono-institution : une institution existe déjà."))

    def nom(self, langue):
        return self.nom_ar if langue == "ar" and self.nom_ar else self.nom_fr


class ParametreInstitution(Horodatage):
    """Paramètre fonctionnel d'une institution. Les clés admises sont déclarées dans `parametres.py`."""

    institution = models.ForeignKey(
        Institution, on_delete=models.PROTECT, related_name="parametres", verbose_name=_("institution")
    )
    cle = models.CharField(_("clé"), max_length=100)
    valeur = models.JSONField(_("valeur"))
    modifie_par = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="+",
        verbose_name=_("modifié par"),
    )

    class Meta:
        verbose_name = _("paramètre de l'institution")
        verbose_name_plural = _("paramètres de l'institution")
        constraints = [models.UniqueConstraint(fields=["institution", "cle"], name="parametre_unique_par_cle")]

    def __str__(self):
        return f"{self.cle} = {self.valeur!r}"


class SerieNumerotation(Horodatage):
    institution = models.ForeignKey(
        Institution, on_delete=models.PROTECT, related_name="series", verbose_name=_("institution")
    )
    code = models.SlugField(_("code"), max_length=50)
    libelle_fr = models.CharField(_("libellé en français"), max_length=255)
    libelle_ar = models.CharField(_("libellé en arabe"), max_length=255, blank=True)
    gabarit = models.CharField(
        _("gabarit"),
        max_length=100,
        help_text=_("Exemple : {SIGLE}/{UNITE}/{AAAA}/{SEQ:5}"),
    )
    par_annee = models.BooleanField(_("repart à 1 chaque année"), default=True)
    par_unite = models.BooleanField(_("compteur distinct par unité"), default=False)
    par_categorie = models.BooleanField(_("compteur distinct par catégorie"), default=False)
    actif = models.BooleanField(_("active"), default=True)

    class Meta:
        verbose_name = _("série de numérotation")
        verbose_name_plural = _("séries de numérotation")
        constraints = [models.UniqueConstraint(fields=["institution", "code"], name="serie_unique_par_code")]

    def __str__(self):
        return f"{self.code} ({self.gabarit})"

    CHAMPS_FIGES = ("gabarit", "par_annee", "par_unite", "par_categorie")

    def clean(self):
        numerotation.analyser_gabarit(
            self.gabarit,
            par_annee=self.par_annee,
            par_unite=self.par_unite,
            par_categorie=self.par_categorie,
        )
        if self.pk and self.compteurs.exists():
            ancienne = SerieNumerotation.objects.get(pk=self.pk)
            if any(getattr(ancienne, c) != getattr(self, c) for c in self.CHAMPS_FIGES):
                raise ValidationError(
                    _(
                        "Cette série a déjà attribué des numéros : son gabarit et sa portée ne "
                        "peuvent plus changer. Créez une nouvelle série."
                    )
                )

    def cle_portee(self, *, date, unite="", categorie=""):
        parties = []
        if self.par_annee:
            parties.append(f"{date.year:04d}")
        if self.par_unite:
            parties.append(unite)
        if self.par_categorie:
            parties.append(categorie)
        return "/".join(parties) or "*"


class CompteurSerie(models.Model):
    serie = models.ForeignKey(
        SerieNumerotation, on_delete=models.PROTECT, related_name="compteurs", verbose_name=_("série")
    )
    cle_portee = models.CharField(_("portée"), max_length=100)
    valeur = models.PositiveBigIntegerField(_("dernier numéro attribué"), default=0)

    class Meta:
        verbose_name = _("compteur de série")
        verbose_name_plural = _("compteurs de série")
        constraints = [models.UniqueConstraint(fields=["serie", "cle_portee"], name="compteur_unique_par_portee")]

    def __str__(self):
        return f"{self.serie.code} [{self.cle_portee}] = {self.valeur}"
