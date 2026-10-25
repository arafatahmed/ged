import { ChangeDetectionStrategy, Component, computed, inject, signal } from '@angular/core';
import { NonNullableFormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { MatButtonModule } from '@angular/material/button';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatIconModule } from '@angular/material/icon';
import { MatInputModule } from '@angular/material/input';
import { MatProgressBarModule } from '@angular/material/progress-bar';
import { Router } from '@angular/router';
import { firstValueFrom } from 'rxjs';

import { ApiService } from '../../core/api.service';
import { NotificationService, erreursChamps } from '../../core/notification.service';
import { TraduirePipe } from '../../core/pipes';
import { SessionService } from '../../core/session.service';
import { EntetePage } from '../../partage/entete-page';

/** Changement de mot de passe (obligatoire après un mot de passe temporaire). */
@Component({
  selector: 'ged-mot-de-passe',
  imports: [
    ReactiveFormsModule,
    MatFormFieldModule,
    MatInputModule,
    MatButtonModule,
    MatIconModule,
    MatProgressBarModule,
    TraduirePipe,
    EntetePage,
  ],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <ged-entete-page [titre]="'mdp.titre' | t" icone="password" />
    <div class="carte panneau" animate.enter="entree-montee">
      @if (session.exigences().changer_mot_de_passe) {
        <p class="bandeau"><mat-icon>info</mat-icon>{{ 'mdp.temporaire' | t }}</p>
      }
      <form [formGroup]="formulaire" (ngSubmit)="enregistrer()" novalidate>
        <mat-form-field appearance="outline">
          <mat-label>{{ 'mdp.actuel' | t }}</mat-label>
          <input matInput type="password" formControlName="ancien" autocomplete="current-password" dir="ltr" />
          @if (erreurs()['ancien']) {
            <mat-error>{{ erreurs()['ancien'] }}</mat-error>
          }
        </mat-form-field>
        <mat-form-field appearance="outline">
          <mat-label>{{ 'mdp.nouveau' | t }}</mat-label>
          <input
            matInput
            type="password"
            formControlName="nouveau"
            autocomplete="new-password"
            dir="ltr"
            (input)="saisie.set(formulaire.controls.nouveau.value)"
          />
          <mat-hint>{{ 'mdp.regles' | t }}</mat-hint>
          @if (erreurs()['nouveau']) {
            <mat-error>{{ erreurs()['nouveau'] }}</mat-error>
          }
        </mat-form-field>
        <div class="force" [attr.aria-label]="'mdp.force' | t">
          <mat-progress-bar mode="determinate" [value]="force().valeur" [class]="force().classe" />
          <span class="texte-attenue">{{ force().libelle | t }}</span>
        </div>
        <mat-form-field appearance="outline">
          <mat-label>{{ 'mdp.confirmation' | t }}</mat-label>
          <input matInput type="password" formControlName="confirmation" autocomplete="new-password" dir="ltr" />
          @if (erreurs()['confirmation']) {
            <mat-error>{{ erreurs()['confirmation'] }}</mat-error>
          }
        </mat-form-field>
        <button mat-flat-button type="submit" [disabled]="envoi() || formulaire.invalid">
          {{ 'action.enregistrer' | t }}
        </button>
      </form>
    </div>
  `,
  styles: `
    .panneau {
      max-width: 520px;
    }
    form {
      display: grid;
      gap: 6px;
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
    .force {
      display: grid;
      gap: 4px;
      margin: 4px 0 12px;
      font-size: 13px;
    }
    .faible {
      --mdc-linear-progress-active-indicator-color: var(--ged-alerte);
    }
    .moyenne {
      --mdc-linear-progress-active-indicator-color: var(--ged-avertissement);
    }
    .forte {
      --mdc-linear-progress-active-indicator-color: var(--ged-succes);
    }
  `,
})
export class MotDePasse {
  private readonly api = inject(ApiService);
  protected readonly session = inject(SessionService);
  private readonly notifications = inject(NotificationService);
  private readonly router = inject(Router);
  protected readonly envoi = signal(false);
  protected readonly erreurs = signal<Record<string, string>>({});
  protected readonly saisie = signal('');

  protected readonly formulaire = inject(NonNullableFormBuilder).group({
    ancien: ['', Validators.required],
    nouveau: ['', [Validators.required, Validators.minLength(12)]],
    confirmation: ['', Validators.required],
  });

  /** Indication de robustesse (le contrôle qui fait foi est celui du serveur). */
  protected readonly force = computed(() => {
    const valeur = this.saisie();
    let points = Math.min(valeur.length, 20) * 3;
    for (const motif of [/[a-z]/, /[A-Z]/, /\d/, /[^A-Za-z0-9]/]) if (motif.test(valeur)) points += 10;
    const total = Math.min(100, points);
    if (total < 45) return { valeur: total, classe: 'faible', libelle: 'mdp.force_faible' as const };
    if (total < 75) return { valeur: total, classe: 'moyenne', libelle: 'mdp.force_moyenne' as const };
    return { valeur: total, classe: 'forte', libelle: 'mdp.force_forte' as const };
  });

  protected async enregistrer(): Promise<void> {
    const { ancien, nouveau, confirmation } = this.formulaire.getRawValue();
    this.envoi.set(true);
    this.erreurs.set({});
    try {
      this.session.appliquer(await firstValueFrom(this.api.changerMotDePasse(ancien, nouveau, confirmation)));
      this.notifications.succes('mdp.modifie');
      this.formulaire.reset();
      await this.router.navigateByUrl(this.session.pageImposee() ?? '/compte');
    } catch (erreur) {
      this.erreurs.set(erreursChamps(erreur));
      for (const champ of Object.keys(this.erreurs())) {
        this.formulaire.get(champ)?.setErrors({ serveur: true });
      }
      if (!Object.keys(this.erreurs()).length) this.notifications.erreur(erreur);
    } finally {
      this.envoi.set(false);
    }
  }
}
