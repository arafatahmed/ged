import { ChangeDetectionStrategy, Component, OnInit, inject, signal } from '@angular/core';
import { FormControl, ReactiveFormsModule, Validators } from '@angular/forms';
import { MatButtonModule } from '@angular/material/button';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatIconModule } from '@angular/material/icon';
import { MatInputModule } from '@angular/material/input';
import { Router } from '@angular/router';
import { firstValueFrom } from 'rxjs';

import { ApiService } from '../../core/api.service';
import { Enrolement } from '../../core/modeles';
import { NotificationService, erreursChamps, messageErreur } from '../../core/notification.service';
import { TraduirePipe } from '../../core/pipes';
import { SessionService } from '../../core/session.service';
import { TraductionService } from '../../core/traduction.service';
import { DialoguesService } from '../../partage/dialogues.service';
import { EntetePage } from '../../partage/entete-page';
import { Squelette } from '../../partage/etats';

/** Activation de la double authentification depuis une session ouverte (volontaire ou imposée par un rôle). */
@Component({
  selector: 'ged-double-authentification',
  imports: [
    ReactiveFormsModule,
    MatFormFieldModule,
    MatInputModule,
    MatButtonModule,
    MatIconModule,
    TraduirePipe,
    EntetePage,
    Squelette,
  ],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <ged-entete-page [titre]="'mfa.activer_titre' | t" icone="phonelink_lock" />
    <div class="carte panneau" animate.enter="entree-montee">
      @if (enrolement(); as e) {
        @if (e.obligatoire) {
          <p class="bandeau"><mat-icon>verified_user</mat-icon>{{ 'mfa.obligatoire' | t }}</p>
        }
        <div class="disposition">
          <div class="qr" animate.enter="entree-zoom">
            <img [src]="e.qr_code" [alt]="'mfa.qr_alt' | t" width="200" height="200" />
          </div>
          <div>
            <ol class="etapes">
              <li>{{ 'mfa.etape_installer' | t }}</li>
              <li>{{ 'mfa.etape_scanner' | t }}</li>
              <li>{{ 'mfa.etape_code' | t }}</li>
            </ol>
            <p class="texte-attenue">
              {{ 'mfa.cle' | t }} <code class="ltr">{{ e.secret }}</code>
            </p>
            <form (ngSubmit)="activer()" novalidate>
              <mat-form-field appearance="outline">
                <mat-label>{{ 'connexion.code' | t }}</mat-label>
                <input
                  matInput
                  class="champ-code"
                  [formControl]="code"
                  inputmode="numeric"
                  maxlength="6"
                  dir="ltr"
                  autocomplete="one-time-code"
                />
                @if (erreur()) {
                  <mat-error>{{ erreur() }}</mat-error>
                }
              </mat-form-field>
              <button mat-flat-button type="submit" [disabled]="envoi() || code.invalid">
                {{ 'mfa.activer' | t }}
              </button>
            </form>
          </div>
        </div>
      } @else {
        <ged-squelette [lignes]="5" />
      }
    </div>
  `,
  styles: `
    .panneau {
      max-width: 760px;
    }
    .bandeau {
      display: flex;
      gap: 10px;
      align-items: center;
      padding: 12px;
      border-radius: 12px;
      margin-top: 0;
      background: var(--mat-sys-primary-container);
      color: var(--mat-sys-on-primary-container);
    }
    .disposition {
      display: grid;
      grid-template-columns: auto 1fr;
      gap: 28px;
      align-items: start;
    }
    .qr {
      padding: 12px;
      border-radius: 16px;
      background: white;
      border: 1px solid var(--ged-bordure);
      box-shadow: var(--ged-ombre);
    }
    .etapes {
      padding-inline-start: 20px;
      line-height: 1.7;
      margin-top: 0;
    }
    .champ-code {
      font-size: 22px;
      letter-spacing: 0.35em;
      text-align: center;
    }
    @media (max-width: 640px) {
      .disposition {
        grid-template-columns: 1fr;
        justify-items: center;
      }
    }
  `,
})
export class DoubleAuthentification implements OnInit {
  private readonly api = inject(ApiService);
  private readonly session = inject(SessionService);
  private readonly dialogues = inject(DialoguesService);
  private readonly notifications = inject(NotificationService);
  private readonly traduction = inject(TraductionService);
  private readonly router = inject(Router);
  protected readonly enrolement = signal<Enrolement | null>(null);
  protected readonly envoi = signal(false);
  protected readonly erreur = signal('');
  protected readonly code = new FormControl('', {
    nonNullable: true,
    validators: [Validators.required, Validators.pattern(/^\d{6}$/)],
  });

  async ngOnInit(): Promise<void> {
    if (this.session.utilisateur()?.mfa_active) {
      await this.router.navigateByUrl('/compte');
      return;
    }
    try {
      this.enrolement.set(await firstValueFrom(this.api.enrolement()));
    } catch (erreur) {
      this.notifications.erreur(erreur);
    }
  }

  protected async activer(): Promise<void> {
    this.envoi.set(true);
    this.erreur.set('');
    try {
      const resultat = await firstValueFrom(this.api.confirmerEnrolement(this.code.value));
      this.session.appliquer(resultat.session);
      await this.dialogues.secret({
        titre: this.traduction.t('mfa.active'),
        message: this.traduction.t('mfa.codes_aide'),
        valeurs: resultat.codes_secours,
      });
      await this.router.navigateByUrl(this.session.pageImposee() ?? '/compte');
    } catch (erreur) {
      this.erreur.set(erreursChamps(erreur)['code'] ?? messageErreur(erreur));
      this.code.setErrors({ serveur: true });
    } finally {
      this.envoi.set(false);
    }
  }
}
