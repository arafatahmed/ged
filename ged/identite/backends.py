"""Authentification par identifiant et mot de passe, avec verrouillage et limitation par adresse IP."""

import datetime

from django.contrib.auth.backends import ModelBackend
from django.core.cache import cache
from django.db import transaction
from django.utils import timezone

from audit.models import Resultat
from audit.services import adresse_ip, journaliser
from noyau.services import lire_parametre

from .models import Utilisateur

# Au-delà de ce nombre d'échecs depuis une même adresse en 15 minutes, toute tentative est refusée.
MAX_ECHECS_PAR_IP = 50
FENETRE_IP_SECONDES = 15 * 60


def cle_ip(requete):
    return f"connexion:echecs:{adresse_ip(requete) or 'inconnue'}"


def ip_bloquee(requete):
    return requete is not None and cache.get(cle_ip(requete), 0) >= MAX_ECHECS_PAR_IP


def compter_echec_ip(requete):
    if requete is None:
        return
    cle = cle_ip(requete)
    cache.add(cle, 0, FENETRE_IP_SECONDES)
    try:
        cache.incr(cle)
    except ValueError:
        cache.set(cle, 1, FENETRE_IP_SECONDES)


def enregistrer_echec(utilisateur, requete, *, motif):
    """Compte un échec sur le compte et le verrouille au seuil configuré."""
    with transaction.atomic():
        compte = Utilisateur.objects.select_for_update().get(pk=utilisateur.pk)
        compte.echecs_connexion += 1
        champs = ["echecs_connexion"]
        institution = compte.institution
        seuil = lire_parametre(institution, "connexion.seuil_verrouillage") if institution else 10
        if compte.echecs_connexion >= seuil and not compte.est_verrouille():
            minutes = lire_parametre(institution, "connexion.duree_verrouillage_minutes") if institution else 30
            compte.verrouille_jusqu_a = timezone.now() + datetime.timedelta(minutes=minutes)
            champs.append("verrouille_jusqu_a")
            journaliser(
                "compte.verrouillage",
                objet=compte,
                acteur_libelle=compte.identifiant,
                requete=requete,
                resultat=Resultat.REFUS,
                details={"echecs": compte.echecs_connexion, "minutes": minutes, "motif": motif},
            )
        compte.save(update_fields=champs)


def remettre_a_zero(utilisateur):
    if utilisateur.echecs_connexion or utilisateur.verrouille_jusqu_a:
        Utilisateur.objects.filter(pk=utilisateur.pk).update(echecs_connexion=0, verrouille_jusqu_a=None)


class BackendGed(ModelBackend):
    def authenticate(self, request, username=None, password=None, **kwargs):
        if ip_bloquee(request):
            journaliser(
                "connexion.ip_bloquee",
                acteur_libelle=str(username or "")[:150],
                requete=request,
                resultat=Resultat.REFUS,
            )
            return None
        utilisateur = super().authenticate(request, username=username, password=password, **kwargs)
        compte = Utilisateur.objects.filter(identifiant=username).first() if username else None
        if utilisateur is None:
            compter_echec_ip(request)
            if compte is not None and compte.is_active:
                enregistrer_echec(compte, request, motif="mot_de_passe")
            return None
        if utilisateur.est_verrouille():
            # Bon mot de passe pendant le verrouillage : refus sans le révéler.
            journaliser(
                "connexion.refus_verrouille",
                objet=utilisateur,
                acteur_libelle=utilisateur.identifiant,
                requete=request,
                resultat=Resultat.REFUS,
            )
            return None
        return utilisateur

    def user_can_authenticate(self, user):
        if not super().user_can_authenticate(user):
            return False
        return user.is_superuser or (user.institution is not None and user.institution.actif)
