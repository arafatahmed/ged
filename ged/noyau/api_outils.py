"""Outils communs aux points d'API : format des erreurs, pagination, permissions."""

import functools

from django.core.exceptions import PermissionDenied
from django.core.exceptions import ValidationError as ValidationDjango
from django.core.paginator import Paginator
from drf_spectacular.openapi import AutoSchema
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import exception_handler

PAR_PAGE = 25


def erreurs_validation(erreur):
    """Convertit une ValidationError Django en {champ: [messages]} (« __all__ » pour les erreurs générales)."""
    if hasattr(erreur, "error_dict"):
        return {champ: [m for e in liste for m in e.messages] for champ, liste in erreur.error_dict.items()}
    return {"__all__": list(erreur.messages)}


def reponse_erreurs(erreurs, code=status.HTTP_400_BAD_REQUEST):
    """Format unique des erreurs : {"detail": premier message, "erreurs": {champ: [messages]}}."""
    premier = next((m for messages in erreurs.values() for m in messages), "")
    return Response({"detail": premier, "erreurs": erreurs}, status=code)


def erreurs_formulaire(formulaire):
    return reponse_erreurs(
        {champ: [e["message"] for e in liste] for champ, liste in formulaire.errors.get_json_data().items()}
    )


def gestionnaire_exceptions(exc, contexte):
    """Ajoute aux erreurs gérées par DRF les ValidationError levées par les services métier."""
    if isinstance(exc, ValidationDjango):
        return reponse_erreurs(erreurs_validation(exc))
    return exception_handler(exc, contexte)


def paginer(request, requete, serialiser):
    page = Paginator(requete, PAR_PAGE).get_page(request.query_params.get("page"))
    return {
        "nombre": page.paginator.count,
        "page": page.number,
        "pages": page.paginator.num_pages,
        "resultats": [serialiser(objet) for objet in page],
    }


def permission_requise(code, *, portee_institution=False):
    """Refuse (403, journalisé) l'appel sans la permission, n'importe où ou sur toute l'institution."""
    from acces import moteur

    def decorateur(vue):
        @functools.wraps(vue)
        def enveloppe(request, *args, **kwargs):
            autorise = (
                moteur.portee_institution(request.user, code)
                if portee_institution
                else moteur.a_permission(request.user, code)
            )
            if not autorise:
                moteur.refuser(request.user, code, requete=request, details={"api": request.path})
            return vue(request, *args, **kwargs)

        return enveloppe

    return decorateur


__all__ = ["PermissionDenied"]


# Les points d'API fonctionnels échangent des objets JSON décrits dans les docstrings et le
# frontend (core/modeles.ts) : le schéma OpenAPI les déclare comme objets génériques.
documenter = extend_schema(request=OpenApiTypes.OBJECT, responses=OpenApiTypes.OBJECT)


class SchemaGed(AutoSchema):
    """Identifiants d'opération tirés du nom de la vue (uniques), plutôt que du chemin."""

    def get_operation_id(self):
        # Pour une vue @api_view, DRF donne à la classe générée le nom de la fonction.
        return f"{self.view.__class__.__name__}_{self.method.lower()}"
