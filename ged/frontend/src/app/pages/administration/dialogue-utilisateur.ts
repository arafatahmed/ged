import { ChangeDetectionStrategy, Component, OnInit, inject, signal } from '@angular/core';
import { NonNullableFormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { MatButtonModule } from '@angular/material/button';
import { MAT_DIALOG_DATA, MatDialogModule, MatDialogRef } from '@angular/material/dialog';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatIconModule } from '@angular/material/icon';
import { MatInputModule } from '@angular/material/input';
import { MatSelectModule } from '@angular/material/select';
import { MatTooltipModule } from '@angular/material/tooltip';
import { firstValueFrom } from 'rxjs';

import { ApiService } from '../../core/api.service';
import { OptionsUtilisateurs, UtilisateurResume } from '../../core/modeles';
import { erreursChamps, messageErreur } from '../../core/notification.service';
import { BilinguePipe, TraduirePipe } from '../../core/pipes';
import { Squelette } from '../../partage/etats';

/** Création d'un compte : identité, habilitation, mot de passe temporaire et affectation initiale. */
@Component({
  selector: 'ged-dialogue-utilisateur',
  imports: [
    ReactiveFormsModule,
    MatDialogModule,
    MatButtonModule,
    MatFormFieldModule,
    MatInputModule,
    MatSelectModule,
    MatIconModule,
    MatTooltipModule,
    TraduirePipe,
    BilinguePipe,
    Squelette,
  ],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <h2 mat-dialog-title>{{ 'utilisateurs.nouveau' | t }}</h2>
    <mat-dialog-content>
      @if (options(); as o) {
        @if (erreurGenerale()) {
          <p class="erreur" role="alert">{{ erreurGenerale() }}</p>
        }
        <form [formGroup]="formulaire" novalidate>
          <h3>{{ 'utilisateurs.section_identite' | t }}</h3>
          <div class="formulaire-grille">
            <mat-form-field appearance="outline">
              <mat-label>{{ 'champ.identifiant' | t }}</mat-label>
              <input matInput formControlName="identifiant" dir="ltr" autocomplete="off" />
              @if (erreurs()['identifiant']) {
                <mat-error>{{ erreurs()['identifiant'] }}</mat-error>
              }
            </mat-form-field>
            <mat-form-field appearance="outline">
              <mat-label>{{ 'champ.courriel' | t }}</mat-label>
              <input matInput formControlName="courriel" type="email" dir="ltr" />
              @if (erreurs()['courriel']) {
                <mat-error>{{ erreurs()['courriel'] }}</mat-error>
              }
            </mat-form-field>
            <mat-form-field appearance="outline">
              <mat-label>{{ 'champ.nom' | t }}</mat-label>
              <input matInput formControlName="nom" />
            </mat-form-field>
            <mat-form-field appearance="outline">
              <mat-label>{{ 'champ.prenom' | t }}</mat-label>
              <input matInput formControlName="prenom" />
            </mat-form-field>
            <mat-form-field appearance="outline">
              <mat-label>{{ 'champ.nom_ar' | t }}</mat-label>
              <input matInput formControlName="nom_ar" dir="rtl" lang="ar" />
            </mat-form-field>
            <mat-form-field appearance="outline">
              <mat-label>{{ 'champ.langue' | t }}</mat-label>
              <mat-select formControlName="langue">
                <mat-option value="">{{ 'compte.langue_institution' | t }}</mat-option>
                @for (l of o.langues; track l.valeur) {
                  <mat-option [value]="l.valeur">{{ l.libelle }}</mat-option>
                }
              </mat-select>
            </mat-form-field>
          </div>
          <h3>{{ 'utilisateurs.section_securite' | t }}</h3>
          <div class="formulaire-grille">
            <mat-form-field appearance="outline">
              <mat-label>{{ 'champ.niveau' | t }}</mat-label>
              <mat-select formControlName="niveau_habilitation">
                @for (n of o.niveaux; track n.valeur) {
                  <mat-option [value]="n.valeur">{{ n.libelle }}</mat-option>
                }
              </mat-select>
              @if (erreurs()['niveau_habilitation']) {
                <mat-error>{{ erreurs()['niveau_habilitation'] }}</mat-error>
              }
            </mat-form-field>
            <mat-form-field appearance="outline">
              <mat-label>{{ 'utilisateurs.mdp_temporaire' | t }}</mat-label>
              <input matInput formControlName="mot_de_passe_temporaire" dir="ltr" autocomplete="off" />
              <button
                mat-icon-button
                matSuffix
                type="button"
                (click)="regenerer()"
                [matTooltip]="'utilisateurs.mdp_regenerer' | t"
              >
                <mat-icon>autorenew</mat-icon>
              </button>
              <mat-hint>{{ 'utilisateurs.mdp_aide' | t }}</mat-hint>
              @if (erreurs()['mot_de_passe_temporaire']) {
                <mat-error>{{ erreurs()['mot_de_passe_temporaire'] }}</mat-error>
              }
            </mat-form-field>
          </div>
          <h3>{{ 'utilisateurs.section_affectation' | t }}</h3>
          <div class="formulaire-grille">
            <mat-form-field appearance="outline">
              <mat-label>{{ 'champ.unite' | t }}</mat-label>
              <mat-select formControlName="unite">
                <mat-option value="">—</mat-option>
                @for (u of o.unites; track u.uuid) {
                  <mat-option [value]="u.uuid"
                    ><span [style.padding-inline-start.px]="u.profondeur * 14">{{ u.libelle }}</span></mat-option
                  >
                }
              </mat-select>
            </mat-form-field>
            <mat-form-field appearance="outline">
              <mat-label>{{ 'champ.role' | t }}</mat-label>
              <mat-select formControlName="role">
                <mat-option value="">—</mat-option>
                @for (r of o.roles; track r.uuid) {
                  <mat-option [value]="r.uuid">{{ r.libelle | bilingue: r.libelle_ar }}</mat-option>
                }
              </mat-select>
            </mat-form-field>
          </div>
        </form>
      } @else {
        <ged-squelette [lignes]="6" />
      }
    </mat-dialog-content>
    <mat-dialog-actions align="end">
      <button mat-button mat-dialog-close>{{ 'action.annuler' | t }}</button>
      <button mat-flat-button [disabled]="envoi() || formulaire.invalid" (click)="enregistrer()">
        {{ 'utilisateurs.creer' | t }}
      </button>
    </mat-dialog-actions>
  `,
  styles: `
    h3 {
      font-size: 14px;
      font-weight: 600;
      color: var(--ged-texte-attenue);
      margin: 12px 0 8px;
      text-transform: uppercase;
      letter-spacing: 0.04em;
    }
    .erreur {
      color: var(--ged-alerte);
    }
  `,
})
export class DialogueUtilisateur implements OnInit {
  private readonly api = inject(ApiService);
  private readonly reference = inject(
    MatDialogRef<DialogueUtilisateur, { compte: UtilisateurResume; motDePasse: string }>,
  );
  protected readonly donnees = inject(MAT_DIALOG_DATA, { optional: true });
  protected readonly options = signal<OptionsUtilisateurs | null>(null);
  protected readonly envoi = signal(false);
  protected readonly erreurs = signal<Record<string, string>>({});
  protected readonly erreurGenerale = signal('');
  protected readonly formulaire = inject(NonNullableFormBuilder).group({
    identifiant: ['', [Validators.required, Validators.maxLength(150)]],
    nom: ['', Validators.required],
    prenom: ['', Validators.required],
    nom_ar: [''],
    courriel: ['', Validators.email],
    langue: [''],
    niveau_habilitation: [0],
    mot_de_passe_temporaire: ['', [Validators.required, Validators.minLength(12)]],
    unite: [''],
    role: [''],
  });

  async ngOnInit(): Promise<void> {
    const options = await firstValueFrom(this.api.optionsUtilisateurs());
    this.options.set(options);
    this.formulaire.patchValue({ mot_de_passe_temporaire: options.mot_de_passe_suggere });
  }

  protected async regenerer(): Promise<void> {
    const options = await firstValueFrom(this.api.optionsUtilisateurs());
    this.formulaire.patchValue({ mot_de_passe_temporaire: options.mot_de_passe_suggere });
  }

  protected async enregistrer(): Promise<void> {
    const valeurs = this.formulaire.getRawValue();
    this.envoi.set(true);
    this.erreurs.set({});
    this.erreurGenerale.set('');
    try {
      const compte = await firstValueFrom(this.api.creerUtilisateur(valeurs));
      this.reference.close({ compte, motDePasse: valeurs.mot_de_passe_temporaire });
    } catch (erreur) {
      const champs = erreursChamps(erreur);
      this.erreurs.set(champs);
      for (const champ of Object.keys(champs)) this.formulaire.get(champ)?.setErrors({ serveur: true });
      this.erreurGenerale.set(champs['__all__'] ?? (Object.keys(champs).length ? '' : messageErreur(erreur)));
    } finally {
      this.envoi.set(false);
    }
  }
}
