import { ChangeDetectionStrategy, Component, input } from '@angular/core';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';
import { RouterLink } from '@angular/router';

import { TraduirePipe } from '../core/pipes';
import { Cle } from '../i18n/fr';

/** Page d'erreur (accès refusé, page introuvable), paramétrée par la route. */
@Component({
  selector: 'ged-page-erreur',
  imports: [RouterLink, MatButtonModule, MatIconModule, TraduirePipe],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <section class="erreur" animate.enter="entree-zoom">
      <span class="code">{{ code() }}</span>
      <mat-icon>{{ icone() }}</mat-icon>
      <h1>{{ titre() | t }}</h1>
      <p class="texte-attenue">{{ message() | t }}</p>
      <a mat-flat-button routerLink="/"><mat-icon>home</mat-icon>{{ 'erreur.retour_accueil' | t }}</a>
    </section>
  `,
  styles: `
    .erreur {
      display: grid;
      justify-items: center;
      text-align: center;
      gap: 8px;
      padding: 64px 16px;
    }
    .code {
      font-size: 96px;
      font-weight: 700;
      line-height: 1;
      color: color-mix(in srgb, var(--ged-primaire) 18%, white);
    }
    mat-icon {
      color: var(--ged-primaire);
      font-size: 40px;
      width: 40px;
      height: 40px;
      margin-top: -40px;
    }
    h1 {
      margin: 8px 0 0;
    }
    p {
      max-width: 50ch;
    }
  `,
})
export class PageErreur {
  readonly code = input('404');
  readonly icone = input('travel_explore');
  readonly titre = input<Cle>('erreur.introuvable_titre');
  readonly message = input<Cle>('erreur.introuvable_message');
}
