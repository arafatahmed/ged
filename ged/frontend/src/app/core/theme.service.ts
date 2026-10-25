import { DOCUMENT } from '@angular/common';
import { Injectable, inject } from '@angular/core';

import { Institution } from './modeles';

const COULEUR = /^#[0-9a-fA-F]{6}$/;

/** Applique l'identité visuelle de l'institution (couleurs) aux variables CSS du thème. */
@Injectable({ providedIn: 'root' })
export class ThemeService {
  private readonly document = inject(DOCUMENT);

  appliquer(institution: Institution | null): void {
    const style = this.document.documentElement.style;
    if (institution && COULEUR.test(institution.couleur_primaire)) {
      style.setProperty('--ged-primaire', institution.couleur_primaire);
    }
    if (institution && COULEUR.test(institution.couleur_secondaire)) {
      style.setProperty('--ged-secondaire', institution.couleur_secondaire);
    }
    if (institution) {
      this.document.title = institution.sigle ? `GED · ${institution.sigle}` : 'GED';
    }
  }
}
