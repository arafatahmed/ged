"""Cases « P » de la matrice : permissions « _propres » pour les rôles modèles existants.

Seuls les rôles modèles (systeme) qui détiennent encore la permission complète sont
modifiés ; un rôle déjà personnalisé par l'institution reste tel quel.
"""

from django.db import migrations

from identite.catalogue import synchroniser_permissions

REMPLACEMENTS = {
    "bureau_ordre": ["document.modifier"],
    "producteur": ["document.telecharger", "document.modifier", "document.versionner"],
}


def appliquer(apps, schema_editor):
    Role = apps.get_model("identite", "Role")
    Permission = apps.get_model("identite", "Permission")
    synchroniser_permissions(Permission)
    for code_role, codes in REMPLACEMENTS.items():
        for role in Role.objects.filter(code=code_role, systeme=True):
            for code in codes:
                complete = role.permissions.filter(code=code).first()
                if complete is not None:
                    role.permissions.remove(complete)
                    role.permissions.add(Permission.objects.get(code=f"{code}_propres"))


class Migration(migrations.Migration):
    dependencies = [("identite", "0005_referentiels_initiaux")]

    operations = [migrations.RunPython(appliquer, migrations.RunPython.noop)]
