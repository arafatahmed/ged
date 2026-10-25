"""Opérations du noyau : institution, paramètres, numérotation.

Chaque opération modifiante journalise son événement d'audit dans la même
transaction : l'événement n'existe que si l'opération a réussi.
"""

import zoneinfo

from django.core.exceptions import ValidationError
from django.db import connection, transaction
from django.utils import timezone
from django.utils.translation import gettext as _

from audit.services import journaliser

from . import numerotation
from .models import CompteurSerie, Institution, ParametreInstitution
from .parametres import CATALOGUE
from .signals import institution_creee


def institution_unique():
    """Institution de l'installation en mode mono-institution."""
    return Institution.objects.filter(actif=True).order_by("id").first()


@transaction.atomic
def creer_institution(*, acteur=None, requete=None, **champs):
    institution = Institution(**champs)
    institution.full_clean()
    institution.save()
    institution_creee.send(sender=Institution, institution=institution)
    journaliser(
        "institution.creation",
        acteur=acteur,
        objet=institution,
        requete=requete,
        details={"code": institution.code, "nom_fr": institution.nom_fr},
    )
    return institution


def lire_parametre(institution, cle):
    definition = CATALOGUE[cle]
    valeur = (
        ParametreInstitution.objects.filter(institution=institution, cle=cle).values_list("valeur", flat=True).first()
    )
    return definition.defaut if valeur is None else valeur


@transaction.atomic
def definir_parametre(institution, cle, valeur, *, acteur=None, requete=None):
    definition = CATALOGUE.get(cle)
    if definition is None:
        raise ValidationError(_("Paramètre inconnu : %(cle)s.") % {"cle": cle})
    definition.valider(valeur)
    parametre = ParametreInstitution.objects.select_for_update().filter(institution=institution, cle=cle).first()
    ancienne = parametre.valeur if parametre else definition.defaut
    if parametre is None:
        parametre = ParametreInstitution(institution=institution, cle=cle)
    parametre.valeur = valeur
    parametre.modifie_par = acteur
    parametre.save()
    journaliser(
        "parametre.modification",
        acteur=acteur,
        institution=institution,
        objet=parametre,
        requete=requete,
        details={"cle": cle, "avant": ancienne, "apres": valeur},
    )
    return parametre


def attribuer_numero(serie, *, unite="", categorie="", date=None):
    """Attribue le numéro suivant d'une série et renvoie la référence formatée.

    Doit être appelé dans la transaction qui crée l'objet numéroté : la ligne
    du compteur reste verrouillée jusqu'à la fin de cette transaction, donc deux
    enregistrements simultanés ne peuvent pas obtenir le même numéro, et un
    échec de la transaction rend le numéro (pas de trou).
    """
    if not connection.in_atomic_block:
        raise RuntimeError("attribuer_numero doit être appelé dans la transaction qui crée l'objet.")
    if not serie.actif:
        raise ValidationError(_("La série %(code)s est inactive.") % {"code": serie.code})
    if serie.par_unite or "{UNITE}" in serie.gabarit:
        numerotation.verifier_code_contexte(unite, _("d'unité"))
    if serie.par_categorie or "{CATEGORIE}" in serie.gabarit:
        numerotation.verifier_code_contexte(categorie, _("de catégorie"))
    institution = serie.institution
    if date is None:
        date = timezone.localdate(timezone=zoneinfo.ZoneInfo(institution.fuseau_horaire))

    cle = serie.cle_portee(date=date, unite=unite, categorie=categorie)
    CompteurSerie.objects.bulk_create([CompteurSerie(serie=serie, cle_portee=cle)], ignore_conflicts=True)
    compteur = CompteurSerie.objects.select_for_update().get(serie=serie, cle_portee=cle)
    compteur.valeur += 1
    compteur.save(update_fields=["valeur"])
    return numerotation.formater(
        serie.gabarit,
        sequence=compteur.valeur,
        date=date,
        sigle=institution.sigle,
        unite=unite,
        categorie=categorie,
    )
