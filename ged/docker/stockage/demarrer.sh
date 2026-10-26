#!/bin/sh
# Démarrage du stockage S3 (SeaweedFS) : une seule identité, celle de l'application,
# lue dans les variables d'environnement. L'API S3 écoute sur le port 9000.
# Les clés ne doivent contenir ni guillemet ni barre oblique inverse (JSON).
set -eu

: "${GED_S3_ACCESS_KEY:?}" "${GED_S3_SECRET_KEY:?}"
umask 077
cat > /tmp/s3.json <<JSON
{"identities": [{"name": "ged",
  "credentials": [{"accessKey": "${GED_S3_ACCESS_KEY}", "secretKey": "${GED_S3_SECRET_KEY}"}],
  "actions": ["Admin", "Read", "Write", "List", "Tagging"]}]}
JSON

exec weed server -dir=/data -ip.bind=0.0.0.0 -s3 -s3.port=9000 -s3.config=/tmp/s3.json
