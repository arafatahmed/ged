import { ChangeDetectionStrategy, Component, inject, signal } from '@angular/core';
import { NonNullableFormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { MatButtonModule } from '@angular/material/button';
import { MAT_DIALOG_DATA, MatDialogModule, MatDialogRef } from '@angular/material/dialog';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { MatSelectModule } from '@angular/material/select';
import { MatSlideToggleModule } from '@angular/material/slide-toggle';
import { Observable, firstValueFrom } from 'rxjs';

import { Poste, TypeUnite, Unite } from '../../core/modeles';
import { erreursChamps, messageErreur } from '../../core/notification.service';
import { BilinguePipe, TraduirePipe } from '../../core/pipes';

/** Base des dialogues de saisie : envoi, erreurs par champ et erreur générale. */
abstract class DialogueSaisie<R> {
  protected readonly envoi = signal(false);
  protected readonly erreurs = signal<Record<string, string>>({});
  protected readonly erreurGenerale = signal('');
  protected abstract readonly reference: MatDialogRef<unknown, R>;

  protected async soumettre(appel: Observable<R>): Promise<void> {
    this.envoi.set(true);
    this.erreurs.set({});
    this.erreurGenerale.set('');
    try {
      this.reference.close(await firstValueFrom(appel));
    } catch (erreur) {
      const champs = erreursChamps(erreur);
      this.erreurs.set(champs);
      this.erreurGenerale.set(champs['__all__'] ?? (Object.keys(champs).length ? '' : messageErreur(erreur)));
    } finally {
      this.envoi.set(false);
    }
  }
}

export interface DonneesUnite {
  unite: Unite | null;
  parent: string | null;
  unites: Unite[];
  types: TypeUnite[];
  enregistrer: (donnees: object, uuid?: string) => Observable<Unite>;
}

@Component({
  selector: 'ged-dialogue-unite',
  imports: [
    ReactiveFormsModule,
    MatDialogModule,
    MatButtonModule,
    MatFormFieldModule,
    MatInputModule,
    MatSelectModule,
    TraduirePipe,
    BilinguePipe,
  ],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <h2 mat-dialog-title>{{ (donnees.unite ? 'organisation.modifier_unite' : 'organisation.nouvelle_unite') | t }}</h2>
    <mat-dialog-content>
      @if (erreurGenerale()) {
        <p class="erreur" role="alert">{{ erreurGenerale() }}</p>
      }
      <form [formGroup]="formulaire" class="formulaire-grille" novalidate>
        <mat-form-field appearance="outline">
          <mat-label>{{ 'organisation.type' | t }}</mat-label>
          <mat-select formControlName="type">
            @for (t of donnees.types; track t.id) {
              <mat-option [value]="t.id">{{ t.libelle_fr | bilingue: t.libelle_ar }}</mat-option>
            }
          </mat-select>
          @if (erreurs()['type']) {
            <mat-error>{{ erreurs()['type'] }}</mat-error>
          }
        </mat-form-field>
        <mat-form-field appearance="outline">
          <mat-label>{{ 'organisation.parent' | t }}</mat-label>
          <mat-select formControlName="parent">
            @if (estRacine) {
              <mat-option value="">{{ 'organisation.aucun_parent' | t }}</mat-option>
            }
            @for (u of parents; track u.uuid) {
              <mat-option [value]="u.uuid"
                ><span [style.padding-inline-start.px]="u.profondeur * 14">{{
                  u.libelle_fr | bilingue: u.libelle_ar
                }}</span></mat-option
              >
            }
          </mat-select>
          @if (erreurs()['parent']) {
            <mat-error>{{ erreurs()['parent'] }}</mat-error>
          }
        </mat-form-field>
        <mat-form-field appearance="outline">
          <mat-label>{{ 'organisation.code' | t }}</mat-label>
          <input matInput formControlName="code" dir="ltr" />
          <mat-hint>{{ 'organisation.code_aide' | t }}</mat-hint>
          @if (erreurs()['code']) {
            <mat-error>{{ erreurs()['code'] }}</mat-error>
          }
        </mat-form-field>
        <mat-form-field appearance="outline">
          <mat-label>{{ 'organisation.sigle' | t }}</mat-label>
          <input matInput formControlName="sigle" dir="ltr" />
        </mat-form-field>
        <mat-form-field appearance="outline">
          <mat-label>{{ 'champ.libelle_fr' | t }}</mat-label>
          <input matInput formControlName="libelle_fr" lang="fr" dir="ltr" />
          @if (erreurs()['libelle_fr']) {
            <mat-error>{{ erreurs()['libelle_fr'] }}</mat-error>
          }
        </mat-form-field>
        <mat-form-field appearance="outline">
          <mat-label>{{ 'champ.libelle_ar' | t }}</mat-label>
          <input matInput formControlName="libelle_ar" lang="ar" dir="rtl" />
        </mat-form-field>
      </form>
    </mat-dialog-content>
    <mat-dialog-actions align="end">
      <button mat-button mat-dialog-close>{{ 'action.annuler' | t }}</button>
      <button mat-flat-button [disabled]="envoi() || formulaire.invalid" (click)="enregistrer()">
        {{ 'action.enregistrer' | t }}
      </button>
    </mat-dialog-actions>
  `,
})
export class DialogueUnite extends DialogueSaisie<Unite> {
  protected readonly donnees = inject<DonneesUnite>(MAT_DIALOG_DATA);
  protected readonly reference = inject(MatDialogRef<DialogueUnite, Unite>);
  /** L'unité racine représente l'institution : elle reste sans parent. */
  protected readonly estRacine = !!this.donnees.unite && this.donnees.unite.parent === null;
  protected readonly parents = this.donnees.unites.filter(
    (u) => u.actif && (!this.donnees.unite || (u.uuid !== this.donnees.unite.uuid && !this.descendDe(u))),
  );
  protected readonly formulaire = inject(NonNullableFormBuilder).group({
    type: [this.donnees.unite?.type ?? this.donnees.types[0]?.id ?? 0, Validators.required],
    parent: [
      {
        value: this.donnees.unite ? (this.donnees.unite.parent ?? '') : (this.donnees.parent ?? ''),
        disabled: this.estRacine,
      },
      this.estRacine ? [] : [Validators.required],
    ],
    code: [this.donnees.unite?.code ?? '', [Validators.required, Validators.pattern(/^[-a-zA-Z0-9_]+$/)]],
    sigle: [this.donnees.unite?.sigle ?? ''],
    libelle_fr: [this.donnees.unite?.libelle_fr ?? '', Validators.required],
    libelle_ar: [this.donnees.unite?.libelle_ar ?? ''],
  });

  /** Une unité ne peut pas être rattachée à l'une de ses sous-unités. */
  private descendDe(candidat: Unite): boolean {
    const parents = new Map(this.donnees.unites.map((u) => [u.uuid, u.parent]));
    let courant: string | null = candidat.parent;
    while (courant) {
      if (courant === this.donnees.unite?.uuid) return true;
      courant = parents.get(courant) ?? null;
    }
    return false;
  }

  protected enregistrer(): void {
    const valeurs = this.formulaire.getRawValue();
    void this.soumettre(
      this.donnees.enregistrer({ ...valeurs, parent: valeurs.parent || null }, this.donnees.unite?.uuid),
    );
  }
}

export interface DonneesTypeUnite {
  type: TypeUnite | null;
  enregistrer: (donnees: object, id?: number) => Observable<TypeUnite>;
}

@Component({
  selector: 'ged-dialogue-type-unite',
  imports: [
    ReactiveFormsModule,
    MatDialogModule,
    MatButtonModule,
    MatFormFieldModule,
    MatInputModule,
    MatSlideToggleModule,
    TraduirePipe,
  ],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <h2 mat-dialog-title>{{ (donnees.type ? 'organisation.modifier_type' : 'organisation.nouveau_type') | t }}</h2>
    <mat-dialog-content>
      <form [formGroup]="formulaire" class="formulaire-grille" novalidate>
        <mat-form-field appearance="outline">
          <mat-label>{{ 'organisation.code' | t }}</mat-label>
          <input matInput formControlName="code" dir="ltr" />
          @if (erreurs()['code']) {
            <mat-error>{{ erreurs()['code'] }}</mat-error>
          }
        </mat-form-field>
        <mat-form-field appearance="outline">
          <mat-label>{{ 'organisation.ordre' | t }}</mat-label>
          <input matInput type="number" formControlName="ordre" />
        </mat-form-field>
        <mat-form-field appearance="outline">
          <mat-label>{{ 'champ.libelle_fr' | t }}</mat-label>
          <input matInput formControlName="libelle_fr" dir="ltr" />
        </mat-form-field>
        <mat-form-field appearance="outline">
          <mat-label>{{ 'champ.libelle_ar' | t }}</mat-label>
          <input matInput formControlName="libelle_ar" dir="rtl" />
        </mat-form-field>
        <mat-slide-toggle formControlName="actif">{{ 'champ.actif' | t }}</mat-slide-toggle>
      </form>
    </mat-dialog-content>
    <mat-dialog-actions align="end">
      <button mat-button mat-dialog-close>{{ 'action.annuler' | t }}</button>
      <button mat-flat-button [disabled]="envoi() || formulaire.invalid" (click)="enregistrer()">
        {{ 'action.enregistrer' | t }}
      </button>
    </mat-dialog-actions>
  `,
})
export class DialogueTypeUnite extends DialogueSaisie<TypeUnite> {
  protected readonly donnees = inject<DonneesTypeUnite>(MAT_DIALOG_DATA);
  protected readonly reference = inject(MatDialogRef<DialogueTypeUnite, TypeUnite>);
  protected readonly formulaire = inject(NonNullableFormBuilder).group({
    code: [this.donnees.type?.code ?? '', Validators.required],
    libelle_fr: [this.donnees.type?.libelle_fr ?? '', Validators.required],
    libelle_ar: [this.donnees.type?.libelle_ar ?? ''],
    ordre: [this.donnees.type?.ordre ?? 0],
    actif: [this.donnees.type?.actif ?? true],
  });

  protected enregistrer(): void {
    void this.soumettre(this.donnees.enregistrer(this.formulaire.getRawValue(), this.donnees.type?.id));
  }
}

export interface DonneesPoste {
  poste: Poste | null;
  unites: Unite[];
  postes: Poste[];
  enregistrer: (donnees: object, id?: number) => Observable<Poste>;
}

@Component({
  selector: 'ged-dialogue-poste',
  imports: [
    ReactiveFormsModule,
    MatDialogModule,
    MatButtonModule,
    MatFormFieldModule,
    MatInputModule,
    MatSelectModule,
    MatSlideToggleModule,
    TraduirePipe,
    BilinguePipe,
  ],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <h2 mat-dialog-title>{{ (donnees.poste ? 'postes.modifier' : 'postes.nouveau') | t }}</h2>
    <mat-dialog-content>
      @if (erreurGenerale()) {
        <p class="erreur" role="alert">{{ erreurGenerale() }}</p>
      }
      <form [formGroup]="formulaire" class="formulaire-grille" novalidate>
        <mat-form-field appearance="outline">
          <mat-label>{{ 'champ.unite' | t }}</mat-label>
          <mat-select formControlName="unite">
            @for (u of donnees.unites; track u.uuid) {
              <mat-option [value]="u.uuid">{{ u.libelle_fr | bilingue: u.libelle_ar }}</mat-option>
            }
          </mat-select>
        </mat-form-field>
        <mat-form-field appearance="outline">
          <mat-label>{{ 'postes.superieur' | t }}</mat-label>
          <mat-select formControlName="superieur">
            <mat-option [value]="null">—</mat-option>
            @for (p of superieurs; track p.id) {
              <mat-option [value]="p.id">{{ p.intitule_fr | bilingue: p.intitule_ar }}</mat-option>
            }
          </mat-select>
          @if (erreurs()['superieur']) {
            <mat-error>{{ erreurs()['superieur'] }}</mat-error>
          }
        </mat-form-field>
        <mat-form-field appearance="outline">
          <mat-label>{{ 'champ.intitule_fr' | t }}</mat-label>
          <input matInput formControlName="intitule_fr" dir="ltr" />
        </mat-form-field>
        <mat-form-field appearance="outline">
          <mat-label>{{ 'champ.intitule_ar' | t }}</mat-label>
          <input matInput formControlName="intitule_ar" dir="rtl" />
        </mat-form-field>
        <mat-slide-toggle formControlName="actif">{{ 'champ.actif' | t }}</mat-slide-toggle>
      </form>
    </mat-dialog-content>
    <mat-dialog-actions align="end">
      <button mat-button mat-dialog-close>{{ 'action.annuler' | t }}</button>
      <button mat-flat-button [disabled]="envoi() || formulaire.invalid" (click)="enregistrer()">
        {{ 'action.enregistrer' | t }}
      </button>
    </mat-dialog-actions>
  `,
})
export class DialoguePoste extends DialogueSaisie<Poste> {
  protected readonly donnees = inject<DonneesPoste>(MAT_DIALOG_DATA);
  protected readonly reference = inject(MatDialogRef<DialoguePoste, Poste>);
  protected readonly superieurs = this.donnees.postes.filter((p) => p.actif && p.id !== this.donnees.poste?.id);
  protected readonly formulaire = inject(NonNullableFormBuilder).group({
    unite: [this.donnees.poste?.unite ?? '', Validators.required],
    superieur: this.donnees.poste?.superieur ?? (null as number | null),
    intitule_fr: [this.donnees.poste?.intitule_fr ?? '', Validators.required],
    intitule_ar: [this.donnees.poste?.intitule_ar ?? ''],
    actif: [this.donnees.poste?.actif ?? true],
  });

  protected enregistrer(): void {
    void this.soumettre(this.donnees.enregistrer(this.formulaire.getRawValue(), this.donnees.poste?.id));
  }
}
