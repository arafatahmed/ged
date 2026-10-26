# Compte rendu du lot 3 : documents et stockage

**Statut : livré en développement et déployé en local, en attente de recette.** Code dans [`ged/documents/`](../../ged/documents/), règles d'accès dans [`ged/acces/documents.py`](../../ged/acces/documents.py), écrans dans [`ged/frontend/src/app/pages/documents/`](../../ged/frontend/src/app/pages/documents/).

## Livrables

| Livrable | Emplacement |
|---|---|
| Types de documents (formats admis, confidentialité par défaut) et métadonnées personnalisées (texte, nombre, date, liste ; obligatoires ou non), désactivées plutôt que supprimées | `documents/models.py`, écran `/administration/types-document` |
| Documents : fiche descriptive, mots-clés, métadonnées validées contre les définitions du type, statut | `documents/services.py` |
| Envoi de fichiers en quarantaine, contrôle du type réel (signature et extension), taille maximale paramétrable, SHA-256 | `documents/formats.py`, `documents/services.py` |
| Analyseur en arrière-plan : antivirus ClamAV, recalcul de l'empreinte, nouveau contrôle du type, publication ou refus ; nettoyage des envois interrompus | `documents/analyse.py`, service Compose `analyseur` |
| Client ClamAV (protocole INSTREAM, sans dépendance) | `documents/antivirus.py`, service Compose `antivirus` |
| Versions successives (la précédente n'est jamais écrasée), pièces jointes, relations entre documents (réponse à, annule, remplace, annexe de, voir aussi) | `documents/services.py` |
| Détection des doublons limitée aux documents visibles | `documents/services.py` (`doublons_visibles`) |
| Aperçu (PDF et images) et téléchargement contrôlés, journalisés | `documents/api.py` |
| Règles d'accès de la matrice 3.5 pour les documents, dont les cases « P » (objets propres) | `acces/documents.py`, permissions `document.*_propres` |
| Écrans Angular : liste filtrée, enregistrement (fichier à gauche, fiche à droite), fiche avec versions, aperçu, relations et doublons ; FR/AR | `frontend/src/app/pages/documents/` |
| Parcours navigateur des écrans du lot | `frontend/e2e/parcours-documents.mjs` |

## Critères d'acceptation

| Critère (document 07) | Résultat |
|---|---|
| Un fichier EICAR est refusé | **Atteint**, à deux niveaux. Un fichier EICAR brut (sans signature de format admis) est refusé dès l'envoi par le contrôle du type. Un document bureautique valide contenant EICAR passe ce contrôle, puis ClamAV le détecte (`Eicar-Test-Signature`) : le fichier est marqué infecté, effacé du stockage, non téléchargeable, et l'événement est journalisé. Vérifié sur la pile Docker avec le vrai ClamAV (parcours de bout en bout et `test_eicar_detecte_par_clamav_reel`) |
| Un `.exe` renommé en `.pdf` est refusé | **Atteint** : refus à l'envoi (400), rien n'est stocké, refus journalisé (`test_executable_renomme_en_pdf_refuse_sans_rien_stocker`, et sur la pile) |
| Un fichier n'est jamais accessible par une URL sans contrôle | **Atteint** : bucket privé, clés d'objet aléatoires jamais transmises au navigateur (`test_la_cle_de_stockage_n_est_jamais_exposee`), aucune URL présignée ; les octets passent uniquement par l'API, qui contrôle les droits et l'état de l'analyse |
| Une nouvelle version n'écrase pas la précédente | **Atteint** : la version 1 reste téléchargeable et identique après l'ajout de la version 2 (`test_une_nouvelle_version_n_ecrase_pas_la_precedente`, et sur la pile) |
| L'empreinte recalculée correspond | **Atteint** : l'analyseur recalcule le SHA-256 en relisant le stockage et refuse un fichier modifié entre-temps (`test_fichier_modifie_dans_le_stockage_refuse`) ; le fichier téléchargé à travers Nginx a la même empreinte |
| Règles « A » et « P » de la matrice (reportées du lot 2) | **« P » atteintes** : télécharger, modifier et versionner ses propres documents (producteur ; modification avant transmission pour le bureau d'ordre), testées dans `TestDroits::test_matrice`. **« A » reportées au lot 7** : elles dépendent des transmissions et des accès explicites |

## Règles d'accès appliquées aux documents

1. La fiche est visible avec `document.consulter` ou `document.consulter_metadonnees` dans l'unité propriétaire (sous-unités comprises si l'affectation est étendue), ou pour l'auteur qui détient `document.creer` dans cette unité.
2. Le niveau d'habilitation doit être au moins celui du document. Au niveau Secret, la liste nominative se limite à l'auteur jusqu'au lot 7.
3. L'aperçu exige le contenu (`document.consulter` ou être l'auteur) : un auditeur voit la fiche, pas le fichier.
4. Abaisser la confidentialité exige `document.confidentialite` et la modification sur tout le périmètre ; la relever est permis à qui peut modifier le document et détient `document.confidentialite`. Jamais au-delà de sa propre habilitation.
5. Un document validé ou archivé n'est plus modifiable ni versionnable.
6. Hors périmètre : 404, comme pour un document inexistant. Action refusée sur un document visible : 403 et trace `acces.refus`.
7. Journalisés : création, modification (noms des champs, jamais leur contenu), version, pièce jointe, relations, refus de fichier, verdicts de l'analyseur, chaque téléchargement, et toute consultation ou aperçu d'un document Confidentiel ou Secret.

## Contrôles réalisés

| Contrôle | Résultat |
|---|---|
| Tests backend (pytest, PostgreSQL) | 300 réussis, couverture 93 % ; 1 test ignoré hors pile (ClamAV réel), joué à part contre le service `antivirus` : réussi |
| Analyse statique, migrations, dictionnaire de données, traductions arabes, `check --deploy` | Sans alerte ; catalogue arabe complet (les entrées approximatives produites par la fusion ont été corrigées) |
| Tests frontend (Vitest) | 22 réussis (garde des documents, taille des fichiers, métadonnées) |
| Compilation de production Angular | Réussie ; chargement initial 743 ko (171 ko compressés), contre 722 ko avant le lot (le chiffre de 497 ko du compte rendu de l'interface était périmé) |
| Parcours de bout en bout sur la pile Docker, à travers Nginx (API) | 13 étapes réussies : dépôt, analyse ClamAV, téléchargement depuis SeaweedFS avec empreinte identique, aperçu, version 2, pièce jointe, EICAR détecté, exécutable déguisé refusé, doublon, relation, recherche |
| Parcours navigateur (Chrome, CSP active) | 6 étapes réussies, aucune violation de CSP ni erreur Angular : changement du mot de passe temporaire, liste, création avec dépôt du fichier, fiche avec aperçu après analyse, arabe, mobile |

Captures : [enregistrement](captures/documents-nouveau.png), [fiche](captures/documents-fiche.png), [fiche en arabe](captures/documents-fiche-arabe.png), [liste sur mobile](captures/documents-mobile.png).

## Écarts et limites

- **File d'attente en base au lieu de Celery** (écart à l'hypothèse H6) : l'analyseur lit la table des fichiers avec `SELECT … FOR UPDATE SKIP LOCKED`. Plusieurs analyseurs peuvent tourner en parallèle, et il n'y a pas de courtier de messages à exploiter. Celery reste envisageable si les traitements asynchrones se multiplient (OCR au lot 12).
- **Reconnaissance du type par signature** (bibliothèque `filetype`, Python pur) plutôt que libmagic : formats admis PDF, PNG, JPEG, TIFF, docx, xlsx, pptx, odt, ods, odp. Les anciens formats Office (doc, xls, ppt), qui peuvent porter des macros, et les formats sans signature fiable (texte, CSV) ne sont pas admis. À revoir si l'institution en a besoin.
- **Signatures antivirales** : le service `antivirus` est le seul autorisé à sortir du réseau interne, pour mettre à jour ses signatures (freshclam). Sur un réseau isolé, il faut un miroir interne. Le premier démarrage télécharge environ 300 Mo de signatures, et ClamAV occupe environ 1,3 Go de mémoire.
- **La chaîne EICAR placée en fin de fichier n'est pas détectée** : c'est la norme EICAR (la chaîne doit ouvrir le fichier), pas un défaut. Un document de l'essai porte ce titre dans l'installation locale.
- **Aperçu** : les PDF s'ouvrent dans la visionneuse du navigateur (nouvel onglet) et les images s'affichent dans la fiche. Pas d'aperçu des formats bureautiques (téléchargement seulement) : il faudrait une conversion côté serveur.
- **Doublons** : signalés après l'envoi, dans la fiche. L'action « lier au document existant au lieu de poursuivre » n'est pas proposée.
- **Pas de référence ni de numérotation des documents** : elles viennent avec le courrier (lot 5). Pas de changement de type ni d'unité propriétaire (transfert entre unités au lot 4).
- **Les pièces jointes sont rattachées à la version courante** : une nouvelle version ne les reprend pas.
- **Validation et immuabilité des versions validées** (déclencheur) : avec les circuits (lot 7).
- Les champs de date suivent la langue du navigateur (limite déjà connue de l'interface).

## Installation locale

Pile déployée le 25 octobre 2026 sur le poste de développement (Windows 10, Docker Desktop) : 7 services (PostgreSQL, Redis, SeaweedFS, web, analyseur, ClamAV, Nginx) sur https://localhost:8443. Données de démonstration : type « Note de service » (métadonnées « Destinataires » et « Urgence ») et compte `agent.demo` (validateur sur toute l'institution, habilitation Confidentiel). L'administrateur fonctionnel n'accède pas au contenu des documents (matrice 3.5) : il administre les types.

## Prochaines actions

1. Recette des écrans avec un agent producteur et le bureau d'ordre pilote.
2. Faire valider la liste des formats admis et la taille maximale (paramètre `fichiers.taille_max_mo`).
3. Choisir la source des signatures antivirales (accès Internet sortant ou miroir interne).
4. Lot 4 (classement et dossiers) et lot 5 (courrier) : ils s'appuient sur les documents de ce lot.
