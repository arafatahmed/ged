import { ChangeDetectionStrategy, Component, input } from '@angular/core';
import { MatIconModule } from '@angular/material/icon';

/** En-tête de page : icône, titre, sous-titre et actions (contenu projeté). */
@Component({
  selector: 'ged-entete-page',
  imports: [MatIconModule],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <header class="entete" animate.enter="entree-montee">
      @if (icone()) {
        <span class="pictogramme" aria-hidden="true"
          ><mat-icon>{{ icone() }}</mat-icon></span
        >
      }
      <div class="textes">
        <h1>{{ titre() }}</h1>
        @if (sousTitre()) {
          <p>{{ sousTitre() }}</p>
        }
      </div>
      <div class="actions"><ng-content /></div>
    </header>
  `,
  styles: `
    .entete {
      display: flex;
      flex-wrap: wrap;
      align-items: center;
      gap: 16px;
      margin-block-end: 24px;
    }
    .pictogramme {
      display: grid;
      place-items: center;
      width: 52px;
      height: 52px;
      border-radius: 16px;
      flex: none;
      color: var(--ged-primaire);
      background: linear-gradient(
        135deg,
        color-mix(in srgb, var(--ged-primaire) 16%, white),
        color-mix(in srgb, var(--ged-secondaire) 14%, white)
      );
    }
    .textes {
      flex: 1 1 240px;
      min-width: 0;
    }
    h1 {
      margin: 0;
      font-size: clamp(22px, 2.6vw, 28px);
      font-weight: 600;
      letter-spacing: -0.01em;
    }
    p {
      margin: 4px 0 0;
      color: var(--ged-texte-attenue);
    }
    .actions {
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
    }
  `,
})
export class EntetePage {
  readonly titre = input.required<string>();
  readonly sousTitre = input<string>('');
  readonly icone = input<string>('');
}
