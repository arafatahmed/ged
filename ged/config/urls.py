"""Routes servies par Django : API, administration technique, sonde et logo.

Toutes les autres adresses (/, /connexion, /administration…) appartiennent au
frontend Angular, servi par Nginx en production et par « ng serve » en développement.
"""

from django.conf import settings
from django.contrib import admin
from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView

from identite.views import connexion_administration_technique

# L'administration technique n'a pas sa propre page de connexion : elle passe par
# celle de l'application, qui impose la double authentification.
admin.site.login = connexion_administration_technique

urlpatterns = [
    path(settings.GED_ADMIN_URL, admin.site.urls),
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path("api/v1/", include("config.api_urls")),
    path("", include("noyau.urls")),
]
