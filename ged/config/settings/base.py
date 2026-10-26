"""Paramètres communs à tous les environnements.

Tout ce qui dépend de l'infrastructure vient de variables d'environnement
(voir `.env.exemple`). Tout ce qui dépend de l'institution est une donnée,
configurée dans l'application, jamais ici.
"""

import os
from pathlib import Path

from django.core.exceptions import ImproperlyConfigured

BASE_DIR = Path(__file__).resolve().parent.parent.parent


def env(nom, defaut=None, obligatoire=False):
    valeur = os.environ.get(nom, defaut)
    if obligatoire and not valeur:
        raise ImproperlyConfigured(f"Variable d'environnement manquante : {nom}")
    return valeur


def env_bool(nom, defaut=False):
    return env(nom, str(defaut)).strip().lower() in {"1", "true", "oui", "yes"}


def env_liste(nom, defaut=""):
    return [v.strip() for v in env(nom, defaut).split(",") if v.strip()]


SECRET_KEY = env("GED_SECRET_KEY", "dev-uniquement-ne-pas-utiliser-en-production")
DEBUG = False
ALLOWED_HOSTS = env_liste("GED_ALLOWED_HOSTS", "localhost,127.0.0.1")

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
    "drf_spectacular",
    "noyau",
    "organisation",
    "acces",
    "administration",
    "identite",
    "audit",
    "documents",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.locale.LocaleMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "noyau.middleware.InstitutionMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "identite.middleware.SecuriteSessionMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.template.context_processors.i18n",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": env("GED_DB_NAME", "ged"),
        "USER": env("GED_DB_USER", "ged"),
        "PASSWORD": env("GED_DB_PASSWORD", "ged"),
        "HOST": env("GED_DB_HOST", "localhost"),
        "PORT": env("GED_DB_PORT", "5432"),
        "CONN_MAX_AGE": int(env("GED_DB_CONN_MAX_AGE", "60")),
        "CONN_HEALTH_CHECKS": True,
    }
}
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# Rôle PostgreSQL utilisé par l'application en production, distinct du
# propriétaire du schéma. S'il est défini, les migrations lui retirent les
# droits UPDATE, DELETE et TRUNCATE sur les tables d'audit.
GED_DB_ROLE_APPLICATIF = env("GED_DB_ROLE_APPLICATIF", "")

AUTH_USER_MODEL = "identite.Utilisateur"
AUTHENTICATION_BACKENDS = ["identite.backends.BackendGed"]
# Pages du frontend Angular (même domaine).
LOGIN_URL = "/connexion"

PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.Argon2PasswordHasher",
    "django.contrib.auth.hashers.PBKDF2PasswordHasher",
]
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
        "OPTIONS": {"min_length": 12},
    },
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# Langues de l'interface : les textes sources sont en français.
LANGUAGE_CODE = "fr"
LANGUAGES = [("fr", "Français"), ("ar", "العربية")]
LOCALE_PATHS = [BASE_DIR / "locale"]
USE_I18N = True
USE_TZ = True
# Fuseau par défaut du serveur ; le fuseau de l'institution est activé par requête.
TIME_ZONE = env("GED_TIME_ZONE", "UTC")

STATIC_URL = "/static/"
STATIC_ROOT = Path(env("GED_STATIC_ROOT", str(BASE_DIR / "staticfiles")))

# Stockage des fichiers : S3 (SeaweedFS ou compatible) si configuré, sinon disque local.
# Les buckets sont privés ; aucun fichier n'est servi directement au navigateur.
GED_S3_ENDPOINT = env("GED_S3_ENDPOINT", "")
if GED_S3_ENDPOINT:
    _stockage_defaut = {
        "BACKEND": "storages.backends.s3.S3Storage",
        "OPTIONS": {
            "endpoint_url": GED_S3_ENDPOINT,
            "access_key": env("GED_S3_ACCESS_KEY", obligatoire=True),
            "secret_key": env("GED_S3_SECRET_KEY", obligatoire=True),
            "bucket_name": env("GED_S3_BUCKET", "ged"),
            "region_name": env("GED_S3_REGION", "us-east-1"),
            "default_acl": None,
            "querystring_auth": True,
            "querystring_expire": 60,
            "file_overwrite": False,
            "signature_version": "s3v4",
            "addressing_style": "path",
        },
    }
else:
    _stockage_defaut = {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
        "OPTIONS": {"location": env("GED_MEDIA_ROOT", str(BASE_DIR / "media"))},
    }
STORAGES = {
    "default": _stockage_defaut,
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
}

# Antivirus des fichiers envoyés (démon ClamAV). Sans hôte : aucune analyse antivirus,
# admis en développement seulement (la production l'exige, voir prod.py).
GED_ANTIVIRUS_HOTE = env("GED_ANTIVIRUS_HOTE", "")
GED_ANTIVIRUS_PORT = int(env("GED_ANTIVIRUS_PORT", "3310"))
GED_ANTIVIRUS_DELAI = int(env("GED_ANTIVIRUS_DELAI", "120"))

GED_REDIS_URL = env("GED_REDIS_URL", "")
if GED_REDIS_URL:
    CACHES = {"default": {"BACKEND": "django.core.cache.backends.redis.RedisCache", "LOCATION": GED_REDIS_URL}}
else:
    CACHES = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}

# Sessions côté serveur, cookies non accessibles au JavaScript.
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Strict"
SESSION_COOKIE_AGE = int(env("GED_SESSION_DUREE_SECONDES", str(8 * 3600)))
SESSION_EXPIRE_AT_BROWSER_CLOSE = True
CSRF_COOKIE_SAMESITE = "Strict"
X_FRAME_OPTIONS = "DENY"
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "same-origin"

# Derrière Nginx : l'adresse IP du client est lue dans X-Forwarded-For
# uniquement si ce paramètre est activé (sinon elle serait falsifiable).
GED_PROXY_DE_CONFIANCE = env_bool("GED_PROXY_DE_CONFIANCE", False)

# Une installation sert une institution, sauf activation explicite.
GED_MULTI_INSTITUTIONS = env_bool("GED_MULTI_INSTITUTIONS", False)

# Répertoire d'export des scellements quotidiens du journal d'audit.
# En production, il doit pointer vers un support hors de la base (WORM si possible).
GED_AUDIT_SCELLEMENT_DIR = env("GED_AUDIT_SCELLEMENT_DIR", str(BASE_DIR / "scellements"))

# Préfixe de l'administration technique (à personnaliser en production).
GED_ADMIN_URL = env("GED_ADMIN_URL", "administration-technique/")

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": ["rest_framework.authentication.SessionAuthentication"],
    "DEFAULT_PERMISSION_CLASSES": ["rest_framework.permissions.IsAuthenticated"],
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 25,
    "DEFAULT_SCHEMA_CLASS": "noyau.api_outils.SchemaGed",
    "EXCEPTION_HANDLER": "noyau.api_outils.gestionnaire_exceptions",
    "DEFAULT_RENDERER_CLASSES": ["rest_framework.renderers.JSONRenderer"],
}
SPECTACULAR_SETTINGS = {
    "TITLE": "API de la GED",
    "VERSION": "0.1.0",
    "SERVE_INCLUDE_SCHEMA": False,
    "SERVE_PERMISSIONS": ["rest_framework.permissions.IsAuthenticated"],
}

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "standard": {"format": "%(asctime)s %(levelname)s %(name)s %(message)s"},
    },
    "handlers": {"console": {"class": "logging.StreamHandler", "formatter": "standard"}},
    "root": {"handlers": ["console"], "level": env("GED_LOG_LEVEL", "INFO")},
}
