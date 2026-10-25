# GED : plateforme de gestion électronique des documents

Application de gestion électronique des documents pour institutions publiques, générique et configurable.
Le cadrage et la conception sont dans [`docs/ged/`](../docs/ged/README.md). Ce dossier contient le code.

Architecture : une **API REST Django** (Python 3.13, Django 5.2 LTS, Django REST Framework, PostgreSQL 16) et une
**interface Angular 21** (`frontend/`, Angular Material 3, signaux, sans zone.js), servies sur le même domaine par Nginx.
Stockage compatible S3, Redis, Docker Compose. L'authentification se fait par session Django (cookie HttpOnly,
SameSite=Strict, jeton CSRF), sans jeton stocké dans le navigateur.

## Modules livrés (lots 1 et 2)

| Module | Rôle |
|---|---|
| `noyau` | Institution (identité, couleurs, logo, fuseau, langue), paramètres fonctionnels validés, séries de numérotation sans doublon ni trou |
| `audit` | Journal d'audit chaîné par SHA-256, en ajout seul (déclencheur PostgreSQL et droits du rôle applicatif), scellement quotidien exporté, vérification |
| `organisation` | Types d'unité, arbre des unités organisationnelles (chemin matérialisé), postes et hiérarchie |
| `identite` | Comptes, rôles, permissions, affectations (rôle × unité × période), délégations ; connexion en deux étapes (TOTP et codes de secours), verrouillage, sessions suivies et révocables, expiration d'inactivité, mot de passe temporaire à changer |
| `acces` | Moteur de décision d'accès : permissions par unité (avec extension aux sous-unités), délégations, habilitation ; refus journalisés |
| `administration` | API d'administration fonctionnelle : organisation, comptes, affectations, rôles, délégations, journal des connexions, revue des habilitations, tableau de bord |
| `config` | Paramètres par environnement (`dev`, `test`, `prod`), routes de l'API, sécurité HTTP |
| `frontend/` | Interface Angular : connexion en étapes, Mon compte, administration ; français et arabe à chaud (RTL), animations, accessibilité |

L'administration fonctionnelle de l'institution se fait dans l'interface (`/administration/...`). L'administration technique de Django
(`/administration-technique/`) reste réservée au superadministrateur technique : elle passe par la connexion de
l'application (double authentification obligatoire), toute modification y est journalisée et aucune suppression n'y est
possible. Le superadministrateur technique n'a aucun droit sur le contenu de l'institution.

## Poste de développement

Prérequis : Python 3.12 ou plus, PostgreSQL 16 (local, ou `docker compose -f compose.yaml -f compose.dev.yaml up postgres`), `gettext`.

```bash
cd ged
python -m venv .venv && . .venv/bin/activate
pip install -r requirements/dev.txt
# Base locale attendue par défaut : base « ged », utilisateur « ged », mot de passe « ged » (voir config/settings/base.py)
createuser --createdb ged && createdb -O ged ged   # en tant qu'administrateur PostgreSQL
python manage.py migrate
python manage.py compilemessages -l ar
python manage.py initialiser_ged --code demo --nom-fr "Institution de démonstration" --nom-ar "مؤسسة تجريبية" --sigle DEMO --fuseau Africa/Nouakchott
python manage.py creer_administrateur --institution demo --identifiant admin --nom Sow --prenom Fatimata
python manage.py runserver            # API sur http://localhost:8000
```

Interface Angular (Node.js 22) dans un second terminal :

```bash
cd ged/frontend
npm ci
npm start                              # http://localhost:4200 ; /api et /institution sont relayés vers Django (proxy.conf.json)
```

Ouvrir http://localhost:4200 : la première connexion de l'administrateur enchaîne l'activation de la double
authentification et le changement du mot de passe temporaire.

## Tests et contrôles

```bash
python -m pytest --cov                    # tests (PostgreSQL requis : verrous, déclencheurs, contraintes)
ruff check . && ruff format --check .     # analyse statique (dont règles de sécurité) et formatage
python manage.py makemigrations --check --dry-run
python manage.py dictionnaire_donnees ../docs/ged/dictionnaire-donnees.md   # après toute modification de modèle
```

Pour tester aussi les droits du rôle applicatif, créer un rôle PostgreSQL et lancer
`GED_DB_ROLE_APPLICATIF=nom_du_role python -m pytest --create-db`.

Après tout ajout de message d'API : `python manage.py makemessages -l ar --no-location --no-obsolete -i "frontend/*"`,
traduire dans `locale/ar/LC_MESSAGES/django.po`, puis `compilemessages`. L'intégration continue échoue si une traduction manque.

Frontend :

```bash
cd frontend
npm test                               # tests unitaires (Vitest)
npm run format:verifier                # formatage (Prettier)
npx ng build                           # compilation de production : types stricts, budgets de taille
```

Les textes de l'interface sont dans `frontend/src/app/i18n/fr.ts` et `ar.ts` ; le compilateur refuse une clé sans
traduction arabe ou une clé inconnue dans un gabarit.

Parcours de recette de bout en bout (navigateur réel, base neuve avec `initialiser_ged` et `creer_administrateur`) :

```bash
GED_URL=http://localhost:4200 GED_MOT_DE_PASSE=<mot de passe temporaire> CHROMIUM=<chemin de Chrome> npm run e2e
```

## Installation sur serveur (recette ou production)

Prérequis : un serveur Linux avec Docker Engine et le plugin Compose.

```bash
cd ged
cp .env.exemple .env          # puis remplacer toutes les valeurs « a-changer »
chmod 600 .env
docker/nginx/generer-certificat-recette.sh ged.institution.example   # recette ; en production, déposer le vrai certificat dans docker/nginx/certs/
docker compose up -d --build
docker compose exec web python manage.py initialiser_ged --code ... --nom-fr "..." --nom-ar "..." --sigle ... --fuseau Africa/Nouakchott --langue fr
docker compose exec web python manage.py creer_administrateur --institution ... --identifiant ... --nom ... --prenom ...
```

`initialiser_ged` crée l'institution avec ses référentiels initiaux (permissions, neuf rôles modèles, types d'unité,
unité racine). `creer_administrateur` crée le premier administrateur fonctionnel (rôle étendu à toute l'organisation) et
affiche un mot de passe temporaire une seule fois. À sa première connexion, il active la double authentification puis
choisit son mot de passe ; il crée ensuite les unités, les comptes et les affectations depuis `/administration/`.
Un superadministrateur technique (`createsuperuser`) n'est utile que pour l'administration technique de Django.

Le service `nginx` est construit à partir de `docker/nginx/Dockerfile` : il compile l'interface Angular puis la sert,
avec une politique de sécurité du contenu (CSP) stricte dont le nonce change à chaque réponse, et relaie `/api/`,
`/administration-technique/`, `/sante/` et `/institution/` vers Django.

Au démarrage, le conteneur `web` applique les migrations avec le rôle propriétaire du schéma, puis sert l'application
avec le rôle applicatif, qui n'a aucun droit sur la structure et ne peut ni modifier ni supprimer le journal d'audit.
Les réseaux de PostgreSQL, Redis et du stockage n'ont pas d'accès à l'extérieur.

Tâches à planifier sur l'hôte (cron) :

```cron
# Scellement du journal d'audit de la veille, à 00:15
15 0 * * * cd /opt/ged && docker compose exec -T web python manage.py sceller_audit
# Vérification complète de la chaîne, chaque dimanche à 02:00
0 2 * * 0 cd /opt/ged && docker compose exec -T web python manage.py verifier_audit --scellements /srv/scellements
```

Les copies des scellements (volume `scellements`) doivent être recopiées régulièrement hors du serveur, sur un support
non modifiable si possible : c'est ce qui permet de détecter une réécriture complète du journal.

### Variables d'environnement

Toutes sont documentées dans [`.env.exemple`](.env.exemple). Les plus importantes :

| Variable | Rôle |
|---|---|
| `GED_SECRET_KEY` | Clé secrète Django (obligatoire en production, 50 caractères aléatoires) |
| `GED_ALLOWED_HOSTS`, `GED_CSRF_TRUSTED_ORIGINS` | Nom(s) de domaine servis |
| `GED_DB_OWNER_USER` / `GED_DB_USER` | Rôle propriétaire (migrations) / rôle applicatif (exécution) |
| `GED_S3_*` | Accès au stockage objet ; sans `GED_S3_ENDPOINT`, les fichiers vont sur disque (développement) |
| `GED_MULTI_INSTITUTIONS` | `false` par défaut : une installation sert une seule institution |
| `GED_ADMIN_URL` | Préfixe de l'administration technique |
| `GED_AUDIT_SCELLEMENT_DIR` | Répertoire d'export des scellements du journal |

### Stockage S3 : point d'attention

L'application n'utilise que l'API S3 standard. L'image MinIO proposée par défaut est configurable (`GED_IMAGE_S3`) :
MinIO a cessé fin 2025 de publier des images de son édition communautaire, et l'étiquette par défaut n'a pas pu être
vérifiée lors de l'écriture de ce lot. Avant la recette, choisir et figer l'image du service S3 retenu par l'institution
(MinIO construit depuis ses sources, Garage, SeaweedFS ou un stockage S3 interne existant).

## Interfaces

Pages de l'interface Angular (servies par Nginx, ou par `npm start` en développement) :

| Adresse | Rôle |
|---|---|
| `/connexion` | Connexion en étapes : mot de passe, code de double authentification ou activation, codes de secours |
| `/` | Tableau de bord : indicateurs du périmètre, raccourcis |
| `/compte`, `/compte/mot-de-passe`, `/compte/double-authentification` | Mon compte : langue, sécurité, affectations, délégations, sessions |
| `/administration/organisation`, `/postes`, `/utilisateurs`, `/roles`, `/connexions` | Administration (selon les droits) |

Adresses servies par Django :

| Adresse | Rôle |
|---|---|
| `/api/v1/session/…` | Session : état, connexion, vérification du code, activation de la double authentification, déconnexion |
| `/api/v1/compte/…` | Mon compte : préférences, mot de passe, double authentification, sessions, délégations |
| `/api/v1/administration/…` | Unités, types, postes, utilisateurs, affectations, rôles, journal des connexions, revue CSV |
| `/api/v1/tableau-de-bord/`, `/api/v1/institution/` | Indicateurs, institution courante |
| `/api/schema/` | Schéma OpenAPI de l'API (connexion requise) |
| `/sante/` | Sonde de supervision (base de données joignable) |
| `/institution/logo/` | Logo de l'institution |
| `/administration-technique/` | Administration technique (superadministrateur, double authentification obligatoire) |
