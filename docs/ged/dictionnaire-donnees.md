# Dictionnaire de données de la GED

Généré par `python manage.py dictionnaire_donnees` à partir des modèles ; ne pas modifier à la main.

## `noyau_compteurserie` (compteur de série)

| Colonne | Type | Nul | Unique | Référence | Description |
|---|---|---|---|---|---|
| `id` | bigint | non | oui |  | ID |
| `serie_id` | bigint | non |  | `noyau_serienumerotation` (PROTECT) | série |
| `cle_portee` | varchar(100) | non |  |  | portée |
| `valeur` | bigint | non |  |  | dernier numéro attribué |

Contraintes : `compteur_unique_par_portee`.

## `noyau_institution` (institution)

| Colonne | Type | Nul | Unique | Référence | Description |
|---|---|---|---|---|---|
| `id` | bigint | non | oui |  | ID |
| `cree_le` | timestamp with time zone | non |  |  | créé le |
| `modifie_le` | timestamp with time zone | non |  |  | modifié le |
| `uuid` | uuid | non | oui |  | identifiant public |
| `code` | varchar(30) | non | oui |  | code |
| `nom_fr` | varchar(255) | non |  |  | nom en français |
| `nom_ar` | varchar(255) | non |  |  | nom en arabe |
| `sigle` | varchar(30) | non |  |  | sigle |
| `logo` | varchar(100) | non |  |  | logo |
| `couleur_primaire` | varchar(7) | non |  |  | couleur principale |
| `couleur_secondaire` | varchar(7) | non |  |  | couleur secondaire |
| `adresse` | text | non |  |  | adresse |
| `telephone` | varchar(50) | non |  |  | téléphone |
| `courriel` | varchar(254) | non |  |  | courriel |
| `site_web` | varchar(200) | non |  |  | site web |
| `fuseau_horaire` | varchar(64) | non |  |  | fuseau horaire |
| `langue_defaut` | varchar(5) | non |  |  | langue par défaut |
| `format_date` | varchar(10) | non |  |  | format de date |
| `actif` | boolean | non |  |  | actif |

## `noyau_parametreinstitution` (paramètre de l'institution)

Paramètre fonctionnel d'une institution. Les clés admises sont déclarées dans `parametres.py`.

| Colonne | Type | Nul | Unique | Référence | Description |
|---|---|---|---|---|---|
| `id` | bigint | non | oui |  | ID |
| `cree_le` | timestamp with time zone | non |  |  | créé le |
| `modifie_le` | timestamp with time zone | non |  |  | modifié le |
| `institution_id` | bigint | non |  | `noyau_institution` (PROTECT) | institution |
| `cle` | varchar(100) | non |  |  | clé |
| `valeur` | jsonb | non |  |  | valeur |
| `modifie_par_id` | bigint | oui |  | `identite_utilisateur` (PROTECT) | modifié par |

Contraintes : `parametre_unique_par_cle`.

## `noyau_serienumerotation` (série de numérotation)

| Colonne | Type | Nul | Unique | Référence | Description |
|---|---|---|---|---|---|
| `id` | bigint | non | oui |  | ID |
| `cree_le` | timestamp with time zone | non |  |  | créé le |
| `modifie_le` | timestamp with time zone | non |  |  | modifié le |
| `institution_id` | bigint | non |  | `noyau_institution` (PROTECT) | institution |
| `code` | varchar(50) | non |  |  | code |
| `libelle_fr` | varchar(255) | non |  |  | libellé en français |
| `libelle_ar` | varchar(255) | non |  |  | libellé en arabe |
| `gabarit` | varchar(100) | non |  |  | gabarit : Exemple : {SIGLE}/{UNITE}/{AAAA}/{SEQ:5} |
| `par_annee` | boolean | non |  |  | repart à 1 chaque année |
| `par_unite` | boolean | non |  |  | compteur distinct par unité |
| `par_categorie` | boolean | non |  |  | compteur distinct par catégorie |
| `actif` | boolean | non |  |  | actif |

Contraintes : `serie_unique_par_code`.

## `organisation_poste` (poste)

| Colonne | Type | Nul | Unique | Référence | Description |
|---|---|---|---|---|---|
| `id` | bigint | non | oui |  | ID |
| `cree_le` | timestamp with time zone | non |  |  | créé le |
| `modifie_le` | timestamp with time zone | non |  |  | modifié le |
| `institution_id` | bigint | non |  | `noyau_institution` (PROTECT) | institution |
| `unite_id` | bigint | non |  | `organisation_uniteorganisationnelle` (PROTECT) | unité |
| `intitule_fr` | varchar(255) | non |  |  | intitulé en français |
| `intitule_ar` | varchar(255) | non |  |  | intitulé en arabe |
| `superieur_id` | bigint | oui |  | `organisation_poste` (PROTECT) | poste supérieur : Sert à l'escalade hiérarchique. |
| `actif` | boolean | non |  |  | actif |

## `organisation_typeunite` (type d'unité)

Niveau d'organisation propre à l'institution : direction, service, agence…

| Colonne | Type | Nul | Unique | Référence | Description |
|---|---|---|---|---|---|
| `id` | bigint | non | oui |  | ID |
| `cree_le` | timestamp with time zone | non |  |  | créé le |
| `modifie_le` | timestamp with time zone | non |  |  | modifié le |
| `institution_id` | bigint | non |  | `noyau_institution` (PROTECT) | institution |
| `code` | varchar(30) | non |  |  | code |
| `libelle_fr` | varchar(100) | non |  |  | libellé en français |
| `libelle_ar` | varchar(100) | non |  |  | libellé en arabe |
| `ordre` | smallint | non |  |  | ordre d'affichage |
| `actif` | boolean | non |  |  | actif |

Contraintes : `type_unite_unique_par_code`.

## `organisation_uniteorganisationnelle` (unité organisationnelle)

Unité de l'organisation (direction, service, agence…), organisée en arbre. `chemin` est le chemin matérialisé des identifiants depuis la racine (par exemple « /1/4/9/ ») : les sous-unités d'une unité sont celles dont le chemin commence par le sien. Il est tenu à jour par `organisation.services`.

| Colonne | Type | Nul | Unique | Référence | Description |
|---|---|---|---|---|---|
| `id` | bigint | non | oui |  | ID |
| `cree_le` | timestamp with time zone | non |  |  | créé le |
| `modifie_le` | timestamp with time zone | non |  |  | modifié le |
| `institution_id` | bigint | non |  | `noyau_institution` (PROTECT) | institution |
| `uuid` | uuid | non | oui |  | identifiant public |
| `type_id` | bigint | non |  | `organisation_typeunite` (PROTECT) | type |
| `parent_id` | bigint | oui |  | `organisation_uniteorganisationnelle` (PROTECT) | unité parente |
| `code` | varchar(30) | non |  |  | code : Utilisé dans les références (jeton {UNITE}). |
| `sigle` | varchar(30) | non |  |  | sigle |
| `libelle_fr` | varchar(255) | non |  |  | libellé en français |
| `libelle_ar` | varchar(255) | non |  |  | libellé en arabe |
| `chemin` | varchar(1000) | non |  |  | chemin |
| `actif` | boolean | non |  |  | actif |

Contraintes : `unite_unique_par_code`, `unite_pas_son_propre_parent`.

## `identite_affectation` (affectation)

Rôle exercé par un utilisateur dans une unité, pour une période. Une affectation ne se supprime pas : elle se clôture (date de fin).

| Colonne | Type | Nul | Unique | Référence | Description |
|---|---|---|---|---|---|
| `id` | bigint | non | oui |  | ID |
| `uuid` | uuid | non | oui |  | identifiant public |
| `utilisateur_id` | bigint | non |  | `identite_utilisateur` (PROTECT) | utilisateur |
| `unite_id` | bigint | non |  | `organisation_uniteorganisationnelle` (PROTECT) | unité |
| `role_id` | bigint | non |  | `identite_role` (PROTECT) | rôle |
| `poste_id` | bigint | oui |  | `organisation_poste` (PROTECT) | poste |
| `etendue_sous_unites` | boolean | non |  |  | s'étend aux sous-unités : Le rôle s'exerce aussi dans toutes les unités rattachées à celle-ci. |
| `date_debut` | date | non |  |  | date de début |
| `date_fin` | date | oui |  |  | date de fin |
| `attribuee_par_id` | bigint | oui |  | `identite_utilisateur` (PROTECT) | attribuée par |
| `cree_le` | timestamp with time zone | non |  |  | créée le |

Contraintes : `affectation_dates_coherentes`.

## `identite_appareiltotp` (application d'authentification)

Application d'authentification (TOTP, RFC 6238) d'un utilisateur.

| Colonne | Type | Nul | Unique | Référence | Description |
|---|---|---|---|---|---|
| `id` | bigint | non | oui |  | ID |
| `utilisateur_id` | bigint | non | oui | `identite_utilisateur` (PROTECT) | utilisateur |
| `secret` | varchar(64) | non |  |  | secret |
| `confirme` | boolean | non |  |  | confirmé |
| `dernier_pas` | bigint | non |  |  | dernier pas de temps utilisé : Empêche de réutiliser un code. |
| `cree_le` | timestamp with time zone | non |  |  | créé le |
| `confirme_le` | timestamp with time zone | oui |  |  | confirmé le |

## `identite_codesecours` (code de secours)

Code de secours à usage unique ; seule son empreinte est conservée.

| Colonne | Type | Nul | Unique | Référence | Description |
|---|---|---|---|---|---|
| `id` | bigint | non | oui |  | ID |
| `utilisateur_id` | bigint | non |  | `identite_utilisateur` (PROTECT) | utilisateur |
| `empreinte` | varchar(64) | non | oui |  | empreinte |
| `utilise_le` | timestamp with time zone | oui |  |  | utilisé le |
| `cree_le` | timestamp with time zone | non |  |  | créé le |

## `identite_delegation` (délégation)

Le délégataire exerce temporairement les rôles du délégant (hors permissions d'administration).

| Colonne | Type | Nul | Unique | Référence | Description |
|---|---|---|---|---|---|
| `id` | bigint | non | oui |  | ID |
| `uuid` | uuid | non | oui |  | identifiant public |
| `delegant_id` | bigint | non |  | `identite_utilisateur` (PROTECT) | délégant |
| `delegataire_id` | bigint | non |  | `identite_utilisateur` (PROTECT) | délégataire |
| `debut` | timestamp with time zone | non |  |  | début |
| `fin` | timestamp with time zone | non |  |  | fin |
| `motif` | varchar(255) | non |  |  | motif |
| `creee_par_id` | bigint | non |  | `identite_utilisateur` (PROTECT) | créée par |
| `creee_le` | timestamp with time zone | non |  |  | créée le |
| `revoquee_le` | timestamp with time zone | oui |  |  | révoquée le |
| `revoquee_par_id` | bigint | oui |  | `identite_utilisateur` (PROTECT) | révoquée par |

Contraintes : `delegation_dates_coherentes`, `delegation_a_un_tiers`.

## `identite_permission` (permission)

Permission du catalogue (`identite.catalogue`), synchronisée après chaque migration.

| Colonne | Type | Nul | Unique | Référence | Description |
|---|---|---|---|---|---|
| `id` | bigint | non | oui |  | ID |
| `code` | varchar(100) | non | oui |  | code |
| `groupe` | varchar(100) | non |  |  | groupe |
| `description` | varchar(255) | non |  |  | description |
| `actif` | boolean | non |  |  | actif |

## `identite_role` (rôle)

| Colonne | Type | Nul | Unique | Référence | Description |
|---|---|---|---|---|---|
| `id` | bigint | non | oui |  | ID |
| `institution_id` | bigint | non |  | `noyau_institution` (PROTECT) | institution |
| `uuid` | uuid | non | oui |  | identifiant public |
| `code` | varchar(50) | non |  |  | code |
| `libelle_fr` | varchar(150) | non |  |  | libellé en français |
| `libelle_ar` | varchar(150) | non |  |  | libellé en arabe |
| `description` | text | non |  |  | description |
| `mfa_requis` | boolean | non |  |  | double authentification obligatoire : Les titulaires de ce rôle doivent activer la double authentification. |
| `systeme` | boolean | non |  |  | rôle fourni à l'installation |
| `actif` | boolean | non |  |  | actif |
| `cree_le` | timestamp with time zone | non |  |  | créé le |
| `modifie_le` | timestamp with time zone | non |  |  | modifié le |

Contraintes : `role_unique_par_code`.

## `identite_sessionutilisateur` (session)

Journal des sessions : permet de lister et révoquer les sessions d'un compte.

| Colonne | Type | Nul | Unique | Référence | Description |
|---|---|---|---|---|---|
| `id` | bigint | non | oui |  | ID |
| `utilisateur_id` | bigint | non |  | `identite_utilisateur` (PROTECT) | utilisateur |
| `cle_session` | varchar(40) | non | oui |  | clé de session |
| `adresse_ip` | varchar(45) | non |  |  | adresse IP |
| `agent` | varchar(255) | non |  |  | navigateur |
| `debut` | timestamp with time zone | non |  |  | début |
| `fin` | timestamp with time zone | oui |  |  | fin |
| `motif_fin` | varchar(20) | non |  |  | motif de fin |

## `identite_utilisateur` (utilisateur)

Compte utilisateur. Les droits ne sont pas portés par le compte mais par ses affectations (rôle exercé dans une unité). Le niveau d'habilitation borne en plus les documents accessibles selon leur confidentialité.

| Colonne | Type | Nul | Unique | Référence | Description |
|---|---|---|---|---|---|
| `id` | bigint | non | oui |  | ID |
| `password` | varchar(128) | non |  |  | mot de passe |
| `last_login` | timestamp with time zone | oui |  |  | dernière connexion |
| `is_superuser` | boolean | non |  |  | statut super-utilisateur : Précise que l’utilisateur possède toutes les permissions sans les assigner explicitement. |
| `uuid` | uuid | non | oui |  | identifiant public |
| `institution_id` | bigint | oui |  | `noyau_institution` (PROTECT) | institution : Vide uniquement pour le superadministrateur technique. |
| `identifiant` | varchar(150) | non | oui |  | identifiant |
| `nom` | varchar(150) | non |  |  | nom |
| `prenom` | varchar(150) | non |  |  | prénom |
| `nom_ar` | varchar(255) | non |  |  | nom complet en arabe |
| `courriel` | varchar(254) | non |  |  | courriel |
| `langue` | varchar(5) | non |  |  | langue de l'interface : Vide : langue par défaut de l'institution. |
| `is_active` | boolean | non |  |  | actif |
| `is_staff` | boolean | non |  |  | accès à l'administration technique |
| `date_creation` | timestamp with time zone | non |  |  | créé le |
| `niveau_habilitation` | smallint | non |  |  | niveau d'habilitation |
| `echecs_connexion` | smallint | non |  |  | échecs de connexion consécutifs |
| `verrouille_jusqu_a` | timestamp with time zone | oui |  |  | verrouillé jusqu'à |
| `doit_changer_mot_de_passe` | boolean | non |  |  | doit changer son mot de passe : Activé lorsqu'un administrateur fixe un mot de passe temporaire. |
| `mot_de_passe_modifie_le` | timestamp with time zone | oui |  |  | mot de passe modifié le |

Contraintes : `utilisateur_rattache_a_une_institution`.

## `audit_journalaudit` (événement d'audit)

Événement du journal d'audit. Table en ajout seul : un déclencheur PostgreSQL refuse UPDATE, DELETE et TRUNCATE (migration 0003). Chaque ligne contient l'empreinte de la précédente : supprimer ou modifier une ligne rompt la chaîne, ce que détecte `audit.services.verifier_chaine`.

| Colonne | Type | Nul | Unique | Référence | Description |
|---|---|---|---|---|---|
| `id` | bigint | non | oui |  | ID |
| `horodatage` | timestamp with time zone | non |  |  | horodatage |
| `institution_id` | bigint | oui |  | `noyau_institution` (PROTECT) | institution |
| `acteur_id` | bigint | oui |  | `identite_utilisateur` (PROTECT) | compte de l'acteur |
| `acteur_libelle` | varchar(150) | non |  |  | acteur |
| `agissant_pour_id` | bigint | oui |  | `identite_utilisateur` (PROTECT) | agissant pour (délégation) |
| `adresse_ip` | varchar(45) | non |  |  | adresse IP |
| `action` | varchar(100) | non |  |  | action |
| `objet_type` | varchar(100) | non |  |  | type d'objet |
| `objet_id` | varchar(64) | non |  |  | identifiant de l'objet |
| `resultat` | varchar(10) | non |  |  | résultat |
| `details` | jsonb | non |  |  | détails |
| `empreinte_precedente` | varchar(64) | non |  |  | empreinte précédente |
| `empreinte` | varchar(64) | non | oui |  | empreinte |

## `audit_scellementaudit` (scellement du journal)

Empreinte de la dernière ligne du journal à la fin d'une journée. Une copie est exportée hors de la base : si la chaîne entière était recalculée après coup, elle ne correspondrait plus aux copies exportées.

| Colonne | Type | Nul | Unique | Référence | Description |
|---|---|---|---|---|---|
| `id` | bigint | non | oui |  | ID |
| `date` | date | non | oui |  | date |
| `dernier_id` | bigint | non |  |  | dernier événement scellé |
| `empreinte` | varchar(64) | non |  |  | empreinte |
| `nombre_evenements` | bigint | non |  |  | nombre d'événements depuis l'origine |
| `cree_le` | timestamp with time zone | non |  |  | créé le |
