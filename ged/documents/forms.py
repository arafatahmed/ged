from django import forms
from django.utils.translation import gettext_lazy as _

from acces import documents as acces
from identite.models import NiveauHabilitation

from .models import DefinitionMetadonnee, NatureRelation, TypeDocument


class ListeJson(forms.JSONField):
    """Champ JSON dont la liste vide reste une liste (et non None)."""

    def clean(self, value):
        valeur = super().clean(value)
        return [] if valeur is None else valeur


class FormulaireTypeDocument(forms.ModelForm):
    formats_autorises = ListeJson(required=False)

    class Meta:
        model = TypeDocument
        fields = [
            "code",
            "libelle_fr",
            "libelle_ar",
            "categorie",
            "formats_autorises",
            "confidentialite_defaut",
            "actif",
        ]


class FormulaireDefinition(forms.ModelForm):
    valeurs_liste = ListeJson(required=False)

    class Meta:
        model = DefinitionMetadonnee
        fields = ["code", "libelle_fr", "libelle_ar", "nature", "obligatoire", "valeurs_liste", "ordre", "actif"]

    def validate_unique(self):
        # L'unicité (type, code) est vérifiée par le service, qui rapproche les définitions par code.
        pass


class FormulaireDocument(forms.Form):
    """Création d'un document (multipart : métadonnées et mots-clés en JSON)."""

    type = forms.ModelChoiceField(queryset=TypeDocument.objects.none(), to_field_name="uuid", label=_("type"))
    unite_proprietaire = forms.ModelChoiceField(queryset=None, to_field_name="uuid", label=_("unité propriétaire"))
    titre = forms.CharField(max_length=500, label=_("titre"))
    objet = forms.CharField(required=False, label=_("objet"))
    date_document = forms.DateField(required=False, label=_("date du document"))
    confidentialite = forms.TypedChoiceField(
        choices=NiveauHabilitation.choices, coerce=int, required=False, empty_value=None, label=_("confidentialité")
    )
    mots_cles = forms.JSONField(required=False, label=_("mots-clés"))
    metadonnees = forms.JSONField(required=False, label=_("métadonnées"))
    commentaire = forms.CharField(required=False, label=_("commentaire"))
    fichier = forms.FileField(required=False, allow_empty_file=True, label=_("fichier"))

    def __init__(self, *args, acteur, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["type"].queryset = TypeDocument.objects.filter(institution_id=acteur.institution_id, actif=True)
        self.fields["unite_proprietaire"].queryset = acces.unites_de_creation(acteur)


class FormulaireModificationDocument(forms.Form):
    """Modification partielle : seuls les champs présents dans la requête sont validés et appliqués."""

    titre = forms.CharField(max_length=500)
    objet = forms.CharField(required=False)
    date_document = forms.DateField(required=False)
    confidentialite = forms.TypedChoiceField(choices=NiveauHabilitation.choices, coerce=int)
    mots_cles = forms.JSONField(required=False)
    metadonnees = forms.JSONField(required=False)

    def __init__(self, data, **kwargs):
        super().__init__(data, **kwargs)
        for nom in list(self.fields):
            if nom not in data:
                del self.fields[nom]


class FormulaireVersion(forms.Form):
    fichier = forms.FileField(allow_empty_file=True, label=_("fichier"))
    commentaire = forms.CharField(required=False, label=_("commentaire"))


class FormulaireRelation(forms.Form):
    cible = forms.UUIDField(label=_("document lié"))
    nature = forms.ChoiceField(choices=NatureRelation.choices, label=_("nature"))
