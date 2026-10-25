import { ChangeDetectionStrategy, Component, OnInit, inject, signal } from '@angular/core';
import { MatButtonModule } from '@angular/material/button';
import { MatButtonToggleModule } from '@angular/material/button-toggle';
import { MatIconModule } from '@angular/material/icon';
import { MatTooltipModule } from '@angular/material/tooltip';
import { RouterLink } from '@angular/router';
import { firstValueFrom } from 'rxjs';

import { ApiService } from '../../core/api.service';
import { Compte as CompteModele, Langue } from '../../core/modeles';
import { NotificationService } from '../../core/notification.service';
import { BilinguePipe, DateLocalePipe, TraduirePipe } from '../../core/pipes';
import { SessionService } from '../../core/session.service';
import { TraductionService } from '../../core/traduction.service';
import { DialogueDelegation, DonneesDelegation } from '../../partage/dialogue-delegation';
import { DialoguesService } from '../../partage/dialogues.service';
import { EntetePage } from '../../partage/entete-page';
import { EtatVide, Squelette } from '../../partage/etats';

/** « Mon compte » : préférences, sécurité, affectations, délégations et sessions ouvertes. */
@Component({
  selector: 'ged-compte',
  imports: [
    RouterLink,
    MatButtonModule,
    MatIconModule,
    MatButtonToggleModule,
    MatTooltipModule,
    TraduirePipe,
    BilinguePipe,
    DateLocalePipe,
    EntetePage,
    EtatVide,
    Squelette,
  ],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './compte.html',
  styleUrl: './compte.scss',
})
export class Compte implements OnInit {
  private readonly api = inject(ApiService);
  private readonly session = inject(SessionService);
  private readonly dialogues = inject(DialoguesService);
  private readonly notifications = inject(NotificationService);
  protected readonly traduction = inject(TraductionService);
  protected readonly compte = signal<CompteModele | null>(null);

  async ngOnInit(): Promise<void> {
    await this.charger();
  }

  private async charger(): Promise<void> {
    try {
      this.compte.set(await firstValueFrom(this.api.compte()));
    } catch (erreur) {
      this.notifications.erreur(erreur);
    }
  }

  protected async changerLangue(langue: Langue | ''): Promise<void> {
    this.compte.set(await firstValueFrom(this.api.changerLangue(langue)));
    if (langue) this.traduction.choisir(langue);
    await this.session.recharger();
    this.notifications.succes('compte.preferences_enregistrees');
  }

  protected async regenererCodes(): Promise<void> {
    const confirme = await this.dialogues.confirmer({
      titre: this.traduction.t('compte.codes_regenerer'),
      message: this.traduction.t('compte.codes_regenerer_confirmation'),
      confirmer: this.traduction.t('action.continuer'),
    });
    if (!confirme) return;
    const { codes_secours } = await firstValueFrom(this.api.regenererCodes());
    await this.dialogues.secret({
      titre: this.traduction.t('mfa.codes_titre'),
      message: this.traduction.t('mfa.codes_aide'),
      valeurs: codes_secours,
    });
    await this.charger();
  }

  protected async desactiverMfa(): Promise<void> {
    const confirme = await this.dialogues.confirmer({
      titre: this.traduction.t('compte.mfa_desactiver'),
      message: this.traduction.t('compte.mfa_desactiver_confirmation'),
      confirmer: this.traduction.t('action.desactiver'),
      danger: true,
    });
    if (!confirme) return;
    try {
      await firstValueFrom(this.api.desactiverMfa());
      await this.session.recharger();
      this.notifications.succes('compte.mfa_desactivee');
      await this.charger();
    } catch (erreur) {
      this.notifications.erreur(erreur);
    }
  }

  protected async fermerSessions(): Promise<void> {
    const { sessions_fermees } = await firstValueFrom(this.api.fermerAutresSessions());
    this.notifications.succes('compte.sessions_fermees', { nombre: sessions_fermees });
    await this.charger();
  }

  protected async deleguer(): Promise<void> {
    const donnees: DonneesDelegation = {
      titre: this.traduction.t('delegation.titre_moi'),
      options: () => this.api.optionsMaDelegation(),
      enregistrer: (corps) => this.api.creerMaDelegation(corps),
    };
    if (await this.dialogues.ouvrir(DialogueDelegation, donnees)) {
      this.notifications.succes('delegation.enregistree');
      await this.charger();
    }
  }

  protected async revoquer(uuid: string): Promise<void> {
    await firstValueFrom(this.api.revoquerDelegation(uuid));
    this.notifications.succes('delegation.revoquee');
    await this.charger();
  }
}
