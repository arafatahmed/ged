"""Contrôles de session : expiration d'inactivité et mise en conformité du compte.

Pour l'API, les refus sont des réponses JSON avec un code que le frontend
interprète (session expirée, mot de passe à changer, double authentification à
activer). Pour l'administration technique, ce sont des redirections vers les
pages correspondantes du frontend.
"""

import time

from django.conf import settings
from django.contrib.auth import logout
from django.http import JsonResponse
from django.shortcuts import redirect
from django.utils.translation import gettext as _

from noyau.services import lire_parametre

from . import mfa
from .models import SessionUtilisateur

CLE_ACTIVITE = "derniere_activite"
# La date de dernière activité n'est réécrite qu'au plus une fois par minute.
INTERVALLE_ECRITURE = 60
PREFIXES_TOUJOURS_PERMIS = ("/static/", "/sante/", "/institution/", "/api/v1/session/")
API_MOT_DE_PASSE = "/api/v1/compte/mot-de-passe/"
API_ENROLEMENT = "/api/v1/session/enrolement/"
PAGE_MOT_DE_PASSE = "/compte/mot-de-passe"
PAGE_ENROLEMENT = "/compte/double-authentification"


class SecuriteSessionMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        utilisateur = request.user
        if utilisateur.is_authenticated:
            reponse = self._controler(request, utilisateur)
            if reponse is not None:
                return reponse
        return self.get_response(request)

    def _controler(self, request, utilisateur):
        api = request.path.startswith("/api/")
        maintenant = time.time()
        institution = utilisateur.institution
        limite = 60 * (lire_parametre(institution, "session.inactivite_minutes") if institution else 30)
        derniere = request.session.get(CLE_ACTIVITE)
        if derniere and maintenant - derniere > limite:
            request._motif_deconnexion = SessionUtilisateur.MotifFin.INACTIVITE
            logout(request)
            if api:
                message = _("Votre session a expiré après une période d'inactivité.")
                return JsonResponse({"detail": message, "code": "session_expiree"}, status=401)
            return redirect(f"{settings.LOGIN_URL}?expiree=1")
        if not derniere or maintenant - derniere > INTERVALLE_ECRITURE:
            request.session[CLE_ACTIVITE] = maintenant

        if request.path.startswith(PREFIXES_TOUJOURS_PERMIS):
            return None
        if utilisateur.doit_changer_mot_de_passe and request.path != API_MOT_DE_PASSE:
            return self._exiger(
                api, "changement_mot_de_passe_requis", _("Changez votre mot de passe temporaire."), PAGE_MOT_DE_PASSE
            )
        if not utilisateur.doit_changer_mot_de_passe and not utilisateur.mfa_active and mfa.mfa_requise(utilisateur):
            if request.path != API_ENROLEMENT:
                return self._exiger(api, "mfa_requise", _("Activez la double authentification."), PAGE_ENROLEMENT)
        return None

    @staticmethod
    def _exiger(api, code, message, page):
        if api:
            return JsonResponse({"detail": message, "code": code}, status=403)
        return redirect(page)
