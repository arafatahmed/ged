from django.urls import path

from . import views

urlpatterns = [
    path("sante/", views.sante, name="sante"),
    path("institution/logo/", views.logo_institution, name="logo_institution"),
]
