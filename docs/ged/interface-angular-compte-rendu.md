# Compte rendu : interface Angular

**Statut : livrée en développement, en attente de recette.** Toutes les interfaces des lots 1 et 2 sont passées en Angular, à la demande du commanditaire ; Django ne sert plus que l'API, l'administration technique, la sonde et le logo.

## Ce qui a changé

| Avant | Après |
|---|---|
| Pages rendues par Django (gabarits) | Application Angular 21 (`ged/frontend/`) servie par Nginx |
| Formulaires HTML et redirections | API REST JSON (`/api/v1/session/`, `/compte/`, `/administration/`), format d'erreur unique `{detail, erreurs}` |
| Middleware : redirections | Pour l'API : réponses 401/403 avec un code (`session_expiree`, `changement_mot_de_passe_requis`, `mfa_requise`) que l'interface interprète |
| CSP : styles `'self'` | CSP stricte avec nonce aléatoire par réponse (styles injectés par Angular), aucun script en ligne |

Les règles métier (moteur d'accès, anti-escalade, verrouillage, double authentification, audit) sont inchangées : les services du lot 2 sont appelés par l'API au lieu des vues.

## Interface

- **Connexion en étapes** sur un écran scindé animé (halos en mouvement, panneau vitré) : mot de passe, puis code à 6 chiffres soumis automatiquement, ou activation de la double authentification avec QR code et codes de secours (coche animée tracée en SVG). Erreur signalée par une secousse du panneau.
- **Coque** : barre aux couleurs de l'institution (dégradé calculé à partir de ses deux couleurs), menu latéral réduit à un tiroir sur mobile, sélecteur de langue, menu du profil.
- **Tableau de bord** : bannière d'accueil selon l'heure, indicateurs du périmètre dont les valeurs défilent jusqu'à leur valeur, raccourcis selon les droits.
- **Mon compte** : langue, mot de passe (jauge de robustesse), double authentification, affectations, délégations (dialogue), sessions ouvertes.
- **Administration** : arbre des unités dépliable (dépliage animé, recherche qui déplie les branches correspondantes), types d'unité, postes, utilisateurs (recherche différée, filtres en pastilles, tri, pagination serveur), fiche utilisateur à onglets (affectations, profil, actions de sécurité en cartes, activité en chronologie), éditeur de rôle par groupes de permissions, journal des connexions.
- **Animations** : transitions entre pages (API View Transitions), entrées échelonnées des listes et cartes (`animate.enter` natif d'Angular), dialogues, squelettes de chargement, survols. Toutes sont désactivées si le système demande de réduire les mouvements (`prefers-reduced-motion`).
- **Français et arabe** changeables à chaud, mise en page miroir (RTL) complète, libellés métier bilingues (unités, rôles, postes), dates localisées avec chiffres occidentaux, pagination traduite. Les messages d'erreur de l'API arrivent traduits (en-tête `X-Langue`).
- **Accessibilité** : lien d'évitement, navigation au clavier (lignes de tableau activables à la touche Entrée), étiquettes ARIA, contrastes, focus visible.
- **Souveraineté** : polices (IBM Plex Sans Arabic) et icônes (Material Symbols) servies par l'application ; aucune ressource externe.

Captures (production, CSP active) : [connexion](captures/connexion.png), [double authentification](captures/double-authentification.png), [accueil](captures/accueil.png), [organisation en arabe](captures/organisation-arabe.png), [fiche utilisateur](captures/fiche-utilisateur.png), [éditeur de rôle](captures/editeur-role.png), [mobile](captures/mobile-utilisateurs.png).

## Sécurité

- Session Django : cookie HttpOnly et SameSite=Strict, aucun jeton dans le navigateur (pas de stockage local de secret).
- CSRF : jeton dans l'en-tête `X-CSRFToken` pour toute écriture ; la connexion elle-même est protégée (DRF ne le fait pas pour un visiteur non connecté), testé.
- Les gardes de navigation masquent ce qui n'est pas autorisé, mais **le serveur reste seul juge** : chaque appel d'API repasse par le moteur d'accès.
- Nginx : CSP stricte avec nonce (`$request_id`) recopié dans `index.html`, `index.html` jamais mis en cache, fichiers à empreinte mis en cache un an. L'administration technique de Django garde une CSP séparée (styles en ligne autorisés pour elle seule).
- Correction métier découverte pendant les essais : créer une seconde unité racine la sortait du périmètre de l'administrateur fonctionnel. Une seule racine est désormais admise (celle qui représente l'institution) ; testé.

## Contrôles réalisés

| Contrôle | Résultat |
|---|---|
| Tests backend (pytest, PostgreSQL), dont l'API complète | 240 réussis, 1 ignoré sans rôle applicatif, couverture 94 % |
| Tests frontend (Vitest) : traduction et paramètres des traductions, dates, session, gardes, intercepteurs, pagination | 18 réussis ; ils ont révélé et fait corriger un défaut (garde appelant `inject()` après un `await`) |
| Compilation de production Angular (types stricts dans les gabarits, traductions complètes imposées par le compilateur) | Réussie ; pages chargées à la demande. Le chargement initial mesuré lors du déploiement local du 25 octobre 2026 est de 722 ko (168 ko compressés), et non 497 ko comme indiqué d'abord |
| Parcours de bout en bout dans Chromium sur le build de production, derrière un frontal reproduisant la CSP et le nonce de Nginx | 8 étapes réussies, aucune violation de CSP ni erreur Angular ; parcours étendu (23 écrans) joué en français, en arabe et sur mobile |
| `docker compose config` | Valide. Les images n'ont pas été construites (pas de démon Docker dans l'environnement de développement) |

## Limites et suites

- Construction des images Docker et installation complète : **faites en local** le 25 octobre 2026 (Windows 10, Docker Desktop) ; parcours vérifié jusqu'à l'étape d'activation de la double authentification. Reste l'installation sur le serveur de recette de l'institution.
- Défaut connu d'Angular 21.2 : deux composants aux styles en ligne strictement identiques empêchent `ng build` de rendre la main (le service esbuild reste ouvert). Les styles communs vont donc dans `src/styles.scss`.
- Les champs de date utilisent le sélecteur natif du navigateur, qui suit la langue du navigateur et non celle de l'interface.
- Le parcours de bout en bout (`npm run e2e`) n'est pas encore joué en intégration continue : il demande Django, une base neuve et un navigateur.
- Lot 3 (documents) : les écrans seront construits directement en Angular sur ce socle.
