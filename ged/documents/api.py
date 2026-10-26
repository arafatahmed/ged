"""API des documents et de l'administration des types de documents.

Un document hors du périmètre répond 404, comme un document inexistant ; une
action refusée sur un document visible répond 403 et laisse une trace
`acces.refus`. Les clés du stockage ne sont jamais transmises : les fichiers
passent uniquement par les points de téléchargement et d'aperçu.
"""

from django.db.models import Count, Prefetch, Q
from django.http import FileResponse
from django.shortcuts import get_object_or_404
from django.utils.translation import gettext as _
from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.response import Response

from acces import documents as acces
from identite.models import NiveauHabilitation
from noyau.api_outils import documenter, erreurs_formulaire, paginer, permission_requise, reponse_erreurs
from noyau.services import lire_parametre

from . import services
from .formats import FORMATS
from .forms import (
    FormulaireDefinition,
    FormulaireDocument,
    FormulaireModificationDocument,
    FormulaireRelation,
    FormulaireTypeDocument,
    FormulaireVersion,
)
from .models import Document, FichierDocument, NatureRelation, RelationDocument, StatutDocument, TypeDocument

# --- Représentations -------------------------------------------------------------


def _definition(definition):
    return {
        "code": definition.code,
        "libelle_fr": definition.libelle_fr,
        "libelle_ar": definition.libelle_ar,
        "nature": definition.nature,
        "obligatoire": definition.obligatoire,
        "valeurs_liste": definition.valeurs_liste,
        "ordre": definition.ordre,
        "actif": definition.actif,
    }


def _type_document(type_document, *, inactives=False):
    definitions = [d for d in type_document.definitions.all() if inactives or d.actif]
    return {
        "uuid": str(type_document.uuid),
        "code": type_document.code,
        "libelle_fr": type_document.libelle_fr,
        "libelle_ar": type_document.libelle_ar,
        "categorie": type_document.categorie,
        "formats_autorises": type_document.formats_autorises,
        "confidentialite_defaut": type_document.confidentialite_defaut,
        "actif": type_document.actif,
        "metadonnees": [_definition(d) for d in definitions],
        "documents": getattr(type_document, "nombre_documents", None),
    }


def _personne(utilisateur):
    return utilisateur.get_full_name() if utilisateur else None


def _fichier(fichier):
    return {
        "uuid": str(fichier.uuid),
        "role": fichier.role,
        "nom": fichier.nom_origine,
        "format": fichier.format,
        "format_libelle": FORMATS[fichier.format].libelle,
        "type_mime": fichier.type_mime,
        "taille": fichier.taille,
        "sha256": fichier.sha256,
        "etat": fichier.etat_analyse,
        "motif": fichier.motif,
        "apercu": fichier.apercu_possible,
        "depose_le": fichier.depose_le,
        "depose_par": _personne(fichier.depose_par),
    }


def _principal(version):
    return next((f for f in version.fichiers.all() if f.role == "principal"), None) if version else None


def _resume(document):
    principal = _principal(document.version_courante)
    return {
        "uuid": str(document.uuid),
        "reference": document.reference,
        "titre": document.titre,
        "type_libelle": document.type.libelle_fr,
        "type_libelle_ar": document.type.libelle_ar,
        "unite_libelle": document.unite_proprietaire.libelle_fr,
        "unite_libelle_ar": document.unite_proprietaire.libelle_ar,
        "confidentialite": document.confidentialite,
        "statut": document.statut,
        "date_document": document.date_document,
        "cree_le": document.cree_le,
        "cree_par": _personne(document.cree_par),
        "version": document.version_courante.numero if document.version_courante_id else None,
        "fichier": {"format": principal.format, "etat": principal.etat_analyse} if principal else None,
    }


def _lien(document):
    return {"uuid": str(document.uuid), "reference": document.reference, "titre": document.titre}


def _detail(acteur, document):
    droits = acces.droits(acteur, document)
    visibles = set(
        acces.filtrer_visibles(
            acteur,
            Document.objects.filter(Q(relations_entrantes__source=document) | Q(relations_sortantes__cible=document)),
        ).values_list("pk", flat=True)
    )
    relations = [
        {"id": r.pk, "nature": r.nature, "sens": "sortante", "document": _lien(r.cible)}
        for r in document.relations_sortantes.select_related("cible")
        if r.cible_id in visibles
    ] + [
        {"id": r.pk, "nature": r.nature, "sens": "entrante", "document": _lien(r.source)}
        for r in document.relations_entrantes.select_related("source")
        if r.source_id in visibles
    ]
    versions = document.versions.select_related("creee_par").prefetch_related(
        Prefetch("fichiers", queryset=FichierDocument.objects.select_related("depose_par"))
    )
    return {
        **_resume(document),
        "objet": document.objet,
        "mots_cles": document.mots_cles,
        "metadonnees": document.metadonnees,
        "type": _type_document(document.type),
        "unite": str(document.unite_proprietaire.uuid),
        "modifie_le": document.modifie_le,
        "modifie_par": _personne(document.modifie_par),
        "droits": droits,
        "versions": [
            {
                "numero": v.numero,
                "commentaire": v.commentaire,
                "statut": v.statut,
                "creee_le": v.creee_le,
                "creee_par": _personne(v.creee_par),
                "courante": v.pk == document.version_courante_id,
                "fichiers": [_fichier(f) for f in v.fichiers.all()],
            }
            for v in versions
        ],
        "relations": relations,
        "doublons": [_lien(d) for d in services.doublons_visibles(acteur, document)[:10]],
    }


# --- Documents -------------------------------------------------------------------


def _requete_documents():
    return Document.objects.select_related(
        "type", "unite_proprietaire", "cree_par", "modifie_par", "version_courante"
    ).prefetch_related("version_courante__fichiers", "type__definitions")


def _document_visible(request, uuid):
    return get_object_or_404(acces.filtrer_visibles(request.user, _requete_documents()), uuid=uuid)


@documenter
@api_view(["GET", "POST"])
def documents(request):
    """Liste des documents visibles (filtres q, type, unite, statut, confidentialite) ; création (multipart)."""
    acteur = request.user
    if request.method == "POST":
        formulaire = FormulaireDocument(request.data, request.FILES, acteur=acteur)
        if not formulaire.is_valid():
            return erreurs_formulaire(formulaire)
        donnees = formulaire.cleaned_data
        document = services.creer_document(
            acteur,
            type_document=donnees["type"],
            unite_proprietaire=donnees["unite_proprietaire"],
            titre=donnees["titre"],
            objet=donnees["objet"],
            date_document=donnees["date_document"],
            confidentialite=donnees["confidentialite"],
            mots_cles=donnees["mots_cles"],
            metadonnees=donnees["metadonnees"],
            fichier=donnees["fichier"],
            commentaire=donnees["commentaire"],
            requete=request,
        )
        return Response(_detail(acteur, _requete_documents().get(pk=document.pk)), status=status.HTTP_201_CREATED)

    requete = acces.filtrer_visibles(acteur, _requete_documents())
    filtres = request.query_params
    if texte := filtres.get("q", "").strip():
        requete = requete.filter(
            Q(titre__icontains=texte)
            | Q(reference__icontains=texte)
            | Q(objet__icontains=texte)
            | Q(mots_cles__contains=[texte])
        )
    if filtres.get("type"):
        requete = requete.filter(type__uuid=filtres["type"])
    if filtres.get("unite"):
        requete = requete.filter(unite_proprietaire__uuid=filtres["unite"])
    if filtres.get("statut") in StatutDocument.values:
        requete = requete.filter(statut=filtres["statut"])
    if filtres.get("confidentialite", "").isdigit():
        requete = requete.filter(confidentialite=int(filtres["confidentialite"]))
    tri = {"titre": "titre", "-titre": "-titre", "date": "date_document", "-date": "-date_document"}
    requete = requete.order_by(tri.get(filtres.get("tri"), "-cree_le"), "-pk")
    return Response(paginer(request, requete, _resume))


@documenter
@api_view(["GET"])
def options(request):
    """Ce dont l'interface a besoin pour créer et filtrer des documents."""
    acteur = request.user
    unites = acces.unites_de_creation(acteur).order_by("chemin")
    return Response(
        {
            "types": [_type_document(t) for t in services.types_actifs(acteur.institution_id)],
            "unites": [
                {
                    "uuid": str(u.uuid),
                    "libelle_fr": u.libelle_fr,
                    "libelle_ar": u.libelle_ar,
                    "profondeur": u.profondeur,
                }
                for u in unites
            ],
            "niveaux": [
                {"valeur": valeur, "libelle": str(libelle)}
                for valeur, libelle in NiveauHabilitation.choices
                if valeur <= acteur.niveau_habilitation
            ],
            "formats": [
                {"code": f.code, "libelle": f.libelle, "extensions": sorted(f.extensions)} for f in FORMATS.values()
            ],
            "taille_max_mo": lire_parametre(acteur.institution, "fichiers.taille_max_mo")
            if acteur.institution_id
            else 0,
            "natures_relation": [{"valeur": v, "libelle": str(lib)} for v, lib in NatureRelation.choices],
        }
    )


@documenter
@api_view(["GET", "PATCH"])
def document(request, uuid):
    objet = _document_visible(request, uuid)
    if request.method == "PATCH":
        formulaire = FormulaireModificationDocument(request.data)
        if not formulaire.is_valid():
            return erreurs_formulaire(formulaire)
        services.modifier_document(request.user, objet, requete=request, **formulaire.cleaned_data)
        objet = _requete_documents().get(pk=objet.pk)
    else:
        services.journaliser_consultation(request.user, objet, requete=request)
    return Response(_detail(request.user, objet))


@documenter
@api_view(["POST"])
def versions(request, uuid):
    objet = _document_visible(request, uuid)
    formulaire = FormulaireVersion(request.data, request.FILES)
    if not formulaire.is_valid():
        return erreurs_formulaire(formulaire)
    services.ajouter_version(
        request.user,
        objet,
        formulaire.cleaned_data["fichier"],
        commentaire=formulaire.cleaned_data["commentaire"],
        requete=request,
    )
    return Response(_detail(request.user, _requete_documents().get(pk=objet.pk)), status=status.HTTP_201_CREATED)


@documenter
@api_view(["POST"])
def pieces_jointes(request, uuid):
    objet = _document_visible(request, uuid)
    formulaire = FormulaireVersion(request.data, request.FILES)
    if not formulaire.is_valid():
        return erreurs_formulaire(formulaire)
    services.ajouter_piece_jointe(request.user, objet, formulaire.cleaned_data["fichier"], requete=request)
    return Response(_detail(request.user, _requete_documents().get(pk=objet.pk)), status=status.HTTP_201_CREATED)


@documenter
@api_view(["GET"])
def fichier(request, uuid, fichier_uuid, mode):
    """Téléchargement (pièce jointe) ou aperçu (affiché par le navigateur : PDF et images seulement)."""
    objet = _document_visible(request, uuid)
    contenu = get_object_or_404(FichierDocument.objects.select_related("version__document"), uuid=fichier_uuid)
    if contenu.version.document_id != objet.pk or (mode == "apercu" and not FORMATS[contenu.format].apercu):
        return reponse_erreurs({"__all__": [_("Introuvable.")]}, status.HTTP_404_NOT_FOUND)
    telechargement = mode == "telecharger"
    flux = services.ouvrir_fichier(request.user, contenu, telechargement=telechargement, requete=request)
    reponse = FileResponse(
        flux, as_attachment=telechargement, filename=contenu.nom_origine, content_type=contenu.type_mime
    )
    reponse["Cache-Control"] = "private, no-store"
    return reponse


@documenter
@api_view(["POST"])
def relations(request, uuid):
    source = _document_visible(request, uuid)
    formulaire = FormulaireRelation(request.data)
    if not formulaire.is_valid():
        return erreurs_formulaire(formulaire)
    cible = _document_visible(request, formulaire.cleaned_data["cible"])
    services.relier(request.user, source, cible, formulaire.cleaned_data["nature"], requete=request)
    return Response(_detail(request.user, source), status=status.HTTP_201_CREATED)


@documenter
@api_view(["DELETE"])
def relation(request, uuid, pk):
    source = _document_visible(request, uuid)
    objet = get_object_or_404(RelationDocument.objects.select_related("source", "cible"), pk=pk, source=source)
    services.supprimer_relation(request.user, objet, requete=request)
    return Response(_detail(request.user, source))


# --- Administration des types de documents ----------------------------------------

ADMINISTRATION = services.ADMINISTRATION


def _valider_definitions(donnees):
    """Valide la liste des métadonnées d'un type ; renvoie (définitions, erreurs)."""
    if not isinstance(donnees, list):
        return None, {"metadonnees": [_("Liste attendue.")]}
    definitions = []
    for rang, element in enumerate(donnees):
        formulaire = FormulaireDefinition(element if isinstance(element, dict) else {})
        if not formulaire.is_valid():
            return None, {
                f"metadonnees.{rang}.{champ}": [e["message"] for e in liste]
                for champ, liste in formulaire.errors.get_json_data().items()
            }
        definitions.append(formulaire.cleaned_data)
    return definitions, None


def _enregistrer_type(request, instance, code_http):
    formulaire = FormulaireTypeDocument(request.data, instance=instance)
    if not formulaire.is_valid():
        return erreurs_formulaire(formulaire)
    definitions, erreurs = _valider_definitions(request.data.get("metadonnees", []))
    if erreurs:
        return reponse_erreurs(erreurs)
    objet = services.enregistrer_type_document(request.user, formulaire.instance, definitions, requete=request)
    objet = TypeDocument.objects.prefetch_related("definitions").get(pk=objet.pk)
    return Response(_type_document(objet, inactives=True), status=code_http)


@documenter
@api_view(["GET", "POST"])
@permission_requise(ADMINISTRATION, portee_institution=True)
def types_document(request):
    if request.method == "POST":
        return _enregistrer_type(request, None, status.HTTP_201_CREATED)
    types = (
        TypeDocument.objects.filter(institution_id=request.user.institution_id)
        .prefetch_related("definitions")
        .annotate(nombre_documents=Count("documents"))
    )
    return Response(
        {
            "types": [_type_document(t, inactives=True) for t in types],
            "formats": [{"code": f.code, "libelle": f.libelle} for f in FORMATS.values()],
        }
    )


@documenter
@api_view(["PATCH"])
@permission_requise(ADMINISTRATION, portee_institution=True)
def type_document(request, uuid):
    objet = get_object_or_404(TypeDocument, uuid=uuid, institution_id=request.user.institution_id)
    return _enregistrer_type(request, objet, status.HTTP_200_OK)
