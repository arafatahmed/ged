# 06. Risques techniques et réglementaires

Échelle : probabilité et impact en Faible, Moyen, Élevé.

## 6.1 Risques techniques

| N° | Risque | Prob. | Impact | Mesures |
|---|---|---|---|---|
| R1 | **Documents personnels déjà exposés dans le dépôt GRH** : 154 pièces nominatives (`src/main/webapp/images/documents/`) et les identifiants MySQL (`WEB-INF/applicationContext.xml`) sont versionnés dans Git | Avérée | Élevé | Hors périmètre de la GED, mais à traiter avant toute ouverture du dépôt : retirer ces fichiers du suivi, purger l'historique (décision du propriétaire du dépôt), changer le mot de passe MySQL, restreindre l'accès au dépôt. La GED ne stockera aucun document dans le code ni dans un dossier web public |
| R2 | Fuite par les fonctions annexes (recherche, extraits, compteurs, suggestions, doublons, notifications, exports) qui contournent le contrôle d'accès | Moyenne | Élevé | Fonction unique `filtrer_visibles` ; tests d'autorisation automatisés sur chaque point d'API, y compris les compteurs et les extraits ; revue de code obligatoire sur le module `acces` |
| R3 | Doublons de numéros lors d'enregistrements simultanés | Moyenne | Élevé | Compteur verrouillé (`SELECT … FOR UPDATE`) dans la transaction de création, contrainte d'unicité en base ; test de charge avec 50 enregistrements simultanés sur la même série |
| R4 | Qualité de l'OCR arabe insuffisante (scans de mauvaise qualité, écriture manuscrite, mise en page mixte FR/AR) | Élevée | Moyen | Mesure sur un échantillon réel de 200 pages avant le lot 12 ; prétraitement (redressement, contraste) ; résultat OCR présenté comme aide à la recherche, jamais comme transcription fiable ; le manuscrit est hors périmètre |
| R5 | Recherche plein texte arabe : racinisation et variantes orthographiques (hamza, ta marbuta, alif maqsura) | Moyenne | Moyen | Normalisation du texte arabe avant indexation, configuration de recherche arabe de PostgreSQL complétée par recherche trigramme ; jeu de requêtes de référence validé par des utilisateurs arabophones |
| R6 | Numérisation : un navigateur ne pilote pas un scanner | Certaine | Moyen | MVP : scanners réseau ou copieurs qui déposent dans un dossier surveillé ou envoient par courriel interne, puis indexation dans la GED ; lot 12 : agent local de numérisation (logiciel libre ou commercial) à choisir après inventaire du parc (hypothèse H5) |
| R7 | Volume de stockage sous-estimé, saturation des disques | Moyenne | Élevé | Supervision et alerte à 70 % ; numérisation par défaut en 300 dpi niveaux de gris compressé ; stockage objet extensible |
| R8 | Sauvegardes non restaurables découvertes le jour du sinistre | Moyenne | Élevé | Test de restauration automatisé mensuel et supervisé ; procédure écrite testée par une personne autre que son auteur |
| R9 | Perte des clés de chiffrement des sauvegardes | Faible | Élevé | Clés en double exemplaire sous séquestre (coffre physique et responsable désigné), procédure de récupération testée |
| R10 | Fichiers malveillants ou piégés (macros, PDF actifs, bombes de décompression) | Moyenne | Élevé | Quarantaine, type réel vérifié, antivirus, limites de taille et de nombre de pages, conversion en aperçu dans un conteneur isolé sans réseau |
| R11 | Compétences d'exploitation insuffisantes dans l'institution (Docker, PostgreSQL, sauvegardes) | Élevée | Élevé | Composants limités au nécessaire ; scripts d'exploitation ; formation ; guide d'incident ; contrat de maintenance à prévoir (hypothèse H11) |
| R12 | Dérive du périmètre (demandes de circuits sur mesure pour chaque unité) | Élevée | Moyen | Circuits configurables plutôt que développés ; comité de validation des demandes ; MVP borné |
| R13 | Infrastructure réseau et électrique instable (coupures, débit entre sites) | Moyenne | Moyen | Onduleur et arrêt propre ; transactions courtes ; envois de fichiers reprenables (envoi par morceaux) pour les agences distantes ; interface légère |
| R14 | Obsolescence technique (la GRH actuelle repose sur des composants abandonnés depuis plus de dix ans) | Moyenne | Moyen | Versions à support long (Django LTS, PostgreSQL, Angular LTS), mises à jour planifiées deux fois par an, dépendances surveillées (alertes de vulnérabilité) |

## 6.2 Risques réglementaires et organisationnels

| N° | Risque | Prob. | Impact | Mesures |
|---|---|---|---|---|
| G1 | Cadre juridique applicable mal identifié (protection des données, archives publiques, transactions et signature électroniques, cybersécurité, commande publique) | Moyenne | Élevé | Revue par le juriste de l'institution avant le lot 1 (hypothèse H3) ; les références réglementaires sont des paramètres (règles de conservation, niveaux de confidentialité), pas du code |
| G2 | Confusion entre visa interne et signature électronique ayant valeur légale | Moyenne | Élevé | Terminologie distincte à l'écran et dans la documentation ; signature électronique uniquement par prestataire conforme (lot 17) |
| G3 | Présentation abusive du système comme archivage à valeur probante certifié | Moyenne | Élevé | Le système fournit intégrité (empreintes, chaînage d'audit, immutabilité) et traçabilité ; une qualification probante exige en plus une politique d'archivage, des procédures, et le cas échéant une certification ou un horodatage qualifié, à décider avec l'autorité des archives |
| G4 | Élimination de documents soumis à obligation de conservation ou à contentieux | Faible | Élevé | Gel bloquant, double validation, revérification à l'exécution, procès-verbal (circuit W6) |
| G5 | Traitement de données personnelles sans base légale ou formalités (déclaration ou autorisation auprès de l'autorité de protection des données) | Moyenne | Élevé | Registre des traitements, information des personnes, formalités à accomplir par l'institution ; minimisation des métadonnées ; durées de conservation des journaux fixées |
| G6 | Transmission de documents confidentiels à un service externe (OCR en ligne, messagerie, nuage public) | Moyenne | Élevé | Aucun service externe dans l'architecture ; tout connecteur externe est désactivé par défaut et son activation est journalisée et soumise à autorisation explicite |
| G7 | Résistance au changement, double circuit papier et numérique durable | Élevée | Moyen | Démarrage pilote par le bureau d'ordre ; formation ; parcours fréquents optimisés ; mesure de l'adoption |
| G8 | Abus de privilèges internes (administrateur qui consulte des dossiers sensibles) | Moyenne | Élevé | Séparation administration et contenu, MFA, journalisation des consultations sensibles, revue périodique par l'auditeur |
| G9 | Dépendance à un prestataire ou à une licence | Faible | Moyen | Composants libres, formats ouverts (PDF/A, CSV, JSON), export complet documenté, code et documentation remis à l'institution |
| G10 | Achat public : la mise en production peut exiger une procédure de commande publique (hébergement, matériel, signature, maintenance) | Moyenne | Moyen | Identifier tôt les éléments à acquérir (serveurs, scanners, prestataire de signature) et les délais de procédure |
