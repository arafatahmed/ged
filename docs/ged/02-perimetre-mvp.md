# 02. Périmètre fonctionnel du MVP

Le MVP couvre les lots 1 à 11 du [plan](07-plan-lots.md). Il doit permettre à une institution de remplacer son registre papier du courrier et de classer ses documents de façon sécurisée, traçable et sauvegardée.

## 2.1 Dans le MVP

| Domaine | Fonctions incluses |
|---|---|
| Administration de l'institution | Identité (nom FR/AR, sigle, logo, couleurs, coordonnées) ; arbre des unités organisationnelles avec types configurables ; postes ; paramètres généraux ; langue par défaut ; formats de date |
| Utilisateurs et habilitations | Comptes, rattachement à une ou plusieurs unités, rôles configurables, niveau d'habilitation de confidentialité, désactivation, révocation des sessions, politique de mot de passe, MFA (TOTP) pour les profils sensibles, journal des connexions, délégation temporaire |
| Documents | Fiche descriptive (champs communs et métadonnées personnalisées par type), envoi de fichiers, contrôle de type, antivirus, empreinte SHA-256, détection des doublons, versions successives, pièces jointes, relations entre documents, aperçu PDF et images, téléchargement contrôlé |
| Acquisition | Import depuis le poste (un ou plusieurs fichiers) ; import des fichiers produits par un scanner réseau ou un copieur (enregistrement puis indexation par l'agent) ; vérification des métadonnées avant validation de l'enregistrement |
| Dossiers et classement | Plan de classement hiérarchique configurable ; dossiers et sous-dossiers ; rattachement de documents ; responsable, statut, clôture et réouverture autorisées ; transfert entre unités ; dossiers confidentiels |
| Courrier | Registres entrant et sortant ; numérotation automatique sans doublon par séries configurables ; priorité, délai, unité responsable ; pièces jointes ; accusé de réception et preuve d'expédition (fichiers rattachés) ; historique des transmissions ; impression du bordereau et de l'étiquette de référence |
| Transmissions et circuits élémentaires | Transmission d'un courrier, document ou dossier à une unité ou une personne, pour attribution, information ou avis ; affectation à un agent ; circuit linéaire configurable (étapes, responsable par rôle ou unité, délai) ; décisions : valider, rejeter avec motif, retourner à l'étape précédente, demander un complément ; historique horodaté |
| Tâches et notifications internes | Corbeille « à traiter » ; validations en attente ; échéances proches et retards ; notifications dans l'application |
| Recherche | Référence, titre, objet, mots-clés, dates, expéditeur, destinataire, unité, type, statut, confidentialité ; plein texte sur le contenu texte des PDF natifs ; filtres, tri, pagination ; résultats et extraits filtrés par les droits |
| Archivage de base | Règles de conservation (durée, point de départ, sort final) rattachées au plan de classement ; calcul de la date d'échéance des dossiers clos ; gel pour contentieux bloquant toute élimination |
| Audit | Journal chaîné de tous les événements significatifs ; consultation filtrée par les auditeurs ; export CSV signé par empreinte |
| Exploitation | Déploiement Docker Compose ; sauvegarde et restauration scriptées et testées ; supervision de base ; guide d'installation |
| Interface | Français et arabe, RTL complet ; responsive ; navigation au clavier ; contraste conforme WCAG 2.1 AA sur les écrans du MVP |

## 2.2 Reporté après le MVP

| Fonction | Lot | Raison du report |
|---|---|---|
| OCR et recherche dans les documents numérisés | 12 | Chaîne asynchrone à part ; la qualité OCR arabe doit être mesurée sur des échantillons réels avant engagement |
| Numérisation pilotée depuis le navigateur (TWAIN/WIA), séparation et assemblage de pages, redressement | 12 | Un navigateur ne peut pas piloter un scanner sans agent local installé sur les postes (voir risque R6) |
| Extraction automatique de métadonnées | 12 | Dépend de l'OCR et des modèles de documents de l'institution |
| Circuits parallèles, conditions, escalade, délégation automatique | 13 | Le circuit linéaire couvre la majorité des cas ; les règles avancées seront définies avec les utilisateurs du MVP |
| Notifications par courriel | 14 | Dépend du serveur SMTP de l'institution |
| Versements, demandes de communication, éliminations avec procès-verbal | 15 | Procédure à valider avec l'archiviste et l'autorité nationale des archives |
| Tableaux de bord, statistiques, exports PDF et Excel | 16 | Le MVP fournit les compteurs de la page d'accueil ; les rapports seront construits sur des données réelles |
| Signature électronique qualifiée | 17 | Nécessite un prestataire conforme au droit applicable (hypothèse H8) |
| Mode multi-institutions | 18 | Prévu dans le modèle de données dès le lot 1, activé et testé plus tard |
| Reprise des pièces de la GRH | 11 (optionnel) | Script de reprise une fois le modèle stabilisé |

## 2.3 Exigences non fonctionnelles du MVP

| Exigence | Cible proposée (à confirmer, H4 et H10) |
|---|---|
| Temps de réponse | Recherche et listes paginées en moins de 2 s au 95e centile avec 50 utilisateurs simultanés et 500 000 documents |
| Envoi de fichiers | Jusqu'à 100 Mo par fichier (paramétrable) |
| Disponibilité | Heures ouvrées, 99 % ; maintenance planifiée hors heures ouvrées |
| Perte de données maximale (RPO) | 15 minutes |
| Temps de reprise (RTO) | 4 heures |
| Intégrité | Aucune référence en double, aucune transmission perdue, vérifié par tests de concurrence |
| Navigateurs | Deux dernières versions de Firefox, Chrome et Edge |
| Accessibilité | WCAG 2.1 niveau AA sur les parcours principaux |

## 2.4 Parcours prioritaires optimisés

Ces cinq parcours font l'objet de maquettes et de tests d'utilisabilité avant développement de l'interface :

1. **Enregistrer un courrier entrant** : un seul écran (fichier à gauche, fiche à droite), référence attribuée à l'enregistrement, impression de l'étiquette.
2. **Numériser ou importer un document** : dépôt glisser-déposer, aperçu immédiat, métadonnées pré-remplies selon le type.
3. **Retrouver un dossier** : barre de recherche globale (référence exacte ou texte), puis filtres.
4. **Affecter un traitement** : depuis la fiche, bouton « Transmettre », choix de l'unité ou de l'agent, instruction et délai.
5. **Valider un document** : depuis la corbeille, aperçu et boutons Valider, Rejeter (motif obligatoire), Retourner, Demander un complément.
