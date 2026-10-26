import { HttpClient, HttpParams } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { Observable } from 'rxjs';

import {
  Compte,
  Delegation,
  DocumentDetail,
  DocumentResume,
  Enrolement,
  EvenementConnexion,
  FormatFichier,
  OptionsDelegation,
  OptionsDocuments,
  OptionsUtilisateurs,
  Page,
  PermissionCatalogue,
  Poste,
  Role,
  Session,
  TypeDocument,
  TypeUnite,
  Unite,
  UtilisateurDetail,
  UtilisateurResume,
} from './modeles';

const BASE = '/api/v1';
const ADMIN = `${BASE}/administration`;
const DOCUMENTS = `${BASE}/documents`;

function parametres(filtres: Record<string, string | number>): HttpParams {
  let params = new HttpParams();
  for (const [cle, valeur] of Object.entries(filtres)) {
    if (valeur !== '' && valeur !== null && valeur !== undefined) params = params.set(cle, String(valeur));
  }
  return params;
}

/** Accès typé à l'API Django. Les droits sont toujours vérifiés côté serveur. */
@Injectable({ providedIn: 'root' })
export class ApiService {
  private readonly http = inject(HttpClient);

  // Session
  session(): Observable<Session> {
    return this.http.get<Session>(`${BASE}/session/`);
  }
  connexion(identifiant: string, motDePasse: string): Observable<Session> {
    return this.http.post<Session>(`${BASE}/session/connexion/`, { identifiant, mot_de_passe: motDePasse });
  }
  verification(code: string): Observable<Session> {
    return this.http.post<Session>(`${BASE}/session/verification/`, { code });
  }
  enrolement(): Observable<Enrolement> {
    return this.http.get<Enrolement>(`${BASE}/session/enrolement/`);
  }
  confirmerEnrolement(code: string): Observable<{ codes_secours: string[]; session: Session }> {
    return this.http.post<{ codes_secours: string[]; session: Session }>(`${BASE}/session/enrolement/`, { code });
  }
  deconnexion(): Observable<Session> {
    return this.http.post<Session>(`${BASE}/session/deconnexion/`, {});
  }

  // Mon compte
  compte(): Observable<Compte> {
    return this.http.get<Compte>(`${BASE}/compte/`);
  }
  changerLangue(langue: string): Observable<Compte> {
    return this.http.patch<Compte>(`${BASE}/compte/`, { langue });
  }
  changerMotDePasse(ancien: string, nouveau: string, confirmation: string): Observable<Session> {
    return this.http.post<Session>(`${BASE}/compte/mot-de-passe/`, { ancien, nouveau, confirmation });
  }
  desactiverMfa(): Observable<void> {
    return this.http.post<void>(`${BASE}/compte/mfa/desactiver/`, {});
  }
  regenererCodes(): Observable<{ codes_secours: string[] }> {
    return this.http.post<{ codes_secours: string[] }>(`${BASE}/compte/mfa/codes/`, {});
  }
  fermerAutresSessions(): Observable<{ sessions_fermees: number }> {
    return this.http.post<{ sessions_fermees: number }>(`${BASE}/compte/sessions/fermer/`, {});
  }
  optionsMaDelegation(): Observable<OptionsDelegation> {
    return this.http.get<OptionsDelegation>(`${BASE}/compte/delegations/`);
  }
  creerMaDelegation(donnees: object): Observable<Delegation> {
    return this.http.post<Delegation>(`${BASE}/compte/delegations/`, donnees);
  }
  revoquerDelegation(uuid: string): Observable<void> {
    return this.http.post<void>(`${BASE}/compte/delegations/${uuid}/revoquer/`, {});
  }

  tableauDeBord(): Observable<{ indicateurs: Record<string, number> }> {
    return this.http.get<{ indicateurs: Record<string, number> }>(`${BASE}/tableau-de-bord/`);
  }

  // Organisation
  unites(): Observable<{ unites: Unite[]; types: TypeUnite[] }> {
    return this.http.get<{ unites: Unite[]; types: TypeUnite[] }>(`${ADMIN}/unites/`);
  }
  enregistrerUnite(donnees: object, uuid?: string): Observable<Unite> {
    return uuid
      ? this.http.patch<Unite>(`${ADMIN}/unites/${uuid}/`, donnees)
      : this.http.post<Unite>(`${ADMIN}/unites/`, donnees);
  }
  desactiverUnite(uuid: string): Observable<Unite> {
    return this.http.post<Unite>(`${ADMIN}/unites/${uuid}/desactiver/`, {});
  }
  typesUnite(): Observable<TypeUnite[]> {
    return this.http.get<TypeUnite[]>(`${ADMIN}/types-unite/`);
  }
  enregistrerTypeUnite(donnees: object, id?: number): Observable<TypeUnite> {
    return id
      ? this.http.patch<TypeUnite>(`${ADMIN}/types-unite/${id}/`, donnees)
      : this.http.post<TypeUnite>(`${ADMIN}/types-unite/`, donnees);
  }
  postes(): Observable<Poste[]> {
    return this.http.get<Poste[]>(`${ADMIN}/postes/`);
  }
  enregistrerPoste(donnees: object, id?: number): Observable<Poste> {
    return id
      ? this.http.patch<Poste>(`${ADMIN}/postes/${id}/`, donnees)
      : this.http.post<Poste>(`${ADMIN}/postes/`, donnees);
  }

  // Utilisateurs
  utilisateurs(filtres: Record<string, string | number>): Observable<Page<UtilisateurResume>> {
    return this.http.get<Page<UtilisateurResume>>(`${ADMIN}/utilisateurs/`, { params: parametres(filtres) });
  }
  optionsUtilisateurs(): Observable<OptionsUtilisateurs> {
    return this.http.get<OptionsUtilisateurs>(`${ADMIN}/utilisateurs/options/`);
  }
  creerUtilisateur(donnees: object): Observable<UtilisateurResume> {
    return this.http.post<UtilisateurResume>(`${ADMIN}/utilisateurs/`, donnees);
  }
  utilisateur(uuid: string): Observable<UtilisateurDetail> {
    return this.http.get<UtilisateurDetail>(`${ADMIN}/utilisateurs/${uuid}/`);
  }
  modifierUtilisateur(uuid: string, donnees: object): Observable<UtilisateurDetail> {
    return this.http.patch<UtilisateurDetail>(`${ADMIN}/utilisateurs/${uuid}/`, donnees);
  }
  actionUtilisateur(uuid: string, action: string, donnees: object = {}): Observable<UtilisateurDetail> {
    return this.http.post<UtilisateurDetail>(`${ADMIN}/utilisateurs/${uuid}/${action}/`, donnees);
  }
  reinitialiserMotDePasse(uuid: string): Observable<{ mot_de_passe: string; utilisateur: UtilisateurDetail }> {
    return this.http.post<{ mot_de_passe: string; utilisateur: UtilisateurDetail }>(
      `${ADMIN}/utilisateurs/${uuid}/mot-de-passe/`,
      {},
    );
  }
  ajouterAffectation(uuid: string, donnees: object): Observable<UtilisateurDetail> {
    return this.http.post<UtilisateurDetail>(`${ADMIN}/utilisateurs/${uuid}/affectations/`, donnees);
  }
  cloturerAffectation(uuid: string): Observable<UtilisateurDetail> {
    return this.http.post<UtilisateurDetail>(`${ADMIN}/affectations/${uuid}/cloturer/`, {});
  }
  optionsDelegationDe(uuid: string): Observable<OptionsDelegation> {
    return this.http.get<OptionsDelegation>(`${ADMIN}/utilisateurs/${uuid}/delegations/`);
  }
  creerDelegationPour(uuid: string, donnees: object): Observable<Delegation> {
    return this.http.post<Delegation>(`${ADMIN}/utilisateurs/${uuid}/delegations/`, donnees);
  }
  readonly urlRevueHabilitations = `${ADMIN}/utilisateurs/revue-habilitations.csv`;

  // Rôles
  roles(): Observable<{ roles: Role[]; permissions: PermissionCatalogue[] }> {
    return this.http.get<{ roles: Role[]; permissions: PermissionCatalogue[] }>(`${ADMIN}/roles/`);
  }
  enregistrerRole(donnees: object, uuid?: string): Observable<Role> {
    return uuid
      ? this.http.patch<Role>(`${ADMIN}/roles/${uuid}/`, donnees)
      : this.http.post<Role>(`${ADMIN}/roles/`, donnees);
  }

  // Journal des connexions
  connexions(page: number, action: string): Observable<Page<EvenementConnexion> & { actions: string[] }> {
    const params = new HttpParams().set('page', page).set('action', action);
    return this.http.get<Page<EvenementConnexion> & { actions: string[] }>(`${ADMIN}/connexions/`, { params });
  }

  // Types de documents (administration)
  typesDocument(): Observable<{ types: TypeDocument[]; formats: FormatFichier[] }> {
    return this.http.get<{ types: TypeDocument[]; formats: FormatFichier[] }>(`${ADMIN}/types-document/`);
  }
  enregistrerTypeDocument(donnees: object, uuid?: string): Observable<TypeDocument> {
    return uuid
      ? this.http.patch<TypeDocument>(`${ADMIN}/types-document/${uuid}/`, donnees)
      : this.http.post<TypeDocument>(`${ADMIN}/types-document/`, donnees);
  }

  // Documents
  documents(filtres: Record<string, string | number>): Observable<Page<DocumentResume>> {
    return this.http.get<Page<DocumentResume>>(`${DOCUMENTS}/`, { params: parametres(filtres) });
  }
  optionsDocuments(): Observable<OptionsDocuments> {
    return this.http.get<OptionsDocuments>(`${DOCUMENTS}/options/`);
  }
  /** Création en multipart : les métadonnées et mots-clés voyagent en JSON. */
  creerDocument(donnees: FormData): Observable<DocumentDetail> {
    return this.http.post<DocumentDetail>(`${DOCUMENTS}/`, donnees);
  }
  document(uuid: string): Observable<DocumentDetail> {
    return this.http.get<DocumentDetail>(`${DOCUMENTS}/${uuid}/`);
  }
  modifierDocument(uuid: string, donnees: object): Observable<DocumentDetail> {
    return this.http.patch<DocumentDetail>(`${DOCUMENTS}/${uuid}/`, donnees);
  }
  ajouterFichier(uuid: string, nature: 'versions' | 'pieces-jointes', donnees: FormData): Observable<DocumentDetail> {
    return this.http.post<DocumentDetail>(`${DOCUMENTS}/${uuid}/${nature}/`, donnees);
  }
  relier(uuid: string, cible: string, nature: string): Observable<DocumentDetail> {
    return this.http.post<DocumentDetail>(`${DOCUMENTS}/${uuid}/relations/`, { cible, nature });
  }
  supprimerRelation(uuid: string, id: number): Observable<DocumentDetail> {
    return this.http.delete<DocumentDetail>(`${DOCUMENTS}/${uuid}/relations/${id}/`);
  }
  /** Adresse d'un fichier : jamais une URL de stockage, toujours l'API qui contrôle les droits. */
  urlFichier(document: string, fichier: string, mode: 'apercu' | 'telecharger'): string {
    return `${DOCUMENTS}/${document}/fichiers/${fichier}/${mode}/`;
  }
}
