"""Formats de fichiers admis et reconnaissance du type réel.

Le type réel est lu dans les premiers octets du fichier (signature), jamais
déduit du nom ni du type déclaré par le navigateur. Un fichier n'est admis que
si sa signature correspond à un format du catalogue ET si son extension est
celle de ce format : un exécutable renommé « .pdf » est refusé.

Les anciens formats bureautiques (doc, xls, ppt), qui peuvent porter des
macros, et les formats sans signature fiable (texte, CSV) ne sont pas admis.
"""

from dataclasses import dataclass

import filetype
from django.utils.translation import gettext_lazy as _

# Taille lue pour reconnaître la signature (les formats bureautiques sont des archives ZIP
# dont les entrées caractéristiques peuvent se trouver au-delà des premiers octets).
TAILLE_SIGNATURE = 64 * 1024


@dataclass(frozen=True)
class Format:
    code: str
    libelle: str
    type_mime: str
    extensions: frozenset
    apercu: bool = False


FORMATS = {
    f.code: f
    for f in [
        Format("pdf", "PDF", "application/pdf", frozenset({"pdf"}), apercu=True),
        Format("png", "PNG", "image/png", frozenset({"png"}), apercu=True),
        Format("jpeg", "JPEG", "image/jpeg", frozenset({"jpg", "jpeg"}), apercu=True),
        Format("tiff", "TIFF", "image/tiff", frozenset({"tif", "tiff"})),
        Format(
            "docx",
            "Word (docx)",
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            frozenset({"docx"}),
        ),
        Format(
            "xlsx",
            "Excel (xlsx)",
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            frozenset({"xlsx"}),
        ),
        Format(
            "pptx",
            "PowerPoint (pptx)",
            "application/vnd.openxmlformats-officedocument.presentationml.presentation",
            frozenset({"pptx"}),
        ),
        Format("odt", "OpenDocument texte", "application/vnd.oasis.opendocument.text", frozenset({"odt"})),
        Format("ods", "OpenDocument tableur", "application/vnd.oasis.opendocument.spreadsheet", frozenset({"ods"})),
        Format(
            "odp", "OpenDocument présentation", "application/vnd.oasis.opendocument.presentation", frozenset({"odp"})
        ),
    ]
}

_PAR_TYPE_MIME = {f.type_mime: f for f in FORMATS.values()}

MESSAGE_FORMAT_INCONNU = _("Format de fichier non admis.")


def extension(nom):
    return nom.rsplit(".", 1)[-1].lower() if "." in nom else ""


def format_par_extension(nom):
    ext = extension(nom)
    return next((f for f in FORMATS.values() if ext in f.extensions), None)


def reconnaitre(entete):
    """Format reconnu d'après la signature des premiers octets, ou None."""
    trouve = filetype.guess(entete)
    return _PAR_TYPE_MIME.get(trouve.mime) if trouve else None
