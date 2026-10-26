import { Injectable, computed, inject, signal } from '@angular/core';
import { firstValueFrom } from 'rxjs';

import { ApiService } from './api.service';
import { Droits, Session } from './modeles';
import { ThemeService } from './theme.service';
import { TraductionService } from './traduction.service';

const DROITS_VIDES: Droits = {
  organisation: false,
  types_unite: false,
  utilisateurs: false,
  roles: false,
  connexions: false,
  types_document: false,
};

/** État de la session côté frontend, source unique pour la coque, les gardes et les pages. */
@Injectable({ providedIn: 'root' })
export class SessionService {
  private readonly api = inject(ApiService);
  private readonly theme = inject(ThemeService);
  private readonly traduction = inject(TraductionService);
  private chargement: Promise<Session> | null = null;

  readonly etat = signal<Session | null>(null);
  readonly authentifie = computed(() => this.etat()?.authentifie ?? false);
  readonly utilisateur = computed(() => this.etat()?.utilisateur ?? null);
  readonly institution = computed(() => this.etat()?.institution ?? null);
  readonly droits = computed<Droits>(() => this.etat()?.droits ?? DROITS_VIDES);
  readonly administration = computed(() => Object.values(this.droits()).some(Boolean));
  readonly documents = computed(() => this.etat()?.documents ?? { consulter: false, creer: false });
  readonly exigences = computed(() => this.etat()?.exigences ?? { changer_mot_de_passe: false, activer_mfa: false });

  /** Charge la session une fois (au démarrage) ; les appels suivants réutilisent le résultat. */
  pret(): Promise<Session> {
    this.chargement ??= this.recharger();
    return this.chargement;
  }

  async recharger(): Promise<Session> {
    const session = await firstValueFrom(this.api.session());
    this.appliquer(session);
    return session;
  }

  appliquer(session: Session): void {
    this.etat.set(session);
    this.chargement = Promise.resolve(session);
    this.theme.appliquer(session.institution);
    const preferee = session.utilisateur?.langue || session.institution?.langue_defaut || 'fr';
    this.traduction.langueParDefaut.set(preferee);
  }

  /** Session perdue (expirée, révoquée) : l'état revient à « non connecté » sans appel réseau. */
  oublier(): void {
    const actuel = this.etat();
    this.appliquer({ authentifie: false, etape: null, utilisateur: null, institution: actuel?.institution ?? null });
  }

  async deconnecter(): Promise<void> {
    this.appliquer(await firstValueFrom(this.api.deconnexion()));
  }

  /** Page imposée par une exigence de sécurité en attente, ou null. */
  pageImposee(): string | null {
    const exigences = this.exigences();
    if (exigences.changer_mot_de_passe) return '/compte/mot-de-passe';
    if (exigences.activer_mfa) return '/compte/double-authentification';
    return null;
  }
}
