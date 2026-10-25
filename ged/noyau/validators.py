from django.core.exceptions import ValidationError
from django.utils.translation import gettext as _

TAILLE_MAX_LOGO = 1024 * 1024
SIGNATURES_IMAGE = {
    b"\x89PNG\r\n\x1a\n": "image/png",
    b"\xff\xd8\xff": "image/jpeg",
}


def type_image(entete):
    for signature, type_mime in SIGNATURES_IMAGE.items():
        if entete.startswith(signature):
            return type_mime
    return None


def valider_logo(fichier):
    """Accepte uniquement des PNG ou JPEG d'au plus 1 Mo, d'après leur contenu réel.

    Le SVG est exclu : il peut contenir du script.
    """
    if fichier.size > TAILLE_MAX_LOGO:
        raise ValidationError(_("Le logo ne doit pas dépasser 1 Mo."))
    position = fichier.tell() if hasattr(fichier, "tell") else 0
    fichier.seek(0)
    entete = fichier.read(8)
    fichier.seek(position)
    if type_image(entete) is None:
        raise ValidationError(_("Le logo doit être une image PNG ou JPEG."))
