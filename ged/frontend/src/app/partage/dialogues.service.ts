import { ComponentType } from '@angular/cdk/portal';
import { Injectable, inject } from '@angular/core';
import { MatDialog, MatDialogConfig } from '@angular/material/dialog';
import { firstValueFrom } from 'rxjs';

import { TraductionService } from '../core/traduction.service';
import { DialogueConfirmation, DialogueSecret, DonneesConfirmation, DonneesSecret } from './dialogues';

/** Ouverture des dialogues dans le sens de lecture courant (les fenêtres sont hors de l'arbre de la page). */
@Injectable({ providedIn: 'root' })
export class DialoguesService {
  private readonly dialog = inject(MatDialog);
  private readonly traduction = inject(TraductionService);

  ouvrir<C, D, R>(composant: ComponentType<C>, donnees: D, config: MatDialogConfig = {}): Promise<R | undefined> {
    const reference = this.dialog.open<C, D, R>(composant, {
      data: donnees,
      direction: this.traduction.direction(),
      width: '560px',
      maxWidth: '94vw',
      autoFocus: 'first-tabbable',
      ...config,
    });
    return firstValueFrom(reference.afterClosed());
  }

  confirmer(donnees: DonneesConfirmation): Promise<string | true | undefined> {
    return this.ouvrir<DialogueConfirmation, DonneesConfirmation, string | true>(DialogueConfirmation, donnees);
  }

  secret(donnees: DonneesSecret): Promise<unknown> {
    return this.ouvrir(DialogueSecret, donnees, { disableClose: true });
  }
}
