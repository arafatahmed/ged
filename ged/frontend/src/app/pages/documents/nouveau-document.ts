import { ChangeDetectionStrategy, Component, OnInit, computed, inject, signal } from '@angular/core';
import { toSignal } from '@angular/core/rxjs-interop';
import { FormControl, FormRecord, NonNullableFormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { MatButtonModule } from '@angular/material/button';
import { MatChipInputEvent, MatChipsModule } from '@angular/material/chips';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatIconModule } from '@angular/material/icon';
import { MatInputModule } from '@angular/material/input';
import { MatProgressBarModule } from '@angular/material/progress-bar';
import { MatSelectModule } from '@angular/material/select';
import { Router, RouterLink } from '@angular/router';
import { firstValueFrom } from 'rxjs';

import { ApiService } from '../../core/api.service';
import { OptionsDocuments, TypeDocument } from '../../core/modeles';
import { NotificationService, erreursChamps, messageErreur } from '../../core/notification.service';
import { BilinguePipe, TraduirePipe } from '../../core/pipes';
import { DepotFichier } from '../../partage/depot-fichier';
import { EntetePage } from '../../partage/entete-page';
import { Squelette } from '../../partage/etats';
import { ChampMetadonnee, controleMetadonnee, valeursMetadonnees } from './champ-metadonnee';

/** Enregistrement d'un document : fichier à gauche, fiche descriptive à droite (parcours prioritaire 2). */
@Component({
  selector: 'ged-nouveau-document',
  imports: [
    ReactiveFormsModule,
    RouterLink,
    MatButtonModule,
    MatChipsModule,
    MatFormFieldModule,
    MatIconModule,
    MatInputModule,
    MatProgressBarModule,
    MatSelectModule,
    TraduirePipe,
    BilinguePipe,
    EntetePage,
    Squelette,
    DepotFichier,
    ChampMetadonnee,
  ],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './nouveau-document.html',
  styleUrl: './nouveau-document.scss',
})
export class NouveauDocument implements OnInit {
  private readonly api = inject(ApiService);
  private readonly router = inject(Router);
  private readonly notifications = inject(NotificationService);

  protected readonly options = signal<OptionsDocuments | null>(null);
  protected readonly fichier = signal<File | null>(null);
  protected readonly motsCles = signal<string[]>([]);
  protected readonly envoi = signal(false);
  protected readonly erreurs = signal<Record<string, string>>({});
  protected readonly erreurGenerale = signal('');

  protected readonly formulaire = inject(NonNullableFormBuilder).group({
    type: ['', Validators.required],
    unite_proprietaire: ['', Validators.required],
    titre: ['', [Validators.required, Validators.maxLength(500)]],
    objet: [''],
    date_document: [''],
    confidentialite: [0],
    commentaire: [''],
  });
  protected readonly metadonnees = new FormRecord<FormControl<string>>({});

  private readonly typeChoisi = toSignal(this.formulaire.controls.type.valueChanges, { initialValue: '' });
  protected readonly type = computed<TypeDocument | undefined>(() =>
    this.options()?.types.find((t) => t.uuid === this.typeChoisi()),
  );
  /** Extensions admises par le type choisi (toutes celles du catalogue si le type n'en restreint pas). */
  protected readonly extensions = computed(() => {
    const formats = this.options()?.formats ?? [];
    const admis = this.type()?.formats_autorises ?? [];
    return formats.filter((f) => !admis.length || admis.includes(f.code)).flatMap((f) => f.extensions ?? []);
  });

  async ngOnInit(): Promise<void> {
    try {
      const options = await firstValueFrom(this.api.optionsDocuments());
      this.options.set(options);
      if (options.unites.length === 1) this.formulaire.controls.unite_proprietaire.setValue(options.unites[0].uuid);
      if (options.types.length === 1) this.choisirType(options.types[0].uuid);
    } catch (erreur) {
      this.notifications.erreur(erreur);
    }
  }

  protected choisirType(uuid: string): void {
    this.formulaire.controls.type.setValue(uuid);
    const type = this.options()?.types.find((t) => t.uuid === uuid);
    for (const code of Object.keys(this.metadonnees.controls)) this.metadonnees.removeControl(code);
    for (const definition of type?.metadonnees ?? []) {
      this.metadonnees.addControl(definition.code, controleMetadonnee(definition));
    }
    if (type) this.formulaire.controls.confidentialite.setValue(type.confidentialite_defaut);
  }

  protected ajouterMotCle(evenement: MatChipInputEvent): void {
    const mot = evenement.value.trim();
    if (mot && !this.motsCles().some((m) => m.toLowerCase() === mot.toLowerCase())) {
      this.motsCles.update((mots) => [...mots, mot]);
    }
    evenement.chipInput.clear();
  }

  protected retirerMotCle(mot: string): void {
    this.motsCles.update((mots) => mots.filter((m) => m !== mot));
  }

  protected async enregistrer(): Promise<void> {
    if (this.formulaire.invalid || this.metadonnees.invalid) {
      this.formulaire.markAllAsTouched();
      this.metadonnees.markAllAsTouched();
      return;
    }
    const valeurs = this.formulaire.getRawValue();
    const donnees = new FormData();
    for (const [cle, valeur] of Object.entries(valeurs)) {
      if (valeur !== '' && valeur !== null) donnees.append(cle, String(valeur));
    }
    donnees.append('mots_cles', JSON.stringify(this.motsCles()));
    donnees.append('metadonnees', JSON.stringify(valeursMetadonnees(this.type()?.metadonnees ?? [], this.metadonnees)));
    const fichier = this.fichier();
    if (fichier) donnees.append('fichier', fichier, fichier.name);

    this.envoi.set(true);
    this.erreurs.set({});
    this.erreurGenerale.set('');
    try {
      const document = await firstValueFrom(this.api.creerDocument(donnees));
      this.notifications.succes('documents.enregistre');
      await this.router.navigate(['/documents', document.uuid]);
    } catch (erreur) {
      const champs = erreursChamps(erreur);
      this.erreurs.set(champs);
      this.erreurGenerale.set(
        champs['__all__'] ?? champs['fichier'] ?? (Object.keys(champs).length ? '' : messageErreur(erreur)),
      );
    } finally {
      this.envoi.set(false);
    }
  }
}
