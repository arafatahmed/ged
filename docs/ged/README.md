# Plateforme GED : dossier de cadrage et de conception

**Statut : cadrage et conception soumis à validation ; lots 1 (socle technique), 2 (organisation et identité) et 3 (documents et stockage) livrés dans [`ged/`](../../ged/README.md), avec une interface Angular.**
Voir les comptes rendus des [lot 1](lot-01-compte-rendu.md), [lot 2](lot-02-compte-rendu.md) et [lot 3](lot-03-compte-rendu.md) et le [dictionnaire de données](dictionnaire-donnees.md), généré depuis le code.

## Contexte

Le dépôt contient aujourd'hui l'application GRH et paie de l'ENAJM, reconstruite par décompilation (Java 7, JSF, Hibernate, MySQL). La GED est une **application distincte** : elle ne réutilise ni son code ni sa base. Elle doit rester générique : aucun nom d'institution, de direction ou de service n'est écrit dans le code. L'ENAJM est l'**institution pilote supposée** (hypothèse H1).

Deux points relevés dans le dépôt GRH concernent directement la GED :

- La GRH gère déjà quelques pièces du personnel (table `pieces` : URL, nom, date, employé), stockées comme fichiers dans `src/main/webapp/images/documents/`. Ces pièces sont des candidates à une reprise dans la GED (dossiers individuels des agents), au lot 11.
- Ces 154 fichiers (pièces d'identité, CV, documents nominatifs) sont **versionnés dans Git**, ainsi que les identifiants MySQL de `WEB-INF/applicationContext.xml`. C'est exactement le type d'exposition que la GED doit empêcher. Ce dossier ne corrige pas ce point (voir le risque R1 du document 06).

## Sommaire

| N° | Document | Contenu |
|---|---|---|
| 01 | [Architecture](01-architecture.md) | Synthèse, composants, choix techniques justifiés, déploiement, sécurité |
| 02 | [Périmètre du MVP](02-perimetre-mvp.md) | Ce qui est dans le MVP, ce qui est reporté, exigences non fonctionnelles |
| 03 | [Profils et permissions](03-profils-permissions.md) | Modèle d'autorisation, rôles, matrice des droits |
| 04 | [Modèle de données](04-modele-donnees.md) | Entités, relations, contraintes, index, règles de suppression |
| 05 | [Workflows administratifs](05-workflows.md) | Courrier entrant et sortant, validation, transmission, archivage, élimination |
| 06 | [Risques](06-risques.md) | Risques techniques et réglementaires, mesures |
| 07 | [Plan de développement](07-plan-lots.md) | Lots, livrables et critères d'acceptation |
| 08 | [Hypothèses et questions](08-hypotheses.md) | Ce que l'institution doit confirmer avant le lot 1 |
| — | [Compte rendu du lot 1](lot-01-compte-rendu.md) | Livrables, tests, écarts, prochaines actions |
| — | [Compte rendu du lot 2](lot-02-compte-rendu.md) | Organisation, habilitations, sécurité de connexion, écrans d'administration |
| — | [Compte rendu du lot 3](lot-03-compte-rendu.md) | Documents, versions, quarantaine, antivirus, aperçu et téléchargement contrôlés |
| — | [Interface Angular](interface-angular-compte-rendu.md) | API REST, interface Angular animée, FR/AR, CSP stricte, tests |
| — | [Dictionnaire de données](dictionnaire-donnees.md) | Tables et colonnes, généré par `manage.py dictionnaire_donnees` |

## Validation attendue

1. Confirmer ou corriger chaque hypothèse du document 08 (les hypothèses H1 à H6 bloquent le lot 1).
2. Valider l'architecture (document 01) et le périmètre du MVP (document 02).
3. Valider la matrice des rôles (document 03) avec le futur administrateur fonctionnel et l'archiviste.
4. Désigner les interlocuteurs : référent métier (bureau d'ordre), archiviste, responsable de la sécurité informatique, juriste.
