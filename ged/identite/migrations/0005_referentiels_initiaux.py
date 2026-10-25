"""Permissions du catalogue, rôles et types d'unité initiaux pour les institutions existantes."""

from django.db import migrations

from identite.catalogue import creer_referentiels_initiaux


def creer(apps, schema_editor):
    Institution = apps.get_model("noyau", "Institution")
    Role = apps.get_model("identite", "Role")
    Permission = apps.get_model("identite", "Permission")
    TypeUnite = apps.get_model("organisation", "TypeUnite")
    for institution in Institution.objects.all():
        creer_referentiels_initiaux(institution, Role, Permission, TypeUnite)


class Migration(migrations.Migration):
    dependencies = [
        ("identite", "0004_affectation_poste_affectation_unite_and_more"),
        ("organisation", "0001_initial"),
    ]

    operations = [migrations.RunPython(creer, migrations.RunPython.noop)]
