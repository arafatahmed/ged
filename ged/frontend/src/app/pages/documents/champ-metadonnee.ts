import { ChangeDetectionStrategy, Component, input } from '@angular/core';
import { FormControl, FormRecord, ReactiveFormsModule, Validators } from '@angular/forms';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { MatSelectModule } from '@angular/material/select';

import { DefinitionMetadonnee } from '../../core/modeles';
import { BilinguePipe, TraduirePipe } from '../../core/pipes';

/** Contrôle de formulaire d'une métadonnée personnalisée (obligatoire selon sa définition). */
export function controleMetadonnee(definition: DefinitionMetadonnee, valeur: unknown = ''): FormControl<string> {
  return new FormControl(valeur === null || valeur === undefined ? '' : String(valeur), {
    nonNullable: true,
    validators: definition.obligatoire ? [Validators.required] : [],
  });
}

/** Valeurs à envoyer à l'API : les champs vides sont omis, les nombres convertis. */
export function valeursMetadonnees(
  definitions: DefinitionMetadonnee[],
  groupe: FormRecord<FormControl<string>>,
): Record<string, string | number> {
  const valeurs: Record<string, string | number> = {};
  for (const definition of definitions) {
    const brute = groupe.controls[definition.code]?.value?.trim() ?? '';
    if (!brute) continue;
    valeurs[definition.code] = definition.nature === 'nombre' && !Number.isNaN(Number(brute)) ? Number(brute) : brute;
  }
  return valeurs;
}

/** Champ de saisie d'une métadonnée, selon sa nature (texte, nombre, date, liste). */
@Component({
  selector: 'ged-champ-metadonnee',
  imports: [ReactiveFormsModule, MatFormFieldModule, MatInputModule, MatSelectModule, TraduirePipe, BilinguePipe],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <mat-form-field appearance="outline" class="pleine-largeur">
      <mat-label>{{ definition().libelle_fr | bilingue: definition().libelle_ar }}</mat-label>
      @switch (definition().nature) {
        @case ('liste') {
          <mat-select [formControl]="controle()" [required]="definition().obligatoire">
            @if (!definition().obligatoire) {
              <mat-option value="">—</mat-option>
            }
            @for (valeur of definition().valeurs_liste; track valeur) {
              <mat-option [value]="valeur">{{ valeur }}</mat-option>
            }
          </mat-select>
        }
        @case ('date') {
          <input matInput type="date" [formControl]="controle()" [required]="definition().obligatoire" />
        }
        @case ('nombre') {
          <input matInput type="number" dir="ltr" [formControl]="controle()" [required]="definition().obligatoire" />
        }
        @default {
          <input matInput maxlength="1000" [formControl]="controle()" [required]="definition().obligatoire" />
        }
      }
      @if (erreur()) {
        <mat-error>{{ erreur() }}</mat-error>
      } @else if (controle().hasError('required')) {
        <mat-error>{{ 'erreur.champ_obligatoire' | t }}</mat-error>
      }
    </mat-form-field>
  `,
})
export class ChampMetadonnee {
  readonly definition = input.required<DefinitionMetadonnee>();
  readonly controle = input.required<FormControl<string>>();
  /** Message d'erreur renvoyé par le serveur pour ce champ. */
  readonly erreur = input<string>('');
}
