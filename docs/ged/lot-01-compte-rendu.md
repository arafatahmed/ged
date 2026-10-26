# Compte rendu du lot 1 : socle technique

**Statut : livré en développement, en attente de validation sur un serveur de recette.** Le code est dans [`ged/`](../../ged/README.md).

## Livrables

| Livrable | Emplacement |
|---|---|
| Projet Django 5.2 LTS sur PostgreSQL 16, paramètres par environnement (`dev`, `test`, `prod`) | `ged/config/` |
| Module `noyau` : institution, paramètres fonctionnels validés et journalisés, séries de numérotation | `ged/noyau/` |
| Module `audit` : journal chaîné SHA-256, ajout seul en base, scellement quotidien exporté, vérification | `ged/audit/` |
| Module `identite` : modèle utilisateur, connexion et déconnexion journalisées, Argon2 | `ged/identite/` |
| Interface français et arabe (RTL complet), responsive, navigation au clavier, couleurs et logo de l'institution | `ged/templates/`, `ged/static/`, `ged/locale/` |
| API REST (institution courante) et schéma OpenAPI | `/api/v1/`, `/api/schema/` |
| Déploiement : Dockerfile, Compose (PostgreSQL, Redis, S3, application, Nginx TLS), rôles PostgreSQL séparés | `ged/compose.yaml`, `ged/docker/` |
| Intégration continue : ruff (dont règles de sécurité), pip-audit, contrôles Django, traductions, tests et couverture | `.github/workflows/ged.yml` |
| Commandes : `initialiser_ged`, `sceller_audit`, `verifier_audit`, `preparer_stockage`, `dictionnaire_donnees` | `ged/*/management/commands/` |
| Guide d'installation, variables d'environnement documentées | `ged/README.md`, `ged/.env.exemple` |
| Dictionnaire de données généré depuis le code (vérifié par les tests) | [`dictionnaire-donnees.md`](dictionnaire-donnees.md) |

## Critères d'acceptation

| Critère (document 07) | Résultat |
|---|---|
| 50 numéros demandés en parallèle sur une série donnent 50 numéros distincts et consécutifs | **Atteint** : test `test_attributions_simultanees_sans_doublon_ni_trou` (50 fils, 50 connexions PostgreSQL) |
| Un événement d'audit modifié en base est détecté | **Atteint** : modification, suppression et recalcul complet de la chaîne sont détectés (tests `TestChaine`) |
| Tests passants en intégration continue | **Atteint** : 99 tests réussis, couverture 96 % ; première exécution GitHub Actions réussie (rôle applicatif compris) |
| `docker compose up` fonctionnel ; installation sur machine vierge en moins de 30 minutes | **Non vérifié** : pas de démon Docker dans l'environnement de développement. Compose a été validé syntaxiquement (`docker compose config`). Le script d'initialisation des rôles PostgreSQL et la séquence de démarrage (migrations avec le rôle propriétaire, exécution avec le rôle applicatif) ont été rejoués sur un PostgreSQL 16 local |

## Contrôles réalisés

- Tests automatisés (pytest, sur PostgreSQL réel) :
  - numérotation : gabarits, attribution concurrente, remise à zéro annuelle, compteurs par unité, annulation sans trou, gel du gabarit après usage ;
  - audit : chaînage, détection des altérations, déclencheurs refusant UPDATE, DELETE et TRUNCATE, droits du rôle applicatif (SELECT et INSERT seulement) ;
  - connexion : réussite, échec (sans mot de passe journalisé), compte désactivé, déconnexion par POST, cookies `HttpOnly` et `SameSite=Strict` ;
  - institution : mode mono-institution, validation du logo (le SVG est refusé) ;
  - langue : choix explicite, puis préférence de l'utilisateur, puis langue de l'institution ; affichage RTL ;
  - API et schéma réservés aux utilisateurs connectés ; administration journalisée et sans suppression.
- Base rejouée comme en production : le rôle applicatif obtient « permission denied » sur un UPDATE du journal et « must be owner » quand il tente de désactiver le déclencheur.
- `manage.py check --deploy` sans avertissement avec les paramètres de production (le préchargement HSTS est volontairement non activé : c'est une décision de l'institution).
- Captures de la page de connexion en arabe, sur ordinateur et sur mobile : la mise en page s'inverse correctement.

## Écarts et décisions à valider

1. **Interface en gabarits Django au lieu d'Angular.** *Tranché après le lot 2 : le commanditaire a demandé une interface Angular ; les gabarits ont été remplacés (voir [le compte rendu de l'interface Angular](interface-angular-compte-rendu.md)).*
2. **Code dans le sous-dossier `ged/` de ce dépôt**, et non dans un dépôt dédié (hypothèse H2 non tranchée). Le déplacement vers un dépôt dédié reste simple tant que le code est jeune.
3. **Identifiant de connexion unique sur toute l'installation** (au lieu d'unique par institution), pour que la connexion ne demande pas l'institution. Le document 04 a été mis à jour.
4. **Celery n'est pas encore installé** : aucun traitement asynchrone n'est nécessaire au lot 1. Le scellement de l'audit est une commande à planifier (cron). Celery arrivera au lot 3 (antivirus, aperçus).
5. **Image MinIO non vérifiée** : MinIO a cessé de publier les images de son édition communautaire fin 2025. L'image est configurable (`GED_IMAGE_S3`) et l'application n'utilise que l'API S3 standard ; l'institution doit choisir son service S3 avant la recette. **Résolu** : les images MinIO ne sont plus distribuées ; Compose fournit SeaweedFS 4.47, vérifié par une installation locale le 25 octobre 2026.
6. **Écritures d'audit sérialisées** : un verrou PostgreSQL ordonne la chaîne et reste tenu jusqu'à la fin de chaque transaction qui journalise. C'est adapté aux volumes visés (hypothèse H4) ; à mesurer lors des tests de charge du lot 11.

## Limites restantes

- Pas encore de rôles, permissions contextuelles, MFA, verrouillage après échecs, expiration d'inactivité ni écrans d'administration fonctionnelle : c'est le lot 2. En attendant, seule l'administration technique de Django est disponible, réservée au superadministrateur.
- Le superadministrateur technique contourne les permissions de Django (`is_superuser`). La séparation avec le contenu documentaire sera appliquée par le module `acces` du lot 2, qui n'utilisera pas ce drapeau.
- Les politiques RLS du mode multi-institutions ne sont pas encore posées (lot 18) ; toutes les tables portent déjà la colonne `institution`.
- Sauvegarde, restauration et supervision : lot 10.

## Prochaines actions

1. Valider les écarts 1 et 2 ci-dessus.
2. Exécuter `docker compose up` sur un serveur de recette et chronométrer l'installation (critère restant du lot 1).
3. Démarrer le lot 2 : unités organisationnelles, rôles, affectations, module `acces`, MFA, verrouillage, écrans d'administration.
