# Compte rendu du lot 2 : organisation et identité

**Statut : livré en développement, en attente de recette.** Code dans [`ged/`](../../ged/README.md).

## Livrables

| Livrable | Emplacement |
|---|---|
| Organisation : types d'unité, arbre des unités (chemin matérialisé, déplacement de sous-arbre, contrôle des boucles), postes et hiérarchie | `ged/organisation/` |
| Catalogue de 20 permissions, 9 rôles modèles conformes au document 03, types d'unité et unité racine créés avec chaque institution | `ged/identite/catalogue.py` |
| Affectations (rôle × unité × période, extension aux sous-unités), délégations temporaires | `ged/identite/models.py`, `ged/identite/services.py` |
| Moteur d'accès : décision par unité, filtrage des listes, portée institutionnelle, délégations sans permissions d'administration, habilitation ; refus journalisés | `ged/acces/moteur.py` |
| Règles anti-escalade (voir ci-dessous) | `ged/identite/services.py` |
| Connexion : verrouillage après échecs (seuil et durée paramétrables), limitation par adresse IP, double authentification TOTP (RFC 6238) avec QR code et 10 codes de secours, étape intermédiaire limitée à 5 minutes | `ged/identite/backends.py`, `totp.py`, `mfa.py`, `views.py` |
| Sessions suivies et révocables, expiration d'inactivité, changement obligatoire du mot de passe temporaire, administration technique soumise à la même connexion | `ged/identite/middleware.py`, `signals.py` |
| Écrans d'administration fonctionnelle (organisation, comptes, affectations, rôles, délégations, journal des connexions, export CSV de revue des habilitations) et « Mon compte » | `ged/administration/`, `ged/templates/` |
| Commande `creer_administrateur` (premier administrateur fonctionnel) | `ged/identite/management/commands/` |
| Traduction arabe complète des nouveaux écrans | `ged/locale/ar/` |

## Critères d'acceptation

| Critère (document 07) | Résultat |
|---|---|
| La matrice du document 03 est entièrement couverte par des tests | **Atteint pour les cases « O »** : `test_roles_initiaux_conformes_a_la_matrice` compare chaque rôle à une matrice écrite à part. Les cases « A » (objets affectés) et « P » (objets propres) sont des règles par objet : elles seront testées avec les documents et dossiers (lots 3 et 4) |
| Un administrateur ne peut pas s'attribuer un rôle | **Atteint** : refus journalisé (`test_auto_affectation_refusee`) ; idem pour son niveau d'habilitation et pour les permissions d'un rôle qu'il détient |
| Un compte désactivé perd ses sessions immédiatement | **Atteint** : sessions supprimées et requête suivante redirigée vers la connexion (`test_desactivation_ferme_les_sessions_immediatement`) |
| MFA exigée pour les rôles marqués | **Atteint** : enrôlement imposé à la connexion et aux sessions déjà ouvertes, désactivation refusée ; superadministrateur technique aussi soumis à la MFA |
| 10 échecs de connexion verrouillent le compte et sont journalisés | **Atteint** (`test_dix_echecs_verrouillent_le_compte`) ; les codes MFA faux comptent aussi comme échecs |

## Règles anti-escalade appliquées

1. Personne ne crée ni ne clôture d'affectation pour lui-même, ne change son propre niveau d'habilitation, ni ne modifie les permissions d'un rôle qu'il exerce.
2. Une permission « administration.* » ne s'attribue que si on la détient soi-même sur l'unité concernée ; l'extension aux sous-unités exige que son propre droit couvre tout le sous-arbre.
3. On n'attribue pas un niveau d'habilitation supérieur au sien.
4. Un administrateur d'unité ne gère que les comptes dont **toutes** les affectations en cours sont dans son périmètre ; un compte sans affectation n'est géré que par un administrateur dont le droit couvre toute l'institution.
5. Les délégations ne transmettent jamais les permissions d'administration et ne lèvent pas la règle d'habilitation.
6. Un objet hors du périmètre répond 404 (introuvable), sans révéler son existence ; une action refusée répond 403 et laisse une trace `acces.refus` dans le journal.

## Contrôles réalisés

- 238 tests réussis (1 ignoré sans rôle applicatif PostgreSQL), couverture 92 %, ruff sans alerte, migrations à jour, dictionnaire de données régénéré.
- Vecteurs de test officiels de la RFC 6238 pour le TOTP ; rejeu d'un code refusé.
- Parcours complet joué dans un navigateur : premier administrateur créé par la commande, connexion, enrôlement MFA (QR code), codes de secours, changement du mot de passe temporaire, création d'une unité puis d'un compte affecté ; écrans vérifiés en arabe (RTL) et sur mobile.

## Écarts et limites

- **Interface en gabarits Django** (écart 1 du lot 1) : remplacée ensuite par l'interface Angular, à la demande du commanditaire (voir [le compte rendu de l'interface Angular](interface-angular-compte-rendu.md)). Les règles et tests de ce lot sont inchangés ; ils s'exercent désormais par l'API.
- **Secrets TOTP stockés en clair en base**, comme le font les bibliothèques courantes : quiconque lit la base peut générer des codes. À chiffrer avec une clé hors base si l'institution l'exige (une dépendance `cryptography` de plus).
- **Libellés des niveaux de confidentialité** fixés dans le code (hypothèse H7) ; à rendre paramétrables si l'institution le demande.
- **Pas d'envoi de courriel** : mots de passe temporaires communiqués par l'administrateur, pas de réinitialisation en libre-service (lot 14).
- **Risque résiduel connu** : un administrateur fonctionnel qui crée un compte connaît son mot de passe temporaire et pourrait s'en servir. Mesures : changement obligatoire à la première connexion, double authentification pour les rôles sensibles, journalisation, revue périodique des habilitations. Une validation à quatre yeux des créations de comptes peut être ajoutée si l'institution l'exige.
- **Limitation par adresse IP** stockée dans le cache : avec plusieurs processus Gunicorn, elle n'est fiable qu'avec Redis (configuré dans Compose), pas avec le cache mémoire du développement.
- Pas d'intégration OIDC (hypothèse H9 non confirmée).

## Prochaines actions

1. Recette des écrans d'administration avec le futur administrateur fonctionnel.
2. Confirmer les libellés de confidentialité (H7) et la politique de verrouillage (seuil, durée).
3. Lot 3 : types de documents, métadonnées, envoi de fichiers avec quarantaine et antivirus, versions, aperçus ; application des règles « A » et « P » de la matrice.
