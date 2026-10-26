import { ChangeDetectionStrategy, Component, inject, signal } from '@angular/core';
import {
  FormControl,
  FormRecord,
  FormsModule,
  NonNullableFormBuilder,
  ReactiveFormsModule,
  Validators,
} from '@angular/forms';
import { MatButtonModule } from '@angular/material/button';
import { MAT_DIALOG_DATA, MatDialogModule, MatDialogRef } from '@angular/material/dialog';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatIconModule } from '@angular/material/icon';
import { MatInputModule } from '@angular/material/input';
import { MatListModule } from '@angular/material/list';
import { MatProgressBarModule } from '@angular/material/progress-bar';
import { MatSelectModule } from '@angular/material/select';
import { firstValueFrom } from 'rxjs';

import { ApiService } from '../../core/api.service';
import { DocumentDetail, DocumentResume, OptionsDocuments } from '../../core/modeles';
import { TraduirePipe } from '../../core/pipes';
import { DepotFichier } from '../../partage/depot-fichier';
import { DialogueSaisie } from '../administration/dialogues-organisation';
import { ChampMetadonnee, controleMetadonnee, valeursMetadonnees } from './champ-metadonnee';

export interface DonneesDocument {
  document: DocumentDetail;
  options: OptionsDocuments;
}

/** Modification de la fiche descriptive (seuls les champs changés sont envoyés). */
@Component({
  selector: 'ged-dialogue-modifier-document',
  imports: [
    ReactiveFormsModule,
    MatDialogModule,
    MatButtonModule,
    MatFormFieldModule,
    MatInputModule,
    MatSelectModule,
    TraduirePipe,
    ChampMetadonnee,
  ],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <h2 mat-dialog-title>{{ 'documents.modifier' | t }}</h2>
    <mat-dialog-content>
      @if (erreurGenerale()) {
        <p class="erreur" role="alert">{{ erreurGenerale() }}</p>
      }
      <form [formGroup]="formulaire" class="formulaire-grille" novalidate>
        <mat-form-field appearance="outline" class="pleine-largeur large">
          <mat-label>{{ 'documents.titre_document' | t }}</mat-label>
          <input matInput formControlName="titre" maxlength="500" />
          @if (erreurs()['titre']) {
            <mat-error>{{ erreurs()['titre'] }}</mat-error>
          }
        </mat-form-field>
        <mat-form-field appearance="outline" class="pleine-largeur large">
          <mat-label>{{ 'documents.objet' | t }}</mat-label>
          <textarea matInput formControlName="objet" rows="2"></textarea>
        </mat-form-field>
        <mat-form-field appearance="outline">
          <mat-label>{{ 'documents.date_document' | t }}</mat-label>
          <input matInput type="date" formControlName="date_document" />
        </mat-form-field>
        <mat-form-field appearance="outline">
          <mat-label>{{ 'documents.confidentialite' | t }}</mat-label>
          <mat-select formControlName="confidentialite">
            @for (n of donnees.options.niveaux; track n.valeur) {
              <mat-option
                [value]="n.valeur"
                [disabled]="
                  n.valeur < donnees.document.confidentialite && !donnees.document.droits.abaisser_confidentialite
                "
                >{{ n.libelle }}</mat-option
              >
            }
          </mat-select>
          @if (erreurs()['confidentialite']) {
            <mat-error>{{ erreurs()['confidentialite'] }}</mat-error>
          }
        </mat-form-field>
        <mat-form-field appearance="outline" class="pleine-largeur large">
          <mat-label>{{ 'documents.mots_cles' | t }}</mat-label>
          <input matInput formControlName="mots_cles" />
          <mat-hint>{{ 'documents.mots_cles_virgules' | t }}</mat-hint>
        </mat-form-field>
        @for (definition of donnees.document.type.metadonnees; track definition.code) {
          <ged-champ-metadonnee
            [definition]="definition"
            [controle]="metadonnees.controls[definition.code]"
            [erreur]="erreurs()['metadonnees.' + definition.code]"
          />
        }
      </form>
    </mat-dialog-content>
    <mat-dialog-actions align="end">
      <button mat-button mat-dialog-close>{{ 'action.annuler' | t }}</button>
      <button mat-flat-button [disabled]="envoi() || formulaire.invalid || metadonnees.invalid" (click)="enregistrer()">
        {{ 'action.enregistrer' | t }}
      </button>
    </mat-dialog-actions>
  `,
  styles: `
    .large {
      grid-column: 1 / -1;
    }
  `,
})
export class DialogueModifierDocument extends DialogueSaisie<DocumentDetail> {
  protected readonly donnees = inject<DonneesDocument>(MAT_DIALOG_DATA);
  protected readonly reference = inject(MatDialogRef<DialogueModifierDocument, DocumentDetail>);
  private readonly api = inject(ApiService);
  private readonly initial = this.donnees.document;

  protected readonly formulaire = inject(NonNullableFormBuilder).group({
    titre: [this.initial.titre, [Validators.required, Validators.maxLength(500)]],
    objet: [this.initial.objet],
    date_document: [this.initial.date_document ?? ''],
    confidentialite: [this.initial.confidentialite],
    mots_cles: [this.initial.mots_cles.join(', ')],
  });
  protected readonly metadonnees = new FormRecord<FormControl<string>>(
    Object.fromEntries(
      this.initial.type.metadonnees.map((d) => [d.code, controleMetadonnee(d, this.initial.metadonnees[d.code])]),
    ),
  );

  protected enregistrer(): void {
    const valeurs = this.formulaire.getRawValue();
    const motsCles = valeurs.mots_cles
      .split(',')
      .map((m) => m.trim())
      .filter(Boolean);
    const metadonnees = valeursMetadonnees(this.initial.type.metadonnees, this.metadonnees);
    const changements: Record<string, unknown> = {};
    if (valeurs.titre !== this.initial.titre) changements['titre'] = valeurs.titre;
    if (valeurs.objet !== this.initial.objet) changements['objet'] = valeurs.objet;
    if (valeurs.date_document !== (this.initial.date_document ?? ''))
      changements['date_document'] = valeurs.date_document || null;
    if (valeurs.confidentialite !== this.initial.confidentialite)
      changements['confidentialite'] = valeurs.confidentialite;
    if (motsCles.join('\u0000') !== this.initial.mots_cles.join('\u0000')) changements['mots_cles'] = motsCles;
    if (JSON.stringify(metadonnees) !== JSON.stringify(this.initial.metadonnees))
      changements['metadonnees'] = metadonnees;
    if (!Object.keys(changements).length) {
      this.reference.close();
      return;
    }
    void this.soumettre(this.api.modifierDocument(this.initial.uuid, changements));
  }
}

export interface DonneesFichier extends DonneesDocument {
  nature: 'versions' | 'pieces-jointes';
}

/** Nouvelle version (fichier principal) ou pièce jointe. */
@Component({
  selector: 'ged-dialogue-fichier',
  imports: [
    FormsModule,
    MatDialogModule,
    MatButtonModule,
    MatFormFieldModule,
    MatInputModule,
    MatProgressBarModule,
    TraduirePipe,
    DepotFichier,
  ],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <h2 mat-dialog-title>
      {{ (donnees.nature === 'versions' ? 'documents.nouvelle_version' : 'documents.joindre') | t }}
    </h2>
    <mat-dialog-content>
      @if (erreurGenerale() || erreurs()['fichier']) {
        <p class="erreur" role="alert">{{ erreurs()['fichier'] || erreurGenerale() }}</p>
      }
      @if (donnees.nature === 'versions' && donnees.document.version) {
        <p class="texte-attenue">
          {{ 'documents.nouvelle_version_aide' | t: { numero: donnees.document.version + 1 } }}
        </p>
      }
      <ged-depot-fichier
        [extensions]="extensions"
        [tailleMaxMo]="donnees.options.taille_max_mo"
        [messageFormat]="'depot.format_refuse' | t"
        [messageTropGros]="'depot.trop_gros' | t: { taille: donnees.options.taille_max_mo }"
        (fichierChange)="fichier.set($event)"
      />
      @if (donnees.nature === 'versions') {
        <mat-form-field appearance="outline" class="pleine-largeur commentaire">
          <mat-label>{{ 'documents.commentaire_version' | t }}</mat-label>
          <input matInput [(ngModel)]="commentaire" />
        </mat-form-field>
      }
      @if (envoi()) {
        <mat-progress-bar mode="indeterminate" />
      }
    </mat-dialog-content>
    <mat-dialog-actions align="end">
      <button mat-button mat-dialog-close>{{ 'action.annuler' | t }}</button>
      <button mat-flat-button [disabled]="envoi() || !fichier()" (click)="envoyer()">
        {{ 'depot.envoyer' | t }}
      </button>
    </mat-dialog-actions>
  `,
  styles: `
    .commentaire {
      margin-top: 16px;
    }
  `,
})
export class DialogueFichier extends DialogueSaisie<DocumentDetail> {
  protected readonly donnees = inject<DonneesFichier>(MAT_DIALOG_DATA);
  protected readonly reference = inject(MatDialogRef<DialogueFichier, DocumentDetail>);
  private readonly api = inject(ApiService);
  protected readonly fichier = signal<File | null>(null);
  protected commentaire = '';
  protected readonly extensions = this.donnees.options.formats
    .filter((f) => {
      const admis = this.donnees.document.type.formats_autorises;
      return !admis.length || admis.includes(f.code);
    })
    .flatMap((f) => f.extensions ?? []);

  protected envoyer(): void {
    const fichier = this.fichier();
    if (!fichier) return;
    const donnees = new FormData();
    donnees.append('fichier', fichier, fichier.name);
    if (this.commentaire) donnees.append('commentaire', this.commentaire);
    void this.soumettre(this.api.ajouterFichier(this.donnees.document.uuid, this.donnees.nature, donnees));
  }
}

/** Relier le document à un autre document visible. */
@Component({
  selector: 'ged-dialogue-relation',
  imports: [
    FormsModule,
    MatDialogModule,
    MatButtonModule,
    MatFormFieldModule,
    MatIconModule,
    MatInputModule,
    MatListModule,
    MatSelectModule,
    TraduirePipe,
  ],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <h2 mat-dialog-title>{{ 'documents.relier' | t }}</h2>
    <mat-dialog-content>
      @if (erreurGenerale() || erreurs()['cible']) {
        <p class="erreur" role="alert">{{ erreurs()['cible'] || erreurGenerale() }}</p>
      }
      <mat-form-field appearance="outline" class="pleine-largeur">
        <mat-label>{{ 'documents.relation_nature' | t }}</mat-label>
        <mat-select [(ngModel)]="nature">
          @for (n of donnees.options.natures_relation; track n.valeur) {
            <mat-option [value]="n.valeur">{{ n.libelle }}</mat-option>
          }
        </mat-select>
      </mat-form-field>
      <mat-form-field appearance="outline" class="pleine-largeur">
        <mat-icon matPrefix>search</mat-icon>
        <mat-label>{{ 'documents.relation_rechercher' | t }}</mat-label>
        <input matInput [ngModel]="recherche()" (ngModelChange)="chercher($event)" />
      </mat-form-field>
      <mat-selection-list [multiple]="false" (selectionChange)="cible.set($event.options[0].value)">
        @for (d of resultats(); track d.uuid) {
          <mat-list-option [value]="d.uuid">
            <span matListItemTitle>{{ d.titre }}</span>
            <span matListItemLine class="ltr">{{ d.reference ?? '' }}</span>
          </mat-list-option>
        } @empty {
          @if (recherche()) {
            <p class="texte-attenue">{{ 'documents.aucun' | t }}</p>
          }
        }
      </mat-selection-list>
    </mat-dialog-content>
    <mat-dialog-actions align="end">
      <button mat-button mat-dialog-close>{{ 'action.annuler' | t }}</button>
      <button mat-flat-button [disabled]="envoi() || !cible() || !nature" (click)="relier()">
        {{ 'documents.relier' | t }}
      </button>
    </mat-dialog-actions>
  `,
})
export class DialogueRelation extends DialogueSaisie<DocumentDetail> {
  protected readonly donnees = inject<DonneesDocument>(MAT_DIALOG_DATA);
  protected readonly reference = inject(MatDialogRef<DialogueRelation, DocumentDetail>);
  private readonly api = inject(ApiService);
  protected readonly recherche = signal('');
  protected readonly resultats = signal<DocumentResume[]>([]);
  protected readonly cible = signal('');
  protected nature = 'voir_aussi';
  private minuterie: ReturnType<typeof setTimeout> | undefined;

  protected chercher(texte: string): void {
    this.recherche.set(texte);
    clearTimeout(this.minuterie);
    this.minuterie = setTimeout(async () => {
      if (!texte.trim()) {
        this.resultats.set([]);
        return;
      }
      const page = await firstValueFrom(this.api.documents({ q: texte }));
      this.resultats.set(page.resultats.filter((d) => d.uuid !== this.donnees.document.uuid));
    }, 300);
  }

  protected relier(): void {
    void this.soumettre(this.api.relier(this.donnees.document.uuid, this.cible(), this.nature));
  }
}
