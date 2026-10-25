#!/bin/sh
# Démarrage du conteneur applicatif.
#   web : migrations (rôle propriétaire du schéma), fichiers statiques, bucket, puis Gunicorn (rôle applicatif)
#   autre commande : exécutée telle quelle, par exemple « python manage.py verifier_audit »
set -eu

case "${1:-web}" in
  web)
    GED_DB_USER="$GED_DB_OWNER_USER" GED_DB_PASSWORD="$GED_DB_OWNER_PASSWORD" \
      python manage.py migrate --noinput
    python manage.py collectstatic --noinput --verbosity 0
    python manage.py preparer_stockage
    exec gunicorn config.wsgi:application \
      --bind 0.0.0.0:8000 \
      --workers "${GED_GUNICORN_WORKERS:-3}" \
      --timeout 120 \
      --access-logfile - \
      --forwarded-allow-ips "*"
    ;;
  migrer)
    exec env GED_DB_USER="$GED_DB_OWNER_USER" GED_DB_PASSWORD="$GED_DB_OWNER_PASSWORD" \
      python manage.py migrate --noinput
    ;;
  *)
    exec "$@"
    ;;
esac
