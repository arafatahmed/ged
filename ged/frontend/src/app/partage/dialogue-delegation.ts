import { ChangeDetectionStrategy, Component, OnInit, inject, signal } from '@angular/core';
import { NonNullableFormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { MatButtonModule } from '@angular/material/button';
import { MatCheckboxModule } from '@angular/material/checkbox';
import { MAT_DIALOG_DATA, MatDialogModule, MatDialogRef } from '@angular/material/dialog';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { MatSelectModule } from '@angular/material/select';
import { Observable, firstValueFrom } from 'rxjs';

import { Delegation, OptionsDelegation } from '../core/modeles';
import { erreursChamps, messageErreur } from '../core/notification.service';
import { BilinguePipe, TraduirePipe } from '../core/pipes';

export interface DonneesDelegation {
  titre: string;
  options: () => Observable<OptionsDelegation>;
  enregistrer: (donnees: object) => Observable<Delegation>;
}

function versSaisieLocale(date: Date): string {
  const decalee = new Date(date.getTime() - date.getTimezoneOffset() * 60000);
  return decalee.toISOString().slice(0, 16);
}

/** Création d'une délégation temporaire (par soi-même ou par un administrateur). */
@Component({
  selector: 'ged-dialogue-delegation',
  imports: [
    ReactiveFormsModule,
    MatDialogModule,
    MatButtonModule,
    MatFormFieldModule,
    MatInputModule,
    MatSelectModule,
    MatCheckboxModule,
    TraduirePipe,
    BilinguePipe,
  ],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <h2 mat-dialog-title>{{ donnees.titre }}</h2>
    <mat-dialog-content>
      <p class="texte-attenue">{{ 'delegation.explication' | t }}</p>
      @if (erreurGenerale()) {
        <p class="erreur" role="alert">{{ erreurGenerale() }}</p>
      }
      <form [formGroup]="formulaire" class="pile" novalidate>
        <mat-form-field appearance="outline">
          <mat-label>{{ 'delegation.delegataire' | t }}</mat-label>
          <mat-select formControlName="delegataire">
            @for (d of options()?.delegataires ?? []; track d.uuid) {
              <mat-option [value]="d.uuid">{{ d.libelle }}</mat-option>
            }
          </mat-select>
          @if (erreurs()['delegataire']) {
            <mat-error>{{ erreurs()['delegataire'] }}</mat-error>
          }
        </mat-form-field>
        <div class="formulaire-grille">
          <mat-form-field appearance="outline">
            <mat-label>{{ 'delegation.debut' | t }}</mat-label>
            <input matInput type="datetime-local" formControlName="debut" />
            @if (erreurs()['debut']) {
              <mat-error>{{ erreurs()['debut'] }}</mat-error>
            }
          </mat-form-field>
          <mat-form-field appearance="outline">
            <mat-label>{{ 'delegation.fin' | t }}</mat-label>
            <input matInput type="datetime-local" formControlName="fin" />
            @if (erreurs()['fin']) {
              <mat-error>{{ erreurs()['fin'] }}</mat-error>
            }
          </mat-form-field>
        </div>
        <mat-form-field appearance="outline">
          <mat-label>{{ 'delegation.motif' | t }}</mat-label>
          <input matInput formControlName="motif" />
        </mat-form-field>
        @if (options()?.roles?.length) {
          <fieldset>
            <legend>{{ 'delegation.roles' | t }}</legend>
            @for (r of options()!.roles; track r.uuid) {
              <mat-checkbox [checked]="roles().includes(r.uuid)" (change)="basculer(r.uuid)">{{
                r.libelle | bilingue: r.libelle_ar
              }}</mat-checkbox>
            }
            <p class="texte-attenue aide">{{ 'delegation.roles_aide' | t }}</p>
          </fieldset>
        }
      </form>
    </mat-dialog-content>
    <mat-dialog-actions align="end">
      <button mat-button mat-dialog-close>{{ 'action.annuler' | t }}</button>
      <button mat-flat-button [disabled]="envoi() || formulaire.invalid" (click)="enregistrer()">
        {{ 'action.enregistrer' | t }}
      </button>
    </mat-dialog-actions>
  `,
  styles: `
    fieldset {
      border: 1px solid var(--ged-bordure);
      border-radius: 12px;
      padding: 8px 16px;
      display: grid;
    }
    legend {
      padding: 0 6px;
      color: var(--ged-texte-attenue);
      font-size: 14px;
    }
    .aide {
      font-size: 12px;
      margin: 4px 0;
    }
    .erreur {
      color: var(--ged-alerte);
    }
  `,
})
export class DialogueDelegation implements OnInit {
  protected readonly donnees = inject<DonneesDelegation>(MAT_DIALOG_DATA);
  private readonly reference = inject(MatDialogRef<DialogueDelegation, Delegation>);
  protected readonly options = signal<OptionsDelegation | null>(null);
  protected readonly roles = signal<string[]>([]);
  protected readonly envoi = signal(false);
  protected readonly erreurs = signal<Record<string, string>>({});
  protected readonly erreurGenerale = signal('');

  protected readonly formulaire = inject(NonNullableFormBuilder).group({
    delegataire: ['', Validators.required],
    debut: [versSaisieLocale(new Date()), Validators.required],
    fin: [versSaisieLocale(new Date(Date.now() + 7 * 86400000)), Validators.required],
    motif: ['', Validators.required],
  });

  async ngOnInit(): Promise<void> {
    this.options.set(await firstValueFrom(this.donnees.options()));
  }

  protected basculer(uuid: string): void {
    this.roles.update((liste) => (liste.includes(uuid) ? liste.filter((r) => r !== uuid) : [...liste, uuid]));
  }

  protected async enregistrer(): Promise<void> {
    const valeurs = this.formulaire.getRawValue();
    this.envoi.set(true);
    this.erreurs.set({});
    this.erreurGenerale.set('');
    try {
      const delegation = await firstValueFrom(
        this.donnees.enregistrer({
          ...valeurs,
          debut: new Date(valeurs.debut).toISOString(),
          fin: new Date(valeurs.fin).toISOString(),
          roles: this.roles(),
        }),
      );
      this.reference.close(delegation);
    } catch (erreur) {
      this.erreurs.set(erreursChamps(erreur));
      this.erreurGenerale.set(messageErreur(erreur));
    } finally {
      this.envoi.set(false);
    }
  }
}
