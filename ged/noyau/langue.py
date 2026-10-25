from django.utils import translation


def localise(francais, arabe):
    """Libellé dans la langue active : l'arabe s'il est renseigné et actif, sinon le français."""
    return arabe if arabe and (translation.get_language() or "").startswith("ar") else francais
