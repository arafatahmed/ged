import uuid

from django.conf import settings
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.db import models
from django.db.models import Q
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from noyau.langue import localise


class GestionnaireUtilisateurs(BaseUserManager):
    use_in_migrations = True

    def create_user(self, identifiant, password=None, **champs):
        if not identifiant:
            raise ValueError("L'identifiant est obligatoire.")
        utilisateur = self.model(identifiant=identifiant, **champs)
        utilisateur.set_password(password)
        utilisateur.full_clean(exclude=["password"])
        utilisateur.save(using=self._db)
        return utilisateur

    def create_superuser(self, identifiant, password=None, **champs):
        """Superadministrateur technique : hors institution, sans accès au contenu documentaire."""
        champs.update(is_staff=True, is_superuser=True, institution=None)
        return self.create_user(identifiant, password, **champs)


class NiveauHabilitation(models.IntegerChoices):
    PUBLIC_INTERNE = 0, _("Public interne")
    RESTREINT = 1, _("Restreint")
    CONFIDENTIEL = 2, _("Confidentiel")
    SECRET = 3, _("Secret")


class Utilisateur(AbstractBaseUser, PermissionsMixin):
    """Compte utilisateur.

    Les droits ne sont pas portés par le compte mais par ses affectations
    (rôle exercé dans une unité). Le niveau d'habilitation borne en plus les
    documents accessibles selon leur confidentialité.
    """

    uuid = models.UUIDField(_("identifiant public"), default=uuid.uuid4, unique=True, editable=False)
    institution = models.ForeignKey(
        "noyau.Institution",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="utilisateurs",
        verbose_name=_("institution"),
        help_text=_("Vide uniquement pour le superadministrateur technique."),
    )
    identifiant = models.CharField(_("identifiant"), max_length=150, unique=True)
    nom = models.CharField(_("nom"), max_length=150)
    prenom = models.CharField(_("prénom"), max_length=150)
    nom_ar = models.CharField(_("nom complet en arabe"), max_length=255, blank=True)
    courriel = models.EmailField(_("courriel"), blank=True)
    langue = models.CharField(
        _("langue de l'interface"),
        max_length=5,
        choices=settings.LANGUAGES,
        blank=True,
        help_text=_("Vide : langue par défaut de l'institution."),
    )
    is_active = models.BooleanField(_("actif"), default=True)
    is_staff = models.BooleanField(_("accès à l'administration technique"), default=False)
    date_creation = models.DateTimeField(_("créé le"), default=timezone.now)
    niveau_habilitation = models.PositiveSmallIntegerField(
        _("niveau d'habilitation"), choices=NiveauHabilitation.choices, default=NiveauHabilitation.PUBLIC_INTERNE
    )
    echecs_connexion = models.PositiveSmallIntegerField(_("échecs de connexion consécutifs"), default=0)
    verrouille_jusqu_a = models.DateTimeField(_("verrouillé jusqu'à"), null=True, blank=True)
    doit_changer_mot_de_passe = models.BooleanField(
        _("doit changer son mot de passe"),
        default=False,
        help_text=_("Activé lorsqu'un administrateur fixe un mot de passe temporaire."),
    )
    mot_de_passe_modifie_le = models.DateTimeField(_("mot de passe modifié le"), null=True, blank=True)

    objects = GestionnaireUtilisateurs()

    USERNAME_FIELD = "identifiant"
    EMAIL_FIELD = "courriel"
    REQUIRED_FIELDS = ["nom", "prenom"]

    class Meta:
        verbose_name = _("utilisateur")
        verbose_name_plural = _("utilisateurs")
        ordering = ["nom", "prenom"]
        constraints = [
            models.CheckConstraint(
                condition=Q(is_superuser=True) | Q(institution__isnull=False),
                name="utilisateur_rattache_a_une_institution",
            )
        ]

    def __str__(self):
        return f"{self.prenom} {self.nom} ({self.identifiant})"

    def get_full_name(self):
        return f"{self.prenom} {self.nom}".strip()

    def get_short_name(self):
        return self.prenom

    def est_verrouille(self, maintenant=None):
        return bool(self.verrouille_jusqu_a and self.verrouille_jusqu_a > (maintenant or timezone.now()))

    @property
    def mfa_active(self):
        appareil = getattr(self, "appareil_totp", None)
        return bool(appareil and appareil.confirme)


class Permission(models.Model):
    """Permission du catalogue (`identite.catalogue`), synchronisée après chaque migration."""

    code = models.CharField(_("code"), max_length=100, unique=True)
    groupe = models.CharField(_("groupe"), max_length=100)
    description = models.CharField(_("description"), max_length=255)
    actif = models.BooleanField(_("active"), default=True)

    class Meta:
        verbose_name = _("permission")
        verbose_name_plural = _("permissions")
        ordering = ["groupe", "code"]

    def __str__(self):
        return self.code


class Role(models.Model):
    institution = models.ForeignKey(
        "noyau.Institution", on_delete=models.PROTECT, related_name="roles", verbose_name=_("institution")
    )
    uuid = models.UUIDField(_("identifiant public"), default=uuid.uuid4, unique=True, editable=False)
    code = models.SlugField(_("code"), max_length=50)
    libelle_fr = models.CharField(_("libellé en français"), max_length=150)
    libelle_ar = models.CharField(_("libellé en arabe"), max_length=150, blank=True)
    description = models.TextField(_("description"), blank=True)
    permissions = models.ManyToManyField(Permission, related_name="roles", blank=True, verbose_name=_("permissions"))
    mfa_requis = models.BooleanField(
        _("double authentification obligatoire"),
        default=False,
        help_text=_("Les titulaires de ce rôle doivent activer la double authentification."),
    )
    systeme = models.BooleanField(_("rôle fourni à l'installation"), default=False, editable=False)
    actif = models.BooleanField(_("actif"), default=True)
    cree_le = models.DateTimeField(_("créé le"), auto_now_add=True)
    modifie_le = models.DateTimeField(_("modifié le"), auto_now=True)

    class Meta:
        verbose_name = _("rôle")
        verbose_name_plural = _("rôles")
        ordering = ["libelle_fr"]
        constraints = [models.UniqueConstraint(fields=["institution", "code"], name="role_unique_par_code")]

    def __str__(self):
        return localise(self.libelle_fr, self.libelle_ar)

    def libelle(self, langue):
        return self.libelle_ar if langue == "ar" and self.libelle_ar else self.libelle_fr


class AffectationQuerySet(models.QuerySet):
    def actives(self, date=None):
        date = date or timezone.localdate()
        return self.filter(
            Q(date_fin__isnull=True) | Q(date_fin__gte=date),
            date_debut__lte=date,
            role__actif=True,
            unite__actif=True,
        )


class Affectation(models.Model):
    """Rôle exercé par un utilisateur dans une unité, pour une période.

    Une affectation ne se supprime pas : elle se clôture (date de fin).
    """

    uuid = models.UUIDField(_("identifiant public"), default=uuid.uuid4, unique=True, editable=False)
    utilisateur = models.ForeignKey(
        Utilisateur, on_delete=models.PROTECT, related_name="affectations", verbose_name=_("utilisateur")
    )
    unite = models.ForeignKey(
        "organisation.UniteOrganisationnelle",
        on_delete=models.PROTECT,
        related_name="affectations",
        verbose_name=_("unité"),
    )
    role = models.ForeignKey(Role, on_delete=models.PROTECT, related_name="affectations", verbose_name=_("rôle"))
    poste = models.ForeignKey(
        "organisation.Poste",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="affectations",
        verbose_name=_("poste"),
    )
    etendue_sous_unites = models.BooleanField(
        _("s'étend aux sous-unités"),
        default=False,
        help_text=_("Le rôle s'exerce aussi dans toutes les unités rattachées à celle-ci."),
    )
    date_debut = models.DateField(_("date de début"), default=timezone.localdate)
    date_fin = models.DateField(_("date de fin"), null=True, blank=True)
    attribuee_par = models.ForeignKey(
        Utilisateur,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="+",
        verbose_name=_("attribuée par"),
    )
    cree_le = models.DateTimeField(_("créée le"), auto_now_add=True)

    objects = AffectationQuerySet.as_manager()

    class Meta:
        verbose_name = _("affectation")
        verbose_name_plural = _("affectations")
        ordering = ["-date_debut"]
        constraints = [
            models.CheckConstraint(
                condition=Q(date_fin__isnull=True) | Q(date_fin__gte=models.F("date_debut")),
                name="affectation_dates_coherentes",
            )
        ]
        indexes = [models.Index(fields=["utilisateur", "date_fin"], name="affectation_utilisateur")]

    def __str__(self):
        return f"{self.utilisateur.identifiant} · {self.role} · {self.unite}"

    def est_active(self, date=None):
        date = date or timezone.localdate()
        return self.date_debut <= date and (self.date_fin is None or self.date_fin >= date)


class DelegationQuerySet(models.QuerySet):
    def en_cours(self, maintenant=None):
        maintenant = maintenant or timezone.now()
        return self.filter(debut__lte=maintenant, fin__gte=maintenant, revoquee_le__isnull=True)


class Delegation(models.Model):
    """Le délégataire exerce temporairement les rôles du délégant (hors permissions d'administration)."""

    uuid = models.UUIDField(_("identifiant public"), default=uuid.uuid4, unique=True, editable=False)
    delegant = models.ForeignKey(
        Utilisateur, on_delete=models.PROTECT, related_name="delegations_donnees", verbose_name=_("délégant")
    )
    delegataire = models.ForeignKey(
        Utilisateur, on_delete=models.PROTECT, related_name="delegations_recues", verbose_name=_("délégataire")
    )
    roles = models.ManyToManyField(
        Role,
        blank=True,
        related_name="+",
        verbose_name=_("rôles délégués"),
        help_text=_("Vide : tous les rôles du délégant."),
    )
    debut = models.DateTimeField(_("début"))
    fin = models.DateTimeField(_("fin"))
    motif = models.CharField(_("motif"), max_length=255)
    creee_par = models.ForeignKey(Utilisateur, on_delete=models.PROTECT, related_name="+", verbose_name=_("créée par"))
    creee_le = models.DateTimeField(_("créée le"), auto_now_add=True)
    revoquee_le = models.DateTimeField(_("révoquée le"), null=True, blank=True)
    revoquee_par = models.ForeignKey(
        Utilisateur, on_delete=models.PROTECT, null=True, blank=True, related_name="+", verbose_name=_("révoquée par")
    )

    objects = DelegationQuerySet.as_manager()

    class Meta:
        verbose_name = _("délégation")
        verbose_name_plural = _("délégations")
        ordering = ["-debut"]
        constraints = [
            models.CheckConstraint(condition=Q(fin__gt=models.F("debut")), name="delegation_dates_coherentes"),
            models.CheckConstraint(condition=~Q(delegant=models.F("delegataire")), name="delegation_a_un_tiers"),
        ]

    def __str__(self):
        return f"{self.delegant.identifiant} → {self.delegataire.identifiant}"


class AppareilTotp(models.Model):
    """Application d'authentification (TOTP, RFC 6238) d'un utilisateur."""

    utilisateur = models.OneToOneField(
        Utilisateur, on_delete=models.PROTECT, related_name="appareil_totp", verbose_name=_("utilisateur")
    )
    secret = models.CharField(_("secret"), max_length=64)
    confirme = models.BooleanField(_("confirmé"), default=False)
    dernier_pas = models.BigIntegerField(
        _("dernier pas de temps utilisé"), default=0, help_text=_("Empêche de réutiliser un code.")
    )
    cree_le = models.DateTimeField(_("créé le"), auto_now_add=True)
    confirme_le = models.DateTimeField(_("confirmé le"), null=True, blank=True)

    class Meta:
        verbose_name = _("application d'authentification")
        verbose_name_plural = _("applications d'authentification")

    def __str__(self):
        return f"TOTP {self.utilisateur.identifiant}"


class CodeSecours(models.Model):
    """Code de secours à usage unique ; seule son empreinte est conservée."""

    utilisateur = models.ForeignKey(
        Utilisateur, on_delete=models.PROTECT, related_name="codes_secours", verbose_name=_("utilisateur")
    )
    empreinte = models.CharField(_("empreinte"), max_length=64, unique=True)
    utilise_le = models.DateTimeField(_("utilisé le"), null=True, blank=True)
    cree_le = models.DateTimeField(_("créé le"), auto_now_add=True)

    class Meta:
        verbose_name = _("code de secours")
        verbose_name_plural = _("codes de secours")

    def __str__(self):
        return f"{self.utilisateur.identifiant} {self.empreinte[:8]}…"


class SessionUtilisateur(models.Model):
    """Journal des sessions : permet de lister et révoquer les sessions d'un compte."""

    class MotifFin(models.TextChoices):
        DECONNEXION = "deconnexion", _("déconnexion")
        INACTIVITE = "inactivite", _("inactivité")
        REVOCATION = "revocation", _("révocation")
        DESACTIVATION = "desactivation", _("compte désactivé")

    utilisateur = models.ForeignKey(
        Utilisateur, on_delete=models.PROTECT, related_name="sessions", verbose_name=_("utilisateur")
    )
    cle_session = models.CharField(_("clé de session"), max_length=40, unique=True)
    adresse_ip = models.CharField(_("adresse IP"), max_length=45, blank=True)
    agent = models.CharField(_("navigateur"), max_length=255, blank=True)
    debut = models.DateTimeField(_("début"), auto_now_add=True)
    fin = models.DateTimeField(_("fin"), null=True, blank=True)
    motif_fin = models.CharField(_("motif de fin"), max_length=20, choices=MotifFin.choices, blank=True)

    class Meta:
        verbose_name = _("session")
        verbose_name_plural = _("sessions")
        ordering = ["-debut"]
        indexes = [models.Index(fields=["utilisateur", "fin"], name="session_utilisateur_fin")]

    def __str__(self):
        return f"{self.utilisateur.identifiant} {self.debut:%Y-%m-%d %H:%M}"
