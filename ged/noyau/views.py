from django.db import DatabaseError, connection
from django.http import Http404, HttpResponse, JsonResponse
from django.views.decorators.cache import cache_control
from django.views.decorators.http import require_GET

from .validators import type_image


@require_GET
def sante(request):
    """Sonde de supervision : vérifie seulement l'accès à la base, sans rien divulguer."""
    try:
        with connection.cursor() as curseur:
            curseur.execute("SELECT 1")
    except DatabaseError:
        return JsonResponse({"statut": "indisponible"}, status=503)
    return JsonResponse({"statut": "ok"})


@require_GET
@cache_control(public=True, max_age=3600)
def logo_institution(request):
    """Sert le logo depuis le stockage privé (affiché aussi sur la page de connexion)."""
    institution = request.institution
    if institution is None or not institution.logo:
        raise Http404
    with institution.logo.open("rb") as fichier:
        contenu = fichier.read()
    type_mime = type_image(contenu[:8])
    if type_mime is None:
        raise Http404
    reponse = HttpResponse(contenu, content_type=type_mime)
    reponse["Content-Security-Policy"] = "default-src 'none'"
    return reponse
