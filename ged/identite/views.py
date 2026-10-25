"""Seule vue non API du module : la connexion de l'administration technique renvoie vers le frontend."""

from urllib.parse import urlencode

from django.conf import settings
from django.shortcuts import redirect


def connexion_administration_technique(request, extra_context=None):
    """L'administration technique passe par la connexion de l'application (double authentification comprise)."""
    if request.user.is_authenticated:
        return redirect("/")
    return redirect(f"{settings.LOGIN_URL}?{urlencode({'suivant': request.GET.get('next', '/')})}")
