"""Documents, versions et fichiers (lot 3).

Aucune suppression physique : un document, une version ou un fichier n'est
jamais effacé par l'application (l'élimination archivistique viendra au lot 15).
Les octets sont dans le stockage objet, sous une clé aléatoire jamais exposée :
ils ne sont lus que par l'application, après contrôle des droits et seulement
si l'analyse du fichier l'a déclaré sain.
"""

import uuid

from django.conf import settings
from django.contrib.postgres.fields import ArrayField
from django.contrib.postgres.indexes import GinIndex
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import F, Q
from django.utils.translation import gettext_lazy as _

from identite.models import NiveauHabilitation
from noyau.models import Horodatage, Institution
from organisation.models import UniteOrganisationnelle

from .formats import FORMATS


class TypeDocument(Horodatage):
    institution = models.ForeignKey(
        Institution, on_delete=models.PROTECT, related_name="types_document", verbose_name=_("institution")
    )
    uuid = models.UUIDField(_("identifiant public"), default=uuid.uuid4, unique=True, editable=False)
    code = models.SlugField(_("code"), max_length=50)
    libelle_fr = models.CharField(_("libellé en français"), max_length=255)
    libelle_ar = models.CharField(_("libellé en arabe"), max_length=255, blank=True)
    categorie = models.CharField(_("catégorie"), max_length=100, blank=True)
    formats_autorises = models.JSONField(
        _("formats autorisés"),
        default=list,
        blank=True,
        help_text=_("Codes de formats ; vide : tous les formats admis."),
    )
    confidentialite_defaut = models.PositiveSmallIntegerField(
        _("confidentialité par défaut"), choices=NiveauHabilitation.choices, default=NiveauHabilitation.PUBLIC_INTERNE
    )
    actif = models.BooleanField(_("actif"), default=True)

    class Meta:
        verbose_name = _("type de document")
        verbose_name_plural = _("types de document")
        ordering = ["libelle_fr"]
        constraints = [models.UniqueConstraint(fields=["institution", "code"], name="type_document_code_unique")]

    def __str__(self):
        return self.libelle_fr

    def clean(self):
        if not isinstance(self.formats_autorises, list) or any(f not in FORMATS for f in self.formats_autorises):
            raise ValidationError({"formats_autorises": _("Format inconnu.")})
        self.formats_autorises = sorted(set(self.formats_autorises))

    def admet(self, code_format):
        return not self.formats_autorises or code_format in self.formats_autorises


class NatureMetadonnee(models.TextChoices):
    TEXTE = "texte", _("Texte")
    NOMBRE = "nombre", _("Nombre")
    DATE = "date", _("Date")
    LISTE = "liste", _("Liste de valeurs")


class DefinitionMetadonnee(models.Model):
    type_document = models.ForeignKey(
        TypeDocument, on_delete=models.PROTECT, related_name="definitions", verbose_name=_("type de document")
    )
    code = models.SlugField(_("code"), max_length=50)
    libelle_fr = models.CharField(_("libellé en français"), max_length=255)
    libelle_ar = models.CharField(_("libellé en arabe"), max_length=255, blank=True)
    nature = models.CharField(_("nature"), max_length=10, choices=NatureMetadonnee.choices)
    obligatoire = models.BooleanField(_("obligatoire"), default=False)
    valeurs_liste = models.JSONField(_("valeurs de la liste"), default=list, blank=True)
    ordre = models.PositiveSmallIntegerField(_("ordre d'affichage"), default=0)
    actif = models.BooleanField(_("active"), default=True)

    class Meta:
        verbose_name = _("définition de métadonnée")
        verbose_name_plural = _("définitions de métadonnées")
        ordering = ["ordre", "pk"]
        constraints = [
            models.UniqueConstraint(fields=["type_document", "code"], name="definition_metadonnee_code_unique")
        ]

    def __str__(self):
        return self.libelle_fr

    def clean(self):
        if self.nature == NatureMetadonnee.LISTE:
            if (
                not isinstance(self.valeurs_liste, list)
                or not self.valeurs_liste
                or not all(isinstance(v, str) and v.strip() for v in self.valeurs_liste)
            ):
                raise ValidationError({"valeurs_liste": _("Indiquez au moins une valeur.")})
        else:
            self.valeurs_liste = []


class StatutDocument(models.TextChoices):
    BROUILLON = "brouillon", _("En cours")
    VALIDE = "valide", _("Validé")
    ARCHIVE = "archive", _("Archivé")


class Document(Horodatage):
    institution = models.ForeignKey(
        Institution, on_delete=models.PROTECT, related_name="documents", verbose_name=_("institution")
    )
    uuid = models.UUIDField(_("identifiant public"), default=uuid.uuid4, unique=True, editable=False)
    # Nulle tant que le document n'est pas enregistré dans une série : l'unicité ne porte que sur les valeurs.
    reference = models.CharField(_("référence"), max_length=100, null=True, blank=True)  # noqa: DJ001
    titre = models.CharField(_("titre"), max_length=500)
    objet = models.TextField(_("objet"), blank=True)
    type = models.ForeignKey(TypeDocument, on_delete=models.PROTECT, related_name="documents", verbose_name=_("type"))
    date_document = models.DateField(_("date du document"), null=True, blank=True)
    unite_proprietaire = models.ForeignKey(
        UniteOrganisationnelle, on_delete=models.PROTECT, related_name="documents", verbose_name=_("unité propriétaire")
    )
    confidentialite = models.PositiveSmallIntegerField(
        _("confidentialité"), choices=NiveauHabilitation.choices, default=NiveauHabilitation.PUBLIC_INTERNE
    )
    mots_cles = ArrayField(models.CharField(max_length=100), verbose_name=_("mots-clés"), default=list, blank=True)
    metadonnees = models.JSONField(_("métadonnées"), default=dict, blank=True)
    statut = models.CharField(_("statut"), max_length=20, choices=StatutDocument.choices, default="brouillon")
    version_courante = models.ForeignKey(
        "VersionDocument",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="+",
        verbose_name=_("version courante"),
    )
    cree_par = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+", verbose_name=_("créé par")
    )
    modifie_par = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="+",
        verbose_name=_("modifié par"),
    )

    class Meta:
        verbose_name = _("document")
        verbose_name_plural = _("documents")
        ordering = ["-cree_le"]
        constraints = [
            models.UniqueConstraint(
                fields=["institution", "reference"],
                condition=Q(reference__isnull=False),
                name="document_reference_unique",
            )
        ]
        indexes = [
            models.Index(fields=["institution", "unite_proprietaire", "statut"], name="document_unite_statut"),
            GinIndex(fields=["mots_cles"], name="document_mots_cles"),
            GinIndex(fields=["metadonnees"], name="document_metadonnees"),
        ]

    def __str__(self):
        return self.titre

    @property
    def modifiable(self):
        return self.statut == StatutDocument.BROUILLON


class StatutVersion(models.TextChoices):
    BROUILLON = "brouillon", _("Brouillon")
    VALIDEE = "validee", _("Validée")


class VersionDocument(models.Model):
    document = models.ForeignKey(
        Document, on_delete=models.PROTECT, related_name="versions", verbose_name=_("document")
    )
    numero = models.PositiveIntegerField(_("numéro"))
    commentaire = models.TextField(_("commentaire"), blank=True)
    statut = models.CharField(_("statut"), max_length=20, choices=StatutVersion.choices, default="brouillon")
    creee_par = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+", verbose_name=_("créée par")
    )
    creee_le = models.DateTimeField(_("créée le"), auto_now_add=True)

    class Meta:
        verbose_name = _("version de document")
        verbose_name_plural = _("versions de document")
        ordering = ["document", "-numero"]
        constraints = [models.UniqueConstraint(fields=["document", "numero"], name="version_numero_unique")]

    def __str__(self):
        return f"{self.document} v{self.numero}"


class RoleFichier(models.TextChoices):
    PRINCIPAL = "principal", _("Fichier principal")
    PIECE_JOINTE = "piece_jointe", _("Pièce jointe")


class EtatAnalyse(models.TextChoices):
    EN_ATTENTE = "en_attente", _("Analyse en cours")
    SAIN = "sain", _("Sain")
    INFECTE = "infecte", _("Infecté")
    REFUSE = "refuse", _("Refusé")


class FichierDocument(models.Model):
    institution = models.ForeignKey(
        Institution, on_delete=models.PROTECT, related_name="+", verbose_name=_("institution")
    )
    uuid = models.UUIDField(_("identifiant public"), default=uuid.uuid4, unique=True, editable=False)
    version = models.ForeignKey(
        VersionDocument, on_delete=models.PROTECT, related_name="fichiers", verbose_name=_("version")
    )
    role = models.CharField(_("rôle"), max_length=20, choices=RoleFichier.choices)
    nom_origine = models.CharField(_("nom d'origine"), max_length=255)
    format = models.CharField(_("format"), max_length=10)
    type_mime = models.CharField(_("type MIME reconnu"), max_length=255)
    taille = models.PositiveBigIntegerField(_("taille en octets"))
    sha256 = models.CharField(_("empreinte SHA-256"), max_length=64)
    # Clé dans le stockage objet : aléatoire, jamais transmise au navigateur.
    cle_objet = models.CharField(_("clé de l'objet"), max_length=255, unique=True)
    etat_analyse = models.CharField(
        _("état de l'analyse"), max_length=20, choices=EtatAnalyse.choices, default=EtatAnalyse.EN_ATTENTE
    )
    motif = models.CharField(_("motif"), max_length=255, blank=True)
    tentatives = models.PositiveSmallIntegerField(_("tentatives d'analyse"), default=0)
    analyse_le = models.DateTimeField(_("analysé le"), null=True, blank=True)
    depose_par = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+", verbose_name=_("déposé par")
    )
    depose_le = models.DateTimeField(_("déposé le"), auto_now_add=True)

    class Meta:
        verbose_name = _("fichier de document")
        verbose_name_plural = _("fichiers de document")
        ordering = ["role", "depose_le"]
        constraints = [
            models.UniqueConstraint(
                fields=["version"], condition=Q(role="principal"), name="un_fichier_principal_par_version"
            )
        ]
        indexes = [
            models.Index(fields=["institution", "sha256"], name="fichier_empreinte"),
            models.Index(fields=["etat_analyse"], condition=Q(etat_analyse="en_attente"), name="fichier_a_analyser"),
        ]

    def __str__(self):
        return self.nom_origine

    @property
    def lisible(self):
        return self.etat_analyse == EtatAnalyse.SAIN

    @property
    def apercu_possible(self):
        return self.lisible and FORMATS[self.format].apercu


class NatureRelation(models.TextChoices):
    REPONSE_A = "reponse_a", _("Réponse à")
    ANNULE = "annule", _("Annule")
    REMPLACE = "remplace", _("Remplace")
    ANNEXE_DE = "annexe_de", _("Annexe de")
    VOIR_AUSSI = "voir_aussi", _("Voir aussi")


class RelationDocument(models.Model):
    institution = models.ForeignKey(
        Institution, on_delete=models.PROTECT, related_name="+", verbose_name=_("institution")
    )
    source = models.ForeignKey(
        Document, on_delete=models.PROTECT, related_name="relations_sortantes", verbose_name=_("source")
    )
    cible = models.ForeignKey(
        Document, on_delete=models.PROTECT, related_name="relations_entrantes", verbose_name=_("cible")
    )
    nature = models.CharField(_("nature"), max_length=20, choices=NatureRelation.choices)
    creee_par = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+", verbose_name=_("créée par")
    )
    creee_le = models.DateTimeField(_("créée le"), auto_now_add=True)

    class Meta:
        verbose_name = _("relation entre documents")
        verbose_name_plural = _("relations entre documents")
        constraints = [
            models.UniqueConstraint(fields=["source", "cible", "nature"], name="relation_unique"),
            models.CheckConstraint(condition=~Q(source=F("cible")), name="relation_sans_boucle"),
        ]

    def __str__(self):
        return f"{self.source} {self.nature} {self.cible}"
