// Types des réponses de l'API Django (/api/v1).

export interface Institution {
  nom_fr: string;
  nom_ar: string;
  sigle: string;
  couleur_primaire: string;
  couleur_secondaire: string;
  langue_defaut: Langue;
  format_date: string;
  logo: boolean;
}

export type Langue = 'fr' | 'ar';
export type Etape = 'mfa' | 'enrolement' | null;

export interface Utilisateur {
  uuid: string;
  identifiant: string;
  nom: string;
  prenom: string;
  nom_complet: string;
  nom_ar: string;
  courriel: string;
  langue: Langue | '';
  niveau_habilitation: number;
  niveau_habilitation_libelle: string;
  superadministrateur: boolean;
  mfa_active: boolean;
}

export interface Droits {
  organisation: boolean;
  types_unite: boolean;
  utilisateurs: boolean;
  roles: boolean;
  connexions: boolean;
}

export interface Session {
  authentifie: boolean;
  etape: Etape;
  utilisateur: Utilisateur | null;
  institution: Institution | null;
  exigences?: { changer_mot_de_passe: boolean; activer_mfa: boolean };
  droits?: Droits;
}

export interface Enrolement {
  qr_code: string;
  secret: string;
  obligatoire: boolean;
}

export interface ErreurApi {
  detail?: string;
  code?: string;
  erreurs?: Record<string, string[]>;
}

export interface Page<T> {
  nombre: number;
  page: number;
  pages: number;
  resultats: T[];
}

export interface AffectationResume {
  uuid: string;
  role: string;
  role_ar: string;
  unite: string;
  unite_ar: string;
  unite_sigle: string;
  etendue_sous_unites: boolean;
  date_debut: string;
  date_fin: string | null;
}

export interface Delegation {
  uuid: string;
  delegant: string;
  delegataire: string;
  debut: string;
  fin: string;
  motif: string;
  roles: string[];
  revoquee: boolean;
}

export interface Compte {
  utilisateur: Utilisateur;
  affectations: AffectationResume[];
  sessions: { debut: string; adresse_ip: string; agent: string; courante: boolean }[];
  delegations_donnees: Delegation[];
  delegations_recues: Delegation[];
  mfa: { active: boolean; obligatoire: boolean; codes_restants: number };
}

export interface OptionsDelegation {
  delegataires: { uuid: string; libelle: string }[];
  roles: { uuid: string; libelle: string; libelle_ar: string }[];
}

export interface TypeUnite {
  id: number;
  code: string;
  libelle_fr: string;
  libelle_ar: string;
  ordre: number;
  actif: boolean;
  unites: number | null;
}

export interface Unite {
  uuid: string;
  code: string;
  sigle: string;
  libelle_fr: string;
  libelle_ar: string;
  type: number;
  type_libelle: string;
  type_libelle_ar: string;
  parent: string | null;
  profondeur: number;
  actif: boolean;
  affectations: number | null;
}

export interface Poste {
  id: number;
  intitule_fr: string;
  intitule_ar: string;
  unite: string;
  unite_libelle: string;
  superieur: number | null;
  superieur_libelle: string | null;
  actif: boolean;
}

export interface UtilisateurResume {
  uuid: string;
  identifiant: string;
  nom: string;
  prenom: string;
  nom_ar: string;
  actif: boolean;
  verrouille: boolean;
  mfa_active: boolean;
  derniere_connexion: string | null;
}

export interface Affectation {
  uuid: string;
  role: string;
  role_libelle: string;
  role_libelle_ar: string;
  unite: string;
  unite_libelle: string;
  poste_libelle: string | null;
  etendue_sous_unites: boolean;
  date_debut: string;
  date_fin: string | null;
  active: boolean;
  attribuee_par: string | null;
}

export interface UtilisateurDetail extends UtilisateurResume {
  courriel: string;
  langue: Langue | '';
  niveau_habilitation: number;
  doit_changer_mot_de_passe: boolean;
  echecs_connexion: number;
  affectations: Affectation[];
  sessions: { debut: string; fin: string | null; adresse_ip: string; motif_fin: string }[];
  delegations: Delegation[];
}

export interface OptionsUtilisateurs {
  unites: { uuid: string; libelle: string; profondeur: number }[];
  roles: { uuid: string; libelle: string; libelle_ar: string; mfa_requis: boolean }[];
  postes: { id: number; libelle: string; unite: string }[];
  niveaux: { valeur: number; libelle: string }[];
  langues: { valeur: string; libelle: string }[];
  mot_de_passe_suggere: string;
}

export interface Role {
  uuid: string;
  code: string;
  libelle_fr: string;
  libelle_ar: string;
  description: string;
  mfa_requis: boolean;
  actif: boolean;
  systeme: boolean;
  permissions: string[];
  titulaires: number | null;
}

export interface PermissionCatalogue {
  code: string;
  groupe: string;
  description: string;
}

export interface EvenementConnexion {
  horodatage: string;
  action: string;
  compte: string;
  adresse_ip: string;
  resultat: 'succes' | 'refus' | 'erreur';
}
