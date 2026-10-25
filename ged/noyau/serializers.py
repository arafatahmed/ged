from rest_framework import serializers

from .models import Institution


class InstitutionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Institution
        fields = [
            "uuid",
            "code",
            "nom_fr",
            "nom_ar",
            "sigle",
            "couleur_primaire",
            "couleur_secondaire",
            "adresse",
            "telephone",
            "courriel",
            "site_web",
            "fuseau_horaire",
            "langue_defaut",
            "format_date",
        ]
        read_only_fields = fields
