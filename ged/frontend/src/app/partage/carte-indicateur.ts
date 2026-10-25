import { ChangeDetectionStrategy, Component, DestroyRef, effect, inject, input, signal } from '@angular/core';
import { MatIconModule } from '@angular/material/icon';

/** Indicateur chiffré dont la valeur défile de 0 à sa valeur (désactivé si mouvements réduits). */
@Component({
  selector: 'ged-carte-indicateur',
  imports: [MatIconModule],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <article class="carte carte-interactive indicateur" [class]="'teinte-' + teinte()">
      <span class="icone" aria-hidden="true"
        ><mat-icon>{{ icone() }}</mat-icon></span
      >
      <div>
        <p class="valeur">{{ affichee() }}</p>
        <p class="libelle">{{ libelle() }}</p>
      </div>
    </article>
  `,
  styles: `
    .indicateur {
      display: flex;
      align-items: center;
      gap: 16px;
      padding: 20px;
      overflow: hidden;
      position: relative;
    }
    .indicateur::after {
      content: '';
      position: absolute;
      inset-inline-end: -30px;
      inset-block-start: -30px;
      width: 110px;
      height: 110px;
      border-radius: 50%;
      background: var(--teinte);
      opacity: 0.08;
    }
    .icone {
      display: grid;
      place-items: center;
      width: 48px;
      height: 48px;
      border-radius: 14px;
      color: var(--teinte);
      background: color-mix(in srgb, var(--teinte) 12%, white);
    }
    .valeur {
      margin: 0;
      font-size: 30px;
      font-weight: 600;
      line-height: 1.1;
      font-variant-numeric: tabular-nums;
    }
    .libelle {
      margin: 2px 0 0;
      color: var(--ged-texte-attenue);
      font-size: 14px;
    }
    .teinte-primaire {
      --teinte: var(--ged-primaire);
    }
    .teinte-succes {
      --teinte: var(--ged-succes);
    }
    .teinte-alerte {
      --teinte: var(--ged-alerte);
    }
    .teinte-avertissement {
      --teinte: var(--ged-avertissement);
    }
  `,
})
export class CarteIndicateur {
  readonly valeur = input.required<number>();
  readonly libelle = input.required<string>();
  readonly icone = input<string>('insights');
  readonly teinte = input<'primaire' | 'succes' | 'alerte' | 'avertissement'>('primaire');
  protected readonly affichee = signal(0);

  constructor() {
    let image = 0;
    inject(DestroyRef).onDestroy(() => cancelAnimationFrame(image));
    effect(() => {
      const cible = this.valeur();
      const reduit = window.matchMedia?.('(prefers-reduced-motion: reduce)').matches;
      if (reduit || cible === 0) {
        this.affichee.set(cible);
        return;
      }
      const debut = performance.now();
      const duree = 900;
      const etape = (instant: number) => {
        const progression = Math.min(1, (instant - debut) / duree);
        const adoucie = 1 - Math.pow(1 - progression, 3);
        this.affichee.set(Math.round(cible * adoucie));
        if (progression < 1) image = requestAnimationFrame(etape);
      };
      cancelAnimationFrame(image);
      image = requestAnimationFrame(etape);
    });
  }
}
