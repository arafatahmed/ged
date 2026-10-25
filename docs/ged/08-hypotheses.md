# 08. Hypothèses à confirmer

Les hypothèses **H1 à H6 bloquent le démarrage du lot 1**. Les autres peuvent être confirmées en cours de MVP, avant le lot indiqué.

| N° | Hypothèse retenue dans ce dossier | À confirmer par | Effet si elle est fausse | Avant le lot |
|---|---|---|---|---|
| H1 | L'institution pilote est l'ENAJM (Nouakchott, Mauritanie), déduite du dépôt GRH ; l'application reste générique et sans référence à l'ENAJM dans le code | Commanditaire | Aucun sur le code ; change les règles et le jeu de paramètres initiaux | 1 |
| H2 | La GED est une application distincte, dans un **dépôt dédié** (par exemple `ged`), sans dépendance au code de la GRH | Commanditaire | Si elle doit vivre dans ce dépôt : sous-dossier `ged/` avec sa propre intégration continue | 1 |
| H3 | Le cadre juridique applicable est mauritanien : loi n° 2017-020 relative à la protection des données à caractère personnel, textes sur les archives publiques, les transactions et la signature électroniques, la cybersécurité et la commande publique. **Ces références n'ont pas été vérifiées et doivent être établies par le juriste de l'institution** | Juriste | Change les règles de conservation, les formalités, la valeur des visas et signatures, pas l'architecture | 1 |
| H4 | Volumes : environ 300 utilisateurs, 50 simultanés, 50 000 documents par an, 2 Mo par document en moyenne ; quelques agences distantes | Commanditaire, DSI | Dimensionnement serveurs et stockage ; si au-delà de quelques millions de documents ou de centaines d'utilisateurs simultanés, réévaluer OpenSearch | 1 |
| H5 | Hébergement sur serveur(s) Linux internes à l'institution (ou cloud privé national) ; scanners existants à inventorier (modèles, numérisation vers dossier réseau ou courriel possible ?) | DSI | Hébergement externe : chiffrement et clauses contractuelles renforcés ; sans scanner réseau : agent local nécessaire dès le MVP | 1 |
| H6 | Pile technique : Django, Angular, PostgreSQL, MinIO, Celery, Redis, Nginx, Docker Compose ; l'équipe de maintenance future est compétente ou sera formée en Python et TypeScript | Commanditaire, DSI | Une autre pile imposée (par exemple Java) change le lot 1 mais pas le modèle ni les règles | 1 |
| H7 | Quatre niveaux de confidentialité (public interne, restreint, confidentiel, secret), libellés à adapter | Responsable sécurité | Ajustement de paramètres | 2 |
| H8 | Pas de signature électronique légale dans le MVP ; un prestataire conforme sera choisi plus tard | Juriste, commanditaire | Si exigée dès le MVP : choisir le prestataire maintenant (procédure d'achat, délais) | 17 |
| H9 | Pas d'annuaire central (LDAP, Active Directory) ni de SSO existant ; authentification locale avec MFA, OIDC activable | DSI | Si un annuaire existe : intégration OIDC (Keycloak fédéré à l'annuaire) dès le lot 2 | 2 |
| H10 | RPO 15 min, RTO 4 h, disponibilité 99 % en heures ouvrées ; un second site ou support pour les sauvegardes hors site est disponible | DSI, commanditaire | Objectifs plus stricts : haute disponibilité (lot 19) à avancer ; pas de site distant : support amovible chiffré en rotation | 10 |
| H11 | Une personne de la DSI sera formée à l'exploitation ; un contrat de maintenance est envisagé | Commanditaire | Sans exploitant : risque R11 non maîtrisé, envisager une infogérance | 10 |
| H12 | Le français et l'arabe suffisent ; dates en calendrier grégorien ; chiffres arabes occidentaux (0-9) par défaut, chiffres arabes orientaux en option | Commanditaire | Autre langue : table de traductions ; calendrier hégirien affiché en complément si demandé | 1 |
| H13 | Les circuits courants sont linéaires (entrant, sortant, validation à 2 ou 3 niveaux) ; les circuits parallèles sont minoritaires | Bureau d'ordre, directions | Circuits parallèles indispensables au démarrage : avancer le lot 13 | 7 |
| H14 | Un plan de classement et un tableau de gestion (durées de conservation) existent ou seront élaborés avec l'archiviste et l'autorité des archives | Archiviste | Sans eux, le module archives démarre avec un plan minimal et des durées à compléter | 9 |
| H15 | Le manuscrit n'est pas à reconnaître par OCR ; seuls les documents dactylographiés le sont | Commanditaire | Le manuscrit arabe nécessiterait un moteur spécialisé et une évaluation dédiée | 12 |
| H16 | La reprise des pièces du personnel de la GRH est souhaitée, mais pas prioritaire | Service RH | Si prioritaire : script de reprise au lot 4 | 11 |

## Questions ouvertes complémentaires

1. Quelles unités et quels utilisateurs participent au pilote (un bureau d'ordre central, une direction) ?
2. Quels modèles de documents (en-têtes, courriers types) doivent être produits par l'application ?
3. Les références actuelles des registres papier doivent-elles être reprises (format de numérotation existant) ?
4. Les agences ont-elles une connexion permanente au site central, et avec quel débit ?
5. Existe-t-il une politique de sécurité des systèmes d'information ou une charte informatique à respecter ?
6. Quelle est l'autorité compétente pour viser les éliminations d'archives publiques ?
