import zoneinfo

from django.conf import settings
from django.utils import timezone, translation

from .services import institution_unique


class InstitutionMiddleware:
    """Rattache la requête à son institution, active son fuseau et sa langue.

    Langue : choix explicite de l'utilisateur (cookie), sinon sa préférence,
    sinon la langue par défaut de l'institution.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        utilisateur = request.user
        if utilisateur.is_authenticated:
            institution = utilisateur.institution
        elif not settings.GED_MULTI_INSTITUTIONS:
            institution = institution_unique()
        else:
            institution = None
        request.institution = institution

        fuseau = zoneinfo.ZoneInfo(institution.fuseau_horaire) if institution is not None else None
        langue = translation.get_language()
        demandee = request.headers.get("X-Langue", "")
        if demandee in dict(settings.LANGUAGES):
            # Langue choisie dans le frontend, transmise à chaque appel d'API.
            langue = demandee
            request.LANGUAGE_CODE = demandee
        elif not request.COOKIES.get(settings.LANGUAGE_COOKIE_NAME):
            preference = getattr(utilisateur, "langue", "") or (institution.langue_defaut if institution else "")
            if preference:
                langue = preference
                request.LANGUAGE_CODE = preference

        # Fuseau et langue ne valent que pour cette requête (rendu compris), puis sont restaurés.
        with timezone.override(fuseau), translation.override(langue):
            reponse = self.get_response(request)
        reponse.headers["Content-Language"] = langue
        return reponse
