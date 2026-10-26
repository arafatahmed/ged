import { ChangeDetectionStrategy, Component, OnInit, inject, signal } from '@angular/core';
import { FormArray, NonNullableFormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { MatButtonModule } from '@angular/material/button';
import { MatCheckboxModule } from '@angular/material/checkbox';
import { MAT_DIALOG_DATA, MatDialogModule, MatDialogRef } from '@angular/material/dialog';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatIconModule } from '@angular/material/icon';
import { MatInputModule } from '@angular/material/input';
import { MatSelectModule } from '@angular/material/select';
import { MatSlideToggleModule } from '@angular/material/slide-toggle';
import { firstValueFrom } from 'rxjs';

import { ApiService } from '../../core/api.service';
import { DefinitionMetadonnee, FormatFichier, NatureMetadonnee, TypeDocument } from '../../core/modeles';
import { NotificationService } from '../../core/notification.service';
import { BilinguePipe, TraduirePipe } from '../../core/pipes';
import { DialoguesService } from '../../partage/dialogues.service';
import { EntetePage } from '../../partage/entete-page';
import { EtatVide, Squelette } from '../../partage/etats';
import { PastilleConfidentialite } from '../documents/pastilles';
import { DialogueSaisie } from './dialogues-organisation';

/** Types de documents de l'institution et leurs métadonnées personnalisées. */
@Component({
  selector: 'ged-types-document',
  imports: [
    MatButtonModule,
    MatIconModule,
    TraduirePipe,
    BilinguePipe,
    EntetePage,
    EtatVide,
    Squelette,
    PastilleConfidentialite,
  ],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <ged-entete-page
      [titre]="'types_document.titre' | t"
      [sousTitre]="'types_document.sous_titre' | t"
      icone="category"
    >
      <button mat-flat-button (click)="editer(null)"><mat-icon>add</mat-icon>{{ 'types_document.nouveau' | t }}</button>
    </ged-entete-page>
    @if (types(); as liste) {
      @if (liste.length) {
        <div class="grille">
          @for (t of liste; track t.uuid; let i = $index) {
            <button
              type="button"
              class="carte carte-interactive type"
              [class.inactif]="!t.actif"
              (click)="editer(t)"
              animate.enter="entree-montee"
              [style.--rang]="i"
            >
              <span class="ligne">
                <strong>{{ t.libelle_fr | bilingue: t.libelle_ar }}</strong>
                <span class="espace"></span>
                @if (!t.actif) {
                  <span class="pastille">{{ 'champ.inactif' | t }}</span>
                }
              </span>
              <span class="texte-attenue ltr code">{{ t.code }}</span>
              <span class="ligne details">
                <ged-pastille-confidentialite [valeur]="t.confidentialite_defaut" />
                <span class="pastille">{{ 'types_document.nombre_metadonnees' | t: { nombre: actives(t) } }}</span>
                <span class="pastille">{{ 'types_document.nombre_documents' | t: { nombre: t.documents ?? 0 } }}</span>
              </span>
              <span class="texte-attenue formats ltr">
                {{ t.formats_autorises.length ? t.formats_autorises.join(', ') : ('types_document.tous_formats' | t) }}
              </span>
            </button>
          }
        </div>
      } @else {
        <ged-etat-vide icone="category" [message]="'types_document.aucun' | t" />
      }
    } @else {
      <div class="carte"><ged-squelette /></div>
    }
  `,
  styles: `
    .type {
      display: grid;
      gap: 8px;
      text-align: start;
      font: inherit;
      color: inherit;
      cursor: pointer;
    }
    .inactif {
      opacity: 0.65;
    }
    .code,
    .formats {
      font-size: 12px;
    }
    .details {
      gap: 6px;
    }
  `,
})
export class TypesDocument implements OnInit {
  private readonly api = inject(ApiService);
  private readonly dialogues = inject(DialoguesService);
  private readonly notifications = inject(NotificationService);
  protected readonly types = signal<TypeDocument[] | null>(null);
  private formats: FormatFichier[] = [];

  async ngOnInit(): Promise<void> {
    await this.charger();
  }

  private async charger(): Promise<void> {
    try {
      const reponse = await firstValueFrom(this.api.typesDocument());
      this.formats = reponse.formats;
      this.types.set(reponse.types);
    } catch (erreur) {
      this.notifications.erreur(erreur);
    }
  }

  protected actives(type: TypeDocument): number {
    return type.metadonnees.filter((d) => d.actif).length;
  }

  protected async editer(type: TypeDocument | null): Promise<void> {
    const resultat = await this.dialogues.ouvrir<DialogueTypeDocument, DonneesTypeDocument, TypeDocument>(
      DialogueTypeDocument,
      { type, formats: this.formats },
      { width: '860px' },
    );
    if (resultat) {
      this.notifications.succes('types_document.enregistre');
      await this.charger();
    }
  }
}

interface DonneesTypeDocument {
  type: TypeDocument | null;
  formats: FormatFichier[];
}

const NATURES: NatureMetadonnee[] = ['texte', 'nombre', 'date', 'liste'];

@Component({
  selector: 'ged-dialogue-type-document',
  imports: [
    ReactiveFormsModule,
    MatDialogModule,
    MatButtonModule,
    MatCheckboxModule,
    MatFormFieldModule,
    MatIconModule,
    MatInputModule,
    MatSelectModule,
    MatSlideToggleModule,
    TraduirePipe,
  ],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <h2 mat-dialog-title>{{ (donnees.type ? 'types_document.modifier' : 'types_document.nouveau') | t }}</h2>
    <mat-dialog-content>
      @if (erreurGenerale()) {
        <p class="erreur" role="alert">{{ erreurGenerale() }}</p>
      }
      <form [formGroup]="formulaire" class="formulaire-grille" novalidate>
        <mat-form-field appearance="outline">
          <mat-label>{{ 'organisation.code' | t }}</mat-label>
          <input matInput formControlName="code" dir="ltr" />
          @if (erreurs()['code']) {
            <mat-error>{{ erreurs()['code'] }}</mat-error>
          }
        </mat-form-field>
        <mat-form-field appearance="outline">
          <mat-label>{{ 'types_document.categorie' | t }}</mat-label>
          <input matInput formControlName="categorie" />
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
        <mat-form-field appearance="outline">
          <mat-label>{{ 'types_document.formats' | t }}</mat-label>
          <mat-select formControlName="formats_autorises" multiple>
            @for (f of donnees.formats; track f.code) {
              <mat-option [value]="f.code">{{ f.libelle }}</mat-option>
            }
          </mat-select>
          <mat-hint>{{ 'types_document.formats_aide' | t }}</mat-hint>
          @if (erreurs()['formats_autorises']) {
            <mat-error>{{ erreurs()['formats_autorises'] }}</mat-error>
          }
        </mat-form-field>
        <mat-form-field appearance="outline">
          <mat-label>{{ 'types_document.confidentialite_defaut' | t }}</mat-label>
          <mat-select formControlName="confidentialite_defaut">
            @for (n of [0, 1, 2, 3]; track n) {
              <mat-option [value]="n">{{ cleNiveau(n) | t }}</mat-option>
            }
          </mat-select>
        </mat-form-field>
        <mat-slide-toggle formControlName="actif">{{ 'champ.actif' | t }}</mat-slide-toggle>
      </form>

      <div class="ligne titre-metadonnees">
        <h3>{{ 'documents.metadonnees' | t }}</h3>
        <span class="espace"></span>
        <button mat-stroked-button type="button" (click)="ajouter()">
          <mat-icon>add</mat-icon>{{ 'types_document.ajouter_metadonnee' | t }}
        </button>
      </div>
      @if (erreursMetadonnees()) {
        <p class="erreur" role="alert">{{ erreursMetadonnees() }}</p>
      }
      @for (groupe of definitions.controls; track groupe; let i = $index) {
        <fieldset class="definition" [formGroup]="groupe" animate.enter="entree-montee">
          <legend class="visuellement-cache">{{ 'documents.metadonnees' | t }} {{ i + 1 }}</legend>
          <mat-form-field appearance="outline">
            <mat-label>{{ 'organisation.code' | t }}</mat-label>
            <input matInput formControlName="code" dir="ltr" [readonly]="existante(i)" />
          </mat-form-field>
          <mat-form-field appearance="outline">
            <mat-label>{{ 'champ.libelle_fr' | t }}</mat-label>
            <input matInput formControlName="libelle_fr" dir="ltr" />
          </mat-form-field>
          <mat-form-field appearance="outline">
            <mat-label>{{ 'champ.libelle_ar' | t }}</mat-label>
            <input matInput formControlName="libelle_ar" dir="rtl" lang="ar" />
          </mat-form-field>
          <mat-form-field appearance="outline">
            <mat-label>{{ 'types_document.nature' | t }}</mat-label>
            <mat-select formControlName="nature">
              @for (n of natures; track n) {
                <mat-option [value]="n">{{ cleNature(n) | t }}</mat-option>
              }
            </mat-select>
          </mat-form-field>
          @if (groupe.controls.nature.value === 'liste') {
            <mat-form-field appearance="outline" class="large">
              <mat-label>{{ 'types_document.valeurs' | t }}</mat-label>
              <input matInput formControlName="valeurs" />
              <mat-hint>{{ 'documents.mots_cles_virgules' | t }}</mat-hint>
            </mat-form-field>
          }
          <span class="ligne options">
            <mat-checkbox formControlName="obligatoire">{{ 'types_document.obligatoire' | t }}</mat-checkbox>
            <mat-checkbox formControlName="actif">{{ 'champ.actif' | t }}</mat-checkbox>
            <span class="espace"></span>
            @if (!existante(i)) {
              <button mat-icon-button type="button" (click)="retirer(i)" [attr.aria-label]="'action.retirer' | t">
                <mat-icon>delete</mat-icon>
              </button>
            }
          </span>
        </fieldset>
      } @empty {
        <p class="texte-attenue">{{ 'types_document.aucune_metadonnee' | t }}</p>
      }
    </mat-dialog-content>
    <mat-dialog-actions align="end">
      <button mat-button mat-dialog-close>{{ 'action.annuler' | t }}</button>
      <button mat-flat-button [disabled]="envoi() || formulaire.invalid || definitions.invalid" (click)="enregistrer()">
        {{ 'action.enregistrer' | t }}
      </button>
    </mat-dialog-actions>
  `,
  styles: `
    .titre-metadonnees {
      margin: 16px 0 8px;
      h3 {
        margin: 0;
        font-size: 15px;
      }
    }
    .definition {
      display: grid;
      gap: 0 12px;
      grid-template-columns: repeat(auto-fit, minmax(min(100%, 170px), 1fr));
      margin: 0 0 12px;
      padding: 12px 12px 0;
      border: 1px solid var(--ged-bordure);
      border-radius: 12px;
    }
    .large,
    .options {
      grid-column: 1 / -1;
    }
    .options {
      padding-bottom: 8px;
    }
  `,
})
export class DialogueTypeDocument extends DialogueSaisie<TypeDocument> {
  protected readonly donnees = inject<DonneesTypeDocument>(MAT_DIALOG_DATA);
  protected readonly reference = inject(MatDialogRef<DialogueTypeDocument, TypeDocument>);
  private readonly api = inject(ApiService);
  private readonly fb = inject(NonNullableFormBuilder);
  protected readonly natures = NATURES;
  protected readonly erreursMetadonnees = signal('');
  private readonly codesExistants = new Set(this.donnees.type?.metadonnees.map((d) => d.code) ?? []);

  protected readonly formulaire = this.fb.group({
    code: [this.donnees.type?.code ?? '', Validators.required],
    libelle_fr: [this.donnees.type?.libelle_fr ?? '', Validators.required],
    libelle_ar: [this.donnees.type?.libelle_ar ?? ''],
    categorie: [this.donnees.type?.categorie ?? ''],
    formats_autorises: [this.donnees.type?.formats_autorises ?? ([] as string[])],
    confidentialite_defaut: [this.donnees.type?.confidentialite_defaut ?? 0],
    actif: [this.donnees.type?.actif ?? true],
  });
  protected readonly definitions = new FormArray(
    (this.donnees.type?.metadonnees ?? []).map((d) => this.groupeDefinition(d)),
  );

  private groupeDefinition(d?: DefinitionMetadonnee) {
    return this.fb.group({
      code: [d?.code ?? '', [Validators.required, Validators.pattern(/^[-a-zA-Z0-9_]+$/)]],
      libelle_fr: [d?.libelle_fr ?? '', Validators.required],
      libelle_ar: [d?.libelle_ar ?? ''],
      nature: [d?.nature ?? ('texte' as NatureMetadonnee)],
      valeurs: [d?.valeurs_liste.join(', ') ?? ''],
      obligatoire: [d?.obligatoire ?? false],
      actif: [d?.actif ?? true],
    });
  }

  protected existante(index: number): boolean {
    return this.codesExistants.has(this.definitions.at(index).controls.code.value);
  }

  protected cleNiveau(niveau: number) {
    return `niveau.${niveau}` as 'niveau.0';
  }

  protected cleNature(nature: NatureMetadonnee) {
    return `nature.${nature}` as 'nature.texte';
  }

  protected ajouter(): void {
    this.definitions.push(this.groupeDefinition());
  }

  /** Seules les métadonnées pas encore enregistrées peuvent être retirées ; les autres se désactivent. */
  protected retirer(index: number): void {
    this.definitions.removeAt(index);
  }

  protected enregistrer(): void {
    const metadonnees = this.definitions.controls.map((groupe, ordre) => {
      const v = groupe.getRawValue();
      return {
        code: v.code,
        libelle_fr: v.libelle_fr,
        libelle_ar: v.libelle_ar,
        nature: v.nature,
        obligatoire: v.obligatoire,
        actif: v.actif,
        ordre,
        valeurs_liste:
          v.nature === 'liste'
            ? v.valeurs
                .split(',')
                .map((x) => x.trim())
                .filter(Boolean)
            : [],
      };
    });
    // Une métadonnée retirée de la liste reste en base, désactivée (des documents peuvent porter sa valeur).
    for (const code of this.codesExistants) {
      if (!metadonnees.some((m) => m.code === code)) {
        const ancienne = this.donnees.type!.metadonnees.find((d) => d.code === code)!;
        metadonnees.push({ ...ancienne, actif: false, ordre: metadonnees.length });
      }
    }
    this.erreursMetadonnees.set('');
    void this.soumettre(
      this.api.enregistrerTypeDocument({ ...this.formulaire.getRawValue(), metadonnees }, this.donnees.type?.uuid),
    ).then(() => {
      const erreurs = Object.entries(this.erreurs()).filter(([cle]) => cle.startsWith('metadonnees'));
      this.erreursMetadonnees.set(erreurs.map(([, message]) => message).join(' '));
    });
  }
}
