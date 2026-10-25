from django.urls import path

from .api import InstitutionCouranteView

urlpatterns = [
    path("institution/", InstitutionCouranteView.as_view(), name="api_institution"),
]
