from django.contrib.auth.forms import BaseUserCreationForm, UserChangeForm

from .models import Utilisateur


class FormulaireCreationUtilisateur(BaseUserCreationForm):
    class Meta:
        model = Utilisateur
        fields = ("identifiant", "nom", "prenom", "institution")


class FormulaireModificationUtilisateur(UserChangeForm):
    class Meta:
        model = Utilisateur
        fields = "__all__"
