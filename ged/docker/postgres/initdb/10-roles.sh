#!/bin/bash
# Exécuté une seule fois, à la création du volume PostgreSQL.
# - propriétaire du schéma (non superutilisateur) : utilisé seulement pour les migrations ;
# - rôle applicatif : lecture et écriture des données, sans droit sur la structure.
#   Les migrations d'audit lui retirent en plus UPDATE, DELETE et TRUNCATE sur le journal.
set -euo pipefail

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname postgres \
  -v base="$GED_DB_NAME" \
  -v proprietaire="$GED_DB_OWNER_USER" -v mdp_proprietaire="$GED_DB_OWNER_PASSWORD" \
  -v applicatif="$GED_DB_USER" -v mdp_applicatif="$GED_DB_PASSWORD" <<'SQL'
CREATE ROLE :"proprietaire" LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE PASSWORD :'mdp_proprietaire';
CREATE ROLE :"applicatif" LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE PASSWORD :'mdp_applicatif';
CREATE DATABASE :"base" OWNER :"proprietaire" ENCODING 'UTF8' TEMPLATE template0;
REVOKE ALL ON DATABASE :"base" FROM PUBLIC;
GRANT CONNECT ON DATABASE :"base" TO :"applicatif";
\connect :"base"
GRANT USAGE ON SCHEMA public TO :"applicatif";
ALTER DEFAULT PRIVILEGES FOR ROLE :"proprietaire" IN SCHEMA public
  GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO :"applicatif";
ALTER DEFAULT PRIVILEGES FOR ROLE :"proprietaire" IN SCHEMA public
  GRANT USAGE, SELECT ON SEQUENCES TO :"applicatif";
SQL
