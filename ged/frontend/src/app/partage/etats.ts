import { ChangeDetectionStrategy, Component, input } from '@angular/core';
import { MatIconModule } from '@angular/material/icon';

/** Liste vide ou résultat absent. */
@Component({
  selector: 'ged-etat-vide',
  imports: [MatIconModule],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <div class="vide" animate.enter="entree-fondu">
      <span class="halo" aria-hidden="true"
        ><mat-icon>{{ icone() }}</mat-icon></span
      >
      <p>{{ message() }}</p>
      <ng-content />
    </div>
  `,
  styles: `
    .vide {
      display: grid;
      justify-items: center;
      gap: 8px;
      padding: 40px 16px;
      text-align: center;
      color: var(--ged-texte-attenue);
    }
    .halo {
      display: grid;
      place-items: center;
      width: 64px;
      height: 64px;
      border-radius: 50%;
      background: color-mix(in srgb, var(--ged-primaire) 8%, white);
      color: var(--ged-primaire);
    }
    .halo mat-icon {
      font-size: 32px;
      width: 32px;
      height: 32px;
    }
    p {
      margin: 0;
      max-width: 42ch;
    }
  `,
})
export class EtatVide {
  readonly message = input.required<string>();
  readonly icone = input<string>('inbox');
}

/** Lignes de chargement animées, à la place du contenu en attente. */
@Component({
  selector: 'ged-squelette',
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <div class="lignes" role="status" aria-live="polite">
      <span class="visuellement-cache">…</span>
      @for (ligne of lignesTableau(); track $index) {
        <div class="squelette ligne" [style.width.%]="ligne"></div>
      }
    </div>
  `,
  styles: `
    .lignes {
      display: grid;
      gap: 14px;
      padding: 8px 0;
    }
    .ligne {
      height: 18px;
    }
  `,
})
export class Squelette {
  readonly lignes = input<number>(4);
  protected lignesTableau() {
    return Array.from({ length: this.lignes() }, (_v, i) => 100 - ((i * 17) % 45));
  }
}
