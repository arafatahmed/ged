import { Injectable, inject } from '@angular/core';
import { MatSnackBar } from '@angular/material/snack-bar';

import { Cle } from '../i18n/fr';
import { ErreurApi } from './modeles';
import { TraductionService } from './traduction.service';

/** Messages éphémères (succès, erreurs), orientés selon la langue. */
@Injectable({ providedIn: 'root' })
export class NotificationService {
  private readonly snackBar = inject(MatSnackBar);
  private readonly traduction = inject(TraductionService);

  succes(cle: Cle, parametres?: Record<string, string | number>): void {
    this.afficher(this.traduction.t(cle, parametres), 'notification-succes');
  }

  erreur(erreur: unknown): void {
    this.afficher(messageErreur(erreur) || this.traduction.t('erreur.inattendue'), 'notification-erreur');
  }

  private afficher(message: string, classe: string): void {
    this.snackBar.open(message, this.traduction.t('action.fermer'), {
      duration: 4500,
      panelClass: classe,
      direction: this.traduction.direction(),
      horizontalPosition: 'center',
      verticalPosition: 'bottom',
    });
  }
}

/** Premier message lisible d'une erreur d'API. */
export function messageErreur(erreur: unknown): string {
  const corps = (erreur as { error?: ErreurApi })?.error;
  return corps?.detail ?? '';
}

/** Erreurs par champ d'une réponse 400 ({champ: [messages]}). */
export function erreursChamps(erreur: unknown): Record<string, string> {
  const erreurs = (erreur as { error?: ErreurApi })?.error?.erreurs ?? {};
  return Object.fromEntries(Object.entries(erreurs).map(([champ, messages]) => [champ, messages.join(' ')]));
}
