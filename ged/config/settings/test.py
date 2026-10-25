"""Tests automatisés (pytest)."""

from .base import *  # noqa: F403
from .base import BASE_DIR

# Hachage rapide pour les tests uniquement ; Argon2 reste la règle ailleurs.
PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]  # noqa: S105
STORAGES = {
    "default": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
        "OPTIONS": {"location": str(BASE_DIR / ".media-tests")},
    },
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
}
CACHES = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}
