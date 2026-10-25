#!/bin/sh
# Certificat autosigné pour la recette uniquement.
# En production, utiliser le certificat délivré par l'autorité de l'institution.
set -eu
dossier="$(dirname "$0")/certs"
nom="${1:-ged.local}"
mkdir -p "$dossier"
openssl req -x509 -newkey rsa:3072 -nodes -days 365 \
  -keyout "$dossier/ged.key" -out "$dossier/ged.crt" \
  -subj "/CN=$nom" -addext "subjectAltName=DNS:$nom,DNS:localhost"
chmod 600 "$dossier/ged.key"
echo "Certificat de recette créé dans $dossier pour $nom."
