import { ChangeDetectionStrategy, Component, computed, input } from '@angular/core';
import { MatIconModule } from '@angular/material/icon';

import { EtatAnalyse } from '../../core/modeles';
import { TraduirePipe } from '../../core/pipes';
import { Cle } from '../../i18n/fr';

const NIVEAUX: Record<number, { cle: Cle; classe: string; icone: string }> = {
  0: { cle: 'niveau.0', classe: '', icone: 'public' },
  1: { cle: 'niveau.1', classe: 'info', icone: 'lock_open' },
  2: { cle: 'niveau.2', classe: 'avertissement', icone: 'lock' },
  3: { cle: 'niveau.3', classe: 'alerte', icone: 'gpp_maybe' },
};

/** Niveau de confidentialité d'un document. */
@Component({
  selector: 'ged-pastille-confidentialite',
  imports: [MatIconModule, TraduirePipe],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `<span class="pastille {{ niveau().classe }}"
    ><mat-icon inline>{{ niveau().icone }}</mat-icon
    >{{ niveau().cle | t }}</span
  >`,
})
export class PastilleConfidentialite {
  readonly valeur = input.required<number>();
  protected readonly niveau = computed(() => NIVEAUX[this.valeur()] ?? NIVEAUX[0]);
}

const ETATS: Record<EtatAnalyse, { cle: Cle; classe: string; icone: string }> = {
  en_attente: { cle: 'fichier.en_attente', classe: 'info', icone: 'hourglass_top' },
  sain: { cle: 'fichier.sain', classe: 'succes', icone: 'verified' },
  infecte: { cle: 'fichier.infecte', classe: 'alerte', icone: 'coronavirus' },
  refuse: { cle: 'fichier.refuse', classe: 'alerte', icone: 'block' },
};

/** État de l'analyse d'un fichier (antivirus, empreinte, type réel). */
@Component({
  selector: 'ged-etat-fichier',
  imports: [MatIconModule, TraduirePipe],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `<span class="pastille {{ etat().classe }}" [class.anime]="valeur() === 'en_attente'"
    ><mat-icon inline>{{ etat().icone }}</mat-icon
    >{{ etat().cle | t }}</span
  >`,
  styles: `
    .anime mat-icon {
      animation: ged-rotation 1.6s linear infinite;
    }
    @media (prefers-reduced-motion: reduce) {
      .anime mat-icon {
        animation: none;
      }
    }
  `,
})
export class EtatFichier {
  readonly valeur = input.required<EtatAnalyse>();
  protected readonly etat = computed(() => ETATS[this.valeur()]);
}
