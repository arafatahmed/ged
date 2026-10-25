import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

from audit.models import JournalAudit
from noyau.models import Institution


@pytest.mark.django_db
class TestInitialisation:
    def test_creation_puis_idempotence(self, capsys):
        arguments = ["--code", "min", "--nom-fr", "Ministère", "--nom-ar", "وزارة", "--sigle", "MIN"]
        call_command("initialiser_ged", *arguments, "--fuseau", "Africa/Nouakchott", "--langue", "ar")
        institution = Institution.objects.get(code="min")
        assert institution.langue_defaut == "ar"
        assert institution.fuseau_horaire == "Africa/Nouakchott"
        call_command("initialiser_ged", *arguments)
        assert "existe déjà" in capsys.readouterr().out
        assert JournalAudit.objects.filter(action="institution.creation").count() == 1

    def test_valeurs_invalides(self):
        with pytest.raises(CommandError, match="Fuseau"):
            call_command("initialiser_ged", "--code", "min", "--nom-fr", "M", "--sigle", "M", "--fuseau", "Lune/Base")


def test_preparer_stockage_local(capsys, settings):
    settings.GED_S3_ENDPOINT = ""
    call_command("preparer_stockage")
    assert "rien à préparer" in capsys.readouterr().out
