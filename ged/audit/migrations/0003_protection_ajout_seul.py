"""Protège les tables d'audit contre la modification et la suppression.

1. Un déclencheur refuse UPDATE, DELETE et TRUNCATE (sauf d'une table vide),
   quel que soit le rôle, tant qu'il n'est pas désactivé par le propriétaire
   du schéma.
2. Si GED_DB_ROLE_APPLICATIF est défini, ce rôle (celui de l'application en
   production, distinct du propriétaire) ne garde que SELECT et INSERT : il
   ne peut ni modifier les lignes ni désactiver le déclencheur.
"""

from django.conf import settings
from django.db import migrations

TABLES = ["audit_journalaudit", "audit_scellementaudit"]

FONCTION = """
CREATE OR REPLACE FUNCTION audit_interdire_modification() RETURNS trigger AS $$
DECLARE
    non_vide boolean;
BEGIN
    -- Vider une table déjà vide ne détruit rien : c'est le cas du nettoyage
    -- des bases de test, qui ne doit pas échouer.
    IF TG_OP = 'TRUNCATE' THEN
        EXECUTE format('SELECT EXISTS (SELECT 1 FROM %I.%I)', TG_TABLE_SCHEMA, TG_TABLE_NAME) INTO non_vide;
        IF NOT non_vide THEN
            RETURN NULL;
        END IF;
    END IF;
    RAISE EXCEPTION 'Table d''audit en ajout seul : % interdit sur %', TG_OP, TG_TABLE_NAME
        USING ERRCODE = 'insufficient_privilege';
END;
$$ LANGUAGE plpgsql;
"""


def creer_declencheurs():
    instructions = [FONCTION]
    for table in TABLES:
        instructions.append(
            f"CREATE TRIGGER {table}_ajout_seul BEFORE UPDATE OR DELETE ON {table} "
            "FOR EACH ROW EXECUTE FUNCTION audit_interdire_modification();"
        )
        instructions.append(
            f"CREATE TRIGGER {table}_sans_troncature BEFORE TRUNCATE ON {table} "
            "FOR EACH STATEMENT EXECUTE FUNCTION audit_interdire_modification();"
        )
    return instructions


def supprimer_declencheurs():
    instructions = []
    for table in TABLES:
        instructions.append(f"DROP TRIGGER IF EXISTS {table}_ajout_seul ON {table};")
        instructions.append(f"DROP TRIGGER IF EXISTS {table}_sans_troncature ON {table};")
    instructions.append("DROP FUNCTION IF EXISTS audit_interdire_modification();")
    return instructions


def restreindre_role_applicatif(apps, schema_editor):
    role = settings.GED_DB_ROLE_APPLICATIF
    if not role:
        return
    nom = schema_editor.quote_name(role)
    for table in TABLES:
        schema_editor.execute(f"GRANT SELECT, INSERT ON {table} TO {nom}")
        schema_editor.execute(f"REVOKE UPDATE, DELETE, TRUNCATE ON {table} FROM {nom}")


class Migration(migrations.Migration):
    dependencies = [("audit", "0002_initial")]

    operations = [
        migrations.RunSQL(creer_declencheurs(), supprimer_declencheurs()),
        migrations.RunPython(restreindre_role_applicatif, migrations.RunPython.noop),
    ]
