import { DOCUMENT } from '@angular/common';
import { Injectable, computed, effect, inject, signal } from '@angular/core';

import { AR } from '../i18n/ar';
import { Cle, FR } from '../i18n/fr';
import { Langue } from './modeles';

const CLE_STOCKAGE = 'ged.langue';

function langueEnregistree(): Langue | null {
  try {
    const valeur = localStorage.getItem(CLE_STOCKAGE);
    return valeur === 'fr' || valeur === 'ar' ? valeur : null;
  } catch {
    return null;
  }
}

/** Langue de l'interface, changeable à chaud ; applique lang et dir au document. */
@Injectable({ providedIn: 'root' })
export class TraductionService {
  private readonly document = inject(DOCUMENT);
  private readonly dictionnaires: Record<Langue, Record<Cle, string>> = { fr: FR, ar: AR };

  /** Choix explicite de l'utilisateur sur ce poste (prioritaire), sinon langue du compte ou de l'institution. */
  readonly choixLocal = signal<Langue | null>(langueEnregistree());
  readonly langueParDefaut = signal<Langue>('fr');
  readonly langue = computed<Langue>(() => this.choixLocal() ?? this.langueParDefaut());
  readonly rtl = computed(() => this.langue() === 'ar');
  readonly direction = computed<'rtl' | 'ltr'>(() => (this.rtl() ? 'rtl' : 'ltr'));

  constructor() {
    effect(() => {
      const racine = this.document.documentElement;
      racine.lang = this.langue();
      racine.dir = this.direction();
    });
  }

  choisir(langue: Langue): void {
    this.choixLocal.set(langue);
    try {
      localStorage.setItem(CLE_STOCKAGE, langue);
    } catch {
      // Stockage indisponible (navigation privée) : le choix vaut pour la session de la page.
    }
  }

  t(cle: Cle, parametres?: Record<string, string | number>): string {
    let texte = this.dictionnaires[this.langue()][cle] ?? FR[cle] ?? cle;
    if (parametres) {
      for (const [nom, valeur] of Object.entries(parametres)) {
        texte = texte.replaceAll(`{${nom}}`, String(valeur));
      }
    }
    return texte;
  }

  /** Libellé bilingue d'un objet métier : l'arabe s'il est renseigné et actif. */
  libelle(francais: string | null | undefined, arabe: string | null | undefined): string {
    return this.rtl() && arabe ? arabe : (francais ?? '');
  }

  /** Locale Intl : chiffres occidentaux (0-9) aussi en arabe. */
  locale(): string {
    return this.rtl() ? 'ar-u-nu-latn' : 'fr-FR';
  }
}
