# 03. Profils et permissions

## 3.1 Principe : rôle, périmètre, puis conditions

Une permission seule ne suffit jamais. Une action est autorisée si **toutes** les conditions suivantes sont vraies :

1. **Rôle (RBAC)** : l'utilisateur détient, par une de ses affectations, un rôle qui contient la permission (par exemple `document.consulter`).
2. **Périmètre** : l'affectation porte sur l'unité propriétaire de l'objet, ou sur une unité parente si l'affectation s'étend aux sous-unités.
3. **Confidentialité** : le niveau d'habilitation de l'utilisateur est supérieur ou égal au niveau de l'objet. Au niveau le plus élevé, il faut en plus figurer sur la liste nominative de l'objet.
4. **Conditions contextuelles** : état de l'objet (un document validé ou archivé n'est plus modifiable), étape du workflow (seul le titulaire de la tâche décide), gel, règles d'archivage.

Indépendamment du rôle, un utilisateur obtient un accès **explicite et tracé** à un objet quand :

- l'objet lui a été transmis ou affecté (accès limité à ce que prévoit la transmission, et révocable) ;
- il est titulaire d'une tâche de workflow sur cet objet ;
- un partage nominatif lui a été accordé par une personne autorisée.

Ces accès explicites ne lèvent jamais la règle de confidentialité : on ne peut pas transmettre un document « secret » à quelqu'un qui n'est pas habilité à ce niveau.

Le refus est la valeur par défaut. Une agence qui connaît la référence d'un document d'une autre unité reçoit la même réponse que si le document n'existait pas (404).

## 3.2 Mise en œuvre

- Un seul module, `acces`, expose deux fonctions : `peut(utilisateur, action, objet)` pour un objet, et `filtrer_visibles(utilisateur, requete)` qui ajoute à une requête SQL les conditions de visibilité. Les listes, la recherche, les compteurs, les tableaux de bord et les exports utilisent `filtrer_visibles` ; aucun écran ne filtre lui-même.
- Les décisions sensibles (consultation d'un document confidentiel, téléchargement, export) sont journalisées, y compris les refus.
- Les permissions sont des codes stables définis dans le code (l'application doit savoir ce qu'elle contrôle) ; les **rôles** qui les regroupent sont des données configurables par l'institution. Les rôles ci-dessous sont fournis comme modèle initial.
- Une suite de tests d'autorisation (matrice rôle × action × situation) est exécutée à chaque modification ; voir le lot 2.

## 3.3 Niveaux de confidentialité (modèle initial, configurable)

| Niveau | Libellé proposé | Règle |
|---|---|---|
| 0 | Public interne | Tout utilisateur de l'unité propriétaire et des unités destinataires |
| 1 | Restreint | Utilisateurs de l'unité propriétaire habilités niveau 1 et destinataires explicites |
| 2 | Confidentiel | Habilitation niveau 2 et périmètre, ou accès explicite |
| 3 | Secret | Habilitation niveau 3 et liste nominative de l'objet ; aucun accès par simple périmètre |

Les libellés réglementaires exacts dépendent de l'institution et du droit applicable (hypothèse H7).

## 3.4 Rôles initiaux

| Rôle | Mission | Points de vigilance |
|---|---|---|
| Superadministrateur technique | Installation, paramètres techniques, création des institutions et de leurs administrateurs, supervision | **Aucun accès au contenu des documents ni aux métadonnées confidentielles.** MFA obligatoire. Toutes ses actions sont journalisées |
| Administrateur fonctionnel de l'institution | Organisation, utilisateurs, rôles, types de documents, plan de classement, séries, circuits, paramètres | N'accède pas au contenu par défaut ; un accès doit lui être attribué comme à tout agent. Ne peut pas s'attribuer à lui-même un rôle ou une habilitation (exige un second administrateur) |
| Administrateur d'unité | Gère les utilisateurs et les affectations de son unité et de ses sous-unités | Ne peut attribuer que des rôles et des niveaux inférieurs ou égaux aux siens |
| Agent du bureau d'ordre | Enregistre les courriers entrants et sortants, numérise, transmet pour attribution | Voit les courriers qu'il enregistre et les registres de son unité ; ne voit pas les suites données dans les autres unités |
| Agent producteur | Crée des documents, des versions, des projets de courrier sortant | Modification limitée à ses documents non validés |
| Agent traitant | Traite les objets qui lui sont affectés, annote, joint des pièces, propose une réponse | Accès limité aux objets affectés et à son unité |
| Responsable et validateur | Affecte, valide, rejette, retourne, signe dans l'application (visa interne) | Le visa n'est pas une signature électronique au sens juridique |
| Archiviste | Plan de classement et règles de conservation (avec l'administrateur), versements, communications, gels, propositions d'élimination | MFA obligatoire. L'élimination exige une seconde validation |
| Auditeur ou contrôleur | Consulte le journal d'audit et les métadonnées dans son périmètre ; exporte le journal | Lecture seule ; l'accès au contenu des documents confidentiels n'est pas inclus par défaut. MFA obligatoire |
| Consultation seule | Consulte les documents de son périmètre | Pas de téléchargement par défaut (permission distincte) |

## 3.5 Matrice des permissions (modèle initial)

Légende : **O** autorisé dans le périmètre ; **A** seulement sur les objets affectés ou transmis à l'utilisateur ; **P** seulement sur ses propres objets ; **—** interdit. Le périmètre et la confidentialité s'appliquent toujours en plus.

Dans le code (lot 3), une case « P » est une permission distincte suffixée `_propres` (par exemple `document.telecharger_propres`), qui ne s'exerce que sur les objets créés par l'utilisateur. Les cases « A » s'appuieront sur les accès explicites du lot 7.

| Permission | Sup. tech. | Adm. fonct. | Adm. unité | Bureau d'ordre | Producteur | Traitant | Validateur | Archiviste | Auditeur | Consult. |
|---|---|---|---|---|---|---|---|---|---|---|
| Paramètres techniques | O | — | — | — | — | — | — | — | — | — |
| Paramètres de l'institution, circuits, types | — | O | — | — | — | — | — | — | — | — |
| Unités et postes | — | O | O (sous-unités) | — | — | — | — | — | — | — |
| Utilisateurs et affectations | — | O | O (son unité) | — | — | — | — | — | — | — |
| Rôles et permissions | — | O | — | — | — | — | — | — | — | — |
| Plan de classement, conservation | — | O | — | — | — | — | — | O | — | — |
| Enregistrer un courrier | — | — | — | O | — | — | — | — | — | — |
| Créer un document | — | — | — | O | O | O | O | — | — | — |
| Consulter un document | — | — | — | O | O | A | O | O | O (métadonnées) | O |
| Télécharger l'original | — | — | — | O | P | A | O | O | — | — |
| Modifier les métadonnées | — | — | — | P (avant transmission) | P | A | O | O (métadonnées archivistiques) | — | — |
| Ajouter une version | — | — | — | — | P | A | O | — | — | — |
| Créer, clôturer un dossier | — | — | — | O | O | A | O | O | — | — |
| Rouvrir un dossier clos | — | — | — | — | — | — | O | O | — | — |
| Transmettre, affecter | — | — | — | O | P | A | O | — | — | — |
| Décider sur une tâche | — | — | — | A | A | A | A | A | — | — |
| Changer le niveau de confidentialité | — | — | — | — | P (à la hausse) | — | O | O | — | — |
| Gel, versement, élimination | — | — | — | — | — | — | — | O | — | — |
| Supprimer définitivement | — | — | — | — | — | — | — | via élimination validée | — | — |
| Consulter le journal d'audit | O (événements techniques) | O (administration) | — | — | — | — | — | O (archivage) | O | — |
| Exporter le journal, les résultats | — | O | — | — | — | — | O | O | O | — |

## 3.6 Règles de gestion des comptes

- Identifiant unique, mot de passe haché (Argon2id), longueur minimale 12 caractères, vérification contre une liste de mots de passe compromis, pas de rotation forcée sans motif.
- MFA (TOTP) obligatoire pour les rôles d'administration, archiviste et auditeur ; activable pour tous.
- Verrouillage progressif après échecs ; déverrouillage par un administrateur ou après délai.
- Désactivation plutôt que suppression : un compte désactivé ne peut plus se connecter, ses sessions sont révoquées, son historique est conservé.
- Départ ou mutation d'un agent : ses tâches en cours sont listées et doivent être réaffectées avant la clôture de l'affectation.
- Délégation : un validateur peut déléguer ses tâches à un autre utilisateur habilité, pour une période, avec mention de la délégation dans l'historique.
- Revue périodique des habilitations : liste exportable des comptes, rôles et niveaux par unité, à faire valider par chaque responsable.
