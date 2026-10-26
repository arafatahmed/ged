import { ChangeDetectionStrategy, Component, computed, input, output, signal } from '@angular/core';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';

import { TailleFichierPipe, TraduirePipe } from '../core/pipes';

/**
 * Zone de dépôt d'un fichier (glisser-déposer ou parcourir).
 * Les contrôles faits ici (extension, taille) n'aident que l'utilisateur : le serveur
 * vérifie le type réel du contenu et refuse ce qui ne convient pas.
 */
@Component({
  selector: 'ged-depot-fichier',
  imports: [MatButtonModule, MatIconModule, TraduirePipe, TailleFichierPipe],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    @if (fichier(); as f) {
      <div class="choisi" animate.enter="entree-zoom">
        <mat-icon class="icone">description</mat-icon>
        <span class="nom">
          <strong class="ltr">{{ f.name }}</strong>
          <span class="texte-attenue">{{ f.size | tailleFichier }}</span>
        </span>
        <button mat-icon-button type="button" (click)="choisir(null)" [attr.aria-label]="'depot.retirer' | t">
          <mat-icon>close</mat-icon>
        </button>
      </div>
    } @else {
      <label
        class="zone"
        [class.survol]="survol()"
        (dragover)="survoler($event, true)"
        (dragleave)="survoler($event, false)"
        (drop)="deposer($event)"
      >
        <input type="file" class="visuellement-cache" [accept]="accept()" (change)="parcourir($event)" />
        <mat-icon class="icone">upload_file</mat-icon>
        <strong>{{ 'depot.deposer' | t }}</strong>
        <span class="texte-attenue">{{ 'depot.aide' | t: { taille: tailleMaxMo() } }}</span>
        @if (extensions().length) {
          <span class="texte-attenue formats ltr">{{ extensions().join(', ') }}</span>
        }
      </label>
    }
    @if (erreur()) {
      <p class="erreur" role="alert">{{ erreur() }}</p>
    }
  `,
  styles: `
    .zone {
      display: grid;
      justify-items: center;
      gap: 6px;
      padding: 28px 16px;
      text-align: center;
      border: 2px dashed var(--ged-bordure);
      border-radius: var(--ged-rayon);
      cursor: pointer;
      transition:
        border-color 160ms,
        background-color 160ms;
      &:hover,
      &:focus-within,
      &.survol {
        border-color: var(--ged-primaire);
        background: color-mix(in srgb, var(--ged-primaire) 5%, transparent);
      }
    }
    .icone {
      font-size: 36px;
      width: 36px;
      height: 36px;
      color: var(--ged-primaire);
    }
    .formats {
      font-size: 12px;
    }
    .choisi {
      display: flex;
      align-items: center;
      gap: 12px;
      padding: 12px 16px;
      border: 1px solid var(--ged-bordure);
      border-radius: var(--ged-rayon);
      background: color-mix(in srgb, var(--ged-primaire) 4%, transparent);
    }
    .nom {
      display: grid;
      flex: 1;
      min-width: 0;
      strong {
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
      }
    }
    .erreur {
      color: var(--ged-alerte);
      margin: 8px 0 0;
    }
  `,
})
export class DepotFichier {
  /** Extensions admises (sans point) ; vide : aucune restriction côté interface. */
  readonly extensions = input<string[]>([]);
  readonly tailleMaxMo = input<number>(100);
  readonly messageTropGros = input<string>('');
  readonly messageFormat = input<string>('');
  readonly fichierChange = output<File | null>();

  protected readonly fichier = signal<File | null>(null);
  protected readonly survol = signal(false);
  protected readonly erreur = signal('');
  protected readonly accept = computed(() =>
    this.extensions()
      .map((e) => `.${e}`)
      .join(','),
  );

  protected survoler(evenement: DragEvent, actif: boolean): void {
    evenement.preventDefault();
    this.survol.set(actif);
  }

  protected deposer(evenement: DragEvent): void {
    evenement.preventDefault();
    this.survol.set(false);
    this.choisir(evenement.dataTransfer?.files.item(0) ?? null);
  }

  protected parcourir(evenement: Event): void {
    const champ = evenement.target as HTMLInputElement;
    this.choisir(champ.files?.item(0) ?? null);
    champ.value = '';
  }

  /** Remet la zone à vide (après un envoi réussi par exemple). */
  vider(): void {
    this.choisir(null);
  }

  protected choisir(fichier: File | null): void {
    this.erreur.set('');
    if (fichier) {
      const extension = fichier.name.includes('.') ? fichier.name.split('.').pop()!.toLowerCase() : '';
      if (this.extensions().length && !this.extensions().includes(extension)) {
        this.erreur.set(this.messageFormat());
        fichier = null;
      } else if (fichier.size > this.tailleMaxMo() * 1024 * 1024) {
        this.erreur.set(this.messageTropGros());
        fichier = null;
      }
    }
    this.fichier.set(fichier);
    this.fichierChange.emit(fichier);
  }
}
