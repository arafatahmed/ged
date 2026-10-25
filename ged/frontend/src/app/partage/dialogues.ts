import { Clipboard } from '@angular/cdk/clipboard';
import { ChangeDetectionStrategy, Component, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { MatButtonModule } from '@angular/material/button';
import { MAT_DIALOG_DATA, MatDialogModule, MatDialogRef } from '@angular/material/dialog';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatIconModule } from '@angular/material/icon';
import { MatInputModule } from '@angular/material/input';

import { TraduirePipe } from '../core/pipes';

export interface DonneesConfirmation {
  titre: string;
  message: string;
  confirmer: string;
  danger?: boolean;
  /** Si renseigné, demande une saisie obligatoire (par exemple un motif). */
  champ?: string;
}

/** Confirmation d'une action sensible, avec saisie facultative d'un motif. Renvoie le texte saisi ou true. */
@Component({
  selector: 'ged-dialogue-confirmation',
  imports: [MatDialogModule, MatButtonModule, MatFormFieldModule, MatInputModule, FormsModule, TraduirePipe],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <h2 mat-dialog-title>{{ donnees.titre }}</h2>
    <mat-dialog-content>
      <p>{{ donnees.message }}</p>
      @if (donnees.champ) {
        <mat-form-field appearance="outline">
          <mat-label>{{ donnees.champ }}</mat-label>
          <input matInput [(ngModel)]="saisie" cdkFocusInitial required />
        </mat-form-field>
      }
    </mat-dialog-content>
    <mat-dialog-actions align="end">
      <button mat-button mat-dialog-close>{{ 'action.annuler' | t }}</button>
      <button
        mat-flat-button
        [class.bouton-danger]="donnees.danger"
        [disabled]="!!donnees.champ && !saisie().trim()"
        (click)="valider()"
      >
        {{ donnees.confirmer }}
      </button>
    </mat-dialog-actions>
  `,
  styles: `
    .bouton-danger {
      --mat-button-filled-container-color: var(--ged-alerte);
    }
    p {
      margin-top: 0;
    }
  `,
})
export class DialogueConfirmation {
  protected readonly donnees = inject<DonneesConfirmation>(MAT_DIALOG_DATA);
  private readonly reference = inject(MatDialogRef<DialogueConfirmation, string | true>);
  protected readonly saisie = signal('');

  protected valider(): void {
    this.reference.close(this.donnees.champ ? this.saisie().trim() : true);
  }
}

export interface DonneesSecret {
  titre: string;
  message: string;
  valeurs: string[];
}

/** Affiche une information à ne montrer qu'une fois (mot de passe temporaire, codes de secours), avec copie. */
@Component({
  selector: 'ged-dialogue-secret',
  imports: [MatDialogModule, MatButtonModule, MatIconModule, TraduirePipe],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <h2 mat-dialog-title>{{ donnees.titre }}</h2>
    <mat-dialog-content>
      <p class="avertissement"><mat-icon>info</mat-icon> {{ donnees.message }}</p>
      <ul class="valeurs ltr" [class.grille-codes]="donnees.valeurs.length > 1">
        @for (valeur of donnees.valeurs; track valeur) {
          <li animate.enter="entree-zoom" [style.--rang]="$index">
            <code>{{ valeur }}</code>
          </li>
        }
      </ul>
    </mat-dialog-content>
    <mat-dialog-actions align="end">
      <button mat-stroked-button (click)="copier()">
        <mat-icon>{{ copie() ? 'check' : 'content_copy' }}</mat-icon>
        {{ (copie() ? 'action.copie' : 'action.copier') | t }}
      </button>
      <button mat-flat-button mat-dialog-close cdkFocusInitial>{{ 'action.jai_note' | t }}</button>
    </mat-dialog-actions>
  `,
  styles: `
    .avertissement {
      display: flex;
      gap: 8px;
      align-items: flex-start;
      padding: 12px;
      border-radius: 12px;
      background: var(--mat-sys-primary-container);
      color: var(--mat-sys-on-primary-container);
      margin-top: 0;
    }
    .valeurs {
      list-style: none;
      padding: 0;
      margin: 16px 0 0;
      display: grid;
      gap: 8px;
    }
    .grille-codes {
      grid-template-columns: repeat(2, minmax(0, 1fr));
    }
    li {
      padding: 10px 14px;
      border-radius: 10px;
      background: #f3f5f9;
      border: 1px dashed var(--ged-bordure);
      text-align: center;
    }
    code {
      font-size: 17px;
      letter-spacing: 0.06em;
      font-weight: 600;
    }
  `,
})
export class DialogueSecret {
  protected readonly donnees = inject<DonneesSecret>(MAT_DIALOG_DATA);
  private readonly pressePapiers = inject(Clipboard);
  protected readonly copie = signal(false);

  protected copier(): void {
    this.copie.set(this.pressePapiers.copy(this.donnees.valeurs.join('\n')));
  }
}
