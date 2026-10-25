"""Journalisation des connexions et suivi des sessions ; référentiels des nouvelles institutions."""

from django.contrib.auth.signals import user_logged_in, user_logged_out, user_login_failed
from django.dispatch import receiver
from django.utils import timezone

from audit.models import Resultat
from audit.services import adresse_ip, journaliser
from noyau.signals import institution_creee


@receiver(user_logged_in)
def connexion_reussie(sender, request, user, **kwargs):
    from .backends import remettre_a_zero
    from .models import SessionUtilisateur

    remettre_a_zero(user)
    if request is not None and request.session.session_key:
        SessionUtilisateur.objects.update_or_create(
            cle_session=request.session.session_key,
            defaults={
                "utilisateur": user,
                "adresse_ip": adresse_ip(request),
                "agent": request.META.get("HTTP_USER_AGENT", "")[:255],
                "fin": None,
                "motif_fin": "",
            },
        )
    journaliser("connexion.reussie", acteur=user, objet=user, requete=request)


@receiver(user_logged_out)
def deconnexion(sender, request, user, **kwargs):
    from .models import SessionUtilisateur

    if user is None:
        return
    motif = getattr(request, "_motif_deconnexion", SessionUtilisateur.MotifFin.DECONNEXION)
    if request is not None and request.session.session_key:
        SessionUtilisateur.objects.filter(cle_session=request.session.session_key, fin__isnull=True).update(
            fin=timezone.now(), motif_fin=motif
        )
    action = "deconnexion" if motif == SessionUtilisateur.MotifFin.DECONNEXION else f"deconnexion.{motif}"
    journaliser(action, acteur=user, objet=user, requete=request)


@receiver(user_login_failed)
def connexion_echouee(sender, credentials, request=None, **kwargs):
    # Seul l'identifiant saisi est conservé, jamais le mot de passe.
    from .models import Utilisateur

    identifiant = str(credentials.get("identifiant") or credentials.get("username") or "")[:150]
    compte = Utilisateur.objects.filter(identifiant=identifiant).only("institution_id").first()
    journaliser(
        "connexion.echec",
        institution=compte.institution if compte else None,
        acteur_libelle=identifiant,
        resultat=Resultat.REFUS,
        details={"identifiant_saisi": identifiant},
        requete=request,
    )


@receiver(institution_creee)
def initialiser_referentiels(sender, institution, **kwargs):
    """Permissions, rôles et types d'unité initiaux, puis unité racine de la nouvelle institution."""
    from organisation.models import TypeUnite
    from organisation.services import creer_unite_racine

    from .catalogue import creer_referentiels_initiaux
    from .models import Permission, Role

    creer_referentiels_initiaux(institution, Role, Permission, TypeUnite)
    creer_unite_racine(institution)


def synchroniser_catalogue(sender, apps=None, **kwargs):
    """Après chaque migration, aligne la table des permissions sur le catalogue du code."""
    from django.apps import apps as applications

    from .catalogue import synchroniser_permissions

    apps = apps or applications
    try:
        Permission = apps.get_model("identite", "Permission")
    except LookupError:  # migration vers un état antérieur au lot 2
        return
    synchroniser_permissions(Permission)
