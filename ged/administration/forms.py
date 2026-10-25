import secrets

from django import forms
from django.utils.translation import gettext_lazy as _

from acces import moteur
from identite.models import Affectation, Permission, Role, Utilisateur
from organisation.models import Poste, TypeUnite, UniteOrganisationnelle


def generer_mot_de_passe():
    return secrets.token_urlsafe(12)


class FormulaireUnite(forms.ModelForm):
    class Meta:
        model = UniteOrganisationnelle
        fields = ["type", "parent", "code", "sigle", "libelle_fr", "libelle_ar"]

    def __init__(self, *args, acteur, **kwargs):
        super().__init__(*args, **kwargs)
        # Nécessaire à la validation du modèle (cohérence d'institution) dès le formulaire.
        self.instance.institution_id = acteur.institution_id
        self.fields["type"].queryset = TypeUnite.objects.filter(institution_id=acteur.institution_id, actif=True)
        parents = moteur.unites_autorisees(acteur, "administration.organisation").filter(actif=True)
        if self.instance.pk:
            parents = parents.exclude(chemin__startswith=self.instance.chemin)
        self.fields["parent"].queryset = parents
        self.fields["parent"].to_field_name = "uuid"
        # Seule l'unité racine (créée à l'installation) n'a pas de parent.
        self.fields["parent"].required = not (self.instance.pk and self.instance.parent_id is None)


class FormulaireTypeUnite(forms.ModelForm):
    class Meta:
        model = TypeUnite
        fields = ["code", "libelle_fr", "libelle_ar", "ordre", "actif"]


class FormulairePoste(forms.ModelForm):
    class Meta:
        model = Poste
        fields = ["unite", "intitule_fr", "intitule_ar", "superieur", "actif"]

    def __init__(self, *args, acteur, **kwargs):
        super().__init__(*args, **kwargs)
        self.instance.institution_id = acteur.institution_id
        self.fields["unite"].queryset = moteur.unites_autorisees(acteur, "administration.organisation").filter(
            actif=True
        )
        self.fields["unite"].to_field_name = "uuid"
        superieurs = Poste.objects.filter(institution_id=acteur.institution_id, actif=True).select_related("unite")
        if self.instance.pk:
            superieurs = superieurs.exclude(pk=self.instance.pk)
        self.fields["superieur"].queryset = superieurs


class FormulaireProfilUtilisateur(forms.ModelForm):
    class Meta:
        model = Utilisateur
        fields = ["nom", "prenom", "nom_ar", "courriel", "langue", "niveau_habilitation"]


class FormulaireCreationUtilisateur(FormulaireProfilUtilisateur):
    mot_de_passe_temporaire = forms.CharField(
        label=_("Mot de passe temporaire"),
        help_text=_("À communiquer à la personne ; il devra être changé à la première connexion."),
        widget=forms.TextInput(attrs={"autocomplete": "off", "dir": "ltr"}),
    )
    unite = forms.ModelChoiceField(
        label=_("Unité"), queryset=UniteOrganisationnelle.objects.none(), required=False, to_field_name="uuid"
    )
    role = forms.ModelChoiceField(label=_("Rôle"), queryset=Role.objects.none(), required=False, to_field_name="uuid")

    class Meta(FormulaireProfilUtilisateur.Meta):
        fields = ["identifiant", *FormulaireProfilUtilisateur.Meta.fields]

    def __init__(self, *args, acteur, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["unite"].queryset = moteur.unites_autorisees(acteur, "administration.utilisateurs").filter(
            actif=True
        )
        self.fields["role"].queryset = Role.objects.filter(institution_id=acteur.institution_id, actif=True)
        if not self.is_bound:
            self.initial["mot_de_passe_temporaire"] = generer_mot_de_passe()

    def clean(self):
        donnees = super().clean()
        if bool(donnees.get("unite")) != bool(donnees.get("role")):
            raise forms.ValidationError(_("Indiquez à la fois l'unité et le rôle, ou aucun des deux."))
        return donnees


class FormulaireAffectation(forms.ModelForm):
    class Meta:
        model = Affectation
        fields = ["unite", "role", "poste", "etendue_sous_unites", "date_debut", "date_fin"]
        widgets = {
            "date_debut": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
            "date_fin": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
        }

    def __init__(self, *args, acteur, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["unite"].queryset = moteur.unites_autorisees(acteur, "administration.utilisateurs").filter(
            actif=True
        )
        self.fields["role"].queryset = Role.objects.filter(institution_id=acteur.institution_id, actif=True)
        self.fields["poste"].queryset = Poste.objects.filter(institution_id=acteur.institution_id, actif=True)
        self.fields["unite"].to_field_name = "uuid"
        self.fields["role"].to_field_name = "uuid"


class FormulaireMotif(forms.Form):
    motif = forms.CharField(label=_("Motif"), max_length=255)


class FormulaireRole(forms.ModelForm):
    permissions = forms.ModelMultipleChoiceField(
        label=_("Permissions"),
        queryset=Permission.objects.filter(actif=True),
        required=False,
        widget=forms.CheckboxSelectMultiple,
        to_field_name="code",
    )

    class Meta:
        model = Role
        fields = ["code", "libelle_fr", "libelle_ar", "description", "mfa_requis", "actif", "permissions"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["permissions"].label_from_instance = lambda p: f"{p.description} ({p.code})"
        if self.instance.systeme:
            self.fields["code"].disabled = True
