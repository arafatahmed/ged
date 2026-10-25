"""Production et recette : HTTPS obligatoire, secrets fournis par l'environnement."""

from .base import *  # noqa: F403
from .base import env, env_liste

DEBUG = False
SECRET_KEY = env("GED_SECRET_KEY", obligatoire=True)
ALLOWED_HOSTS = env_liste("GED_ALLOWED_HOSTS")
CSRF_TRUSTED_ORIGINS = env_liste("GED_CSRF_TRUSTED_ORIGINS")

# TLS terminé par Nginx, qui transmet X-Forwarded-Proto.
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SECURE_SSL_REDIRECT = True
SECURE_REDIRECT_EXEMPT = [r"^sante/$"]
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_HSTS_SECONDS = 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True

STORAGES["staticfiles"] = {  # noqa: F405
    "BACKEND": "django.contrib.staticfiles.storage.ManifestStaticFilesStorage"
}
# L'inscription à la liste de préchargement HSTS des navigateurs est une décision
# de l'institution (difficile à annuler) : elle n'est pas activée par défaut.
SILENCED_SYSTEM_CHECKS = ["security.W021"]
