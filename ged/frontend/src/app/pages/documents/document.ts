import { ComponentType } from '@angular/cdk/portal';
import { ChangeDetectionStrategy, Component, DestroyRef, OnInit, computed, inject, input, signal } from '@angular/core';
import { MatButtonModule } from '@angular/material/button';
import { MatChipsModule } from '@angular/material/chips';
import { MatIconModule } from '@angular/material/icon';
import { MatTooltipModule } from '@angular/material/tooltip';
import { RouterLink } from '@angular/router';
import { firstValueFrom } from 'rxjs';

import { ApiService } from '../../core/api.service';
import { DocumentDetail, FichierDocument, OptionsDocuments } from '../../core/modeles';
import { NotificationService } from '../../core/notification.service';
import { BilinguePipe, DateLocalePipe, TailleFichierPipe, TraduirePipe } from '../../core/pipes';
import { TraductionService } from '../../core/traduction.service';
import { Cle } from '../../i18n/fr';
import { DialoguesService } from '../../partage/dialogues.service';
import { EntetePage } from '../../partage/entete-page';
import { Squelette } from '../../partage/etats';
import { DialogueFichier, DialogueModifierDocument, DialogueRelation } from './dialogues-document';
import { EtatFichier, PastilleConfidentialite } from './pastilles';

const INTERVALLE_SUIVI_MS = 3000;
const DUREE_SUIVI_MS = 5 * 60 * 1000;

/** Fiche d'un document : description, fichiers et versions, relations, doublons. */
@Component({
  selector: 'ged-document',
  imports: [
    RouterLink,
    MatButtonModule,
    MatChipsModule,
    MatIconModule,
    MatTooltipModule,
    TraduirePipe,
    BilinguePipe,
    DateLocalePipe,
    TailleFichierPipe,
    EntetePage,
    Squelette,
    PastilleConfidentialite,
    EtatFichier,
  ],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './document.html',
  styleUrl: './document.scss',
})
export class FicheDocument implements OnInit {
  readonly uuid = input.required<string>();

  private readonly api = inject(ApiService);
  private readonly dialogues = inject(DialoguesService);
  private readonly notifications = inject(NotificationService);
  private readonly traduction = inject(TraductionService);

  protected readonly document = signal<DocumentDetail | null>(null);
  protected readonly options = signal<OptionsDocuments | null>(null);
  protected readonly introuvable = signal(false);
  /** Image affichée en aperçu dans la page (les PDF s'ouvrent dans un nouvel onglet). */
  protected readonly apercu = signal<FichierDocument | null>(null);

  protected readonly versionCourante = computed(() => this.document()?.versions.find((v) => v.courante) ?? null);
  protected readonly anciennes = computed(() => this.document()?.versions.filter((v) => !v.courante) ?? []);
  protected readonly enAnalyse = computed(
    () => this.document()?.versions.some((v) => v.fichiers.some((f) => f.etat === 'en_attente')) ?? false,
  );
  protected readonly metadonnees = computed(() => {
    const document = this.document();
    if (!document) return [];
    return document.type.metadonnees
      .filter((d) => document.metadonnees[d.code] !== undefined)
      .map((d) => ({ definition: d, valeur: document.metadonnees[d.code] }));
  });

  private suiviDepuis = 0;
  private minuterie: ReturnType<typeof setTimeout> | undefined;

  constructor() {
    inject(DestroyRef).onDestroy(() => clearTimeout(this.minuterie));
  }

  async ngOnInit(): Promise<void> {
    void firstValueFrom(this.api.optionsDocuments()).then((options) => this.options.set(options));
    await this.charger();
  }

  private async charger(): Promise<void> {
    try {
      this.appliquer(await firstValueFrom(this.api.document(this.uuid())));
    } catch (erreur) {
      if ((erreur as { status?: number }).status === 404) this.introuvable.set(true);
      else this.notifications.erreur(erreur);
    }
  }

  /** Tant qu'un fichier est en cours d'analyse, la fiche se recharge à intervalle régulier. */
  private appliquer(document: DocumentDetail): void {
    this.document.set(document);
    clearTimeout(this.minuterie);
    if (!this.enAnalyse()) {
      this.suiviDepuis = 0;
      return;
    }
    this.suiviDepuis ||= Date.now();
    if (Date.now() - this.suiviDepuis < DUREE_SUIVI_MS) {
      this.minuterie = setTimeout(() => void this.charger(), INTERVALLE_SUIVI_MS);
    }
  }

  protected url(fichier: FichierDocument, mode: 'apercu' | 'telecharger'): string {
    return this.api.urlFichier(this.uuid(), fichier.uuid, mode);
  }

  protected afficher(fichier: FichierDocument): void {
    if (fichier.format === 'pdf') {
      window.open(this.url(fichier, 'apercu'), '_blank', 'noopener');
    } else {
      this.apercu.set(this.apercu()?.uuid === fichier.uuid ? null : fichier);
    }
  }

  protected cleRelation(nature: string, sens: 'sortante' | 'entrante'): Cle {
    return `relation.${nature}${sens === 'entrante' ? '_inverse' : ''}` as Cle;
  }

  protected cleStatut(statut: string): Cle {
    return `statut.${statut}` as Cle;
  }

  protected async modifier(): Promise<void> {
    await this.dialoguer(DialogueModifierDocument, {}, 'documents.modifie');
  }

  protected async ajouterFichier(nature: 'versions' | 'pieces-jointes'): Promise<void> {
    await this.dialoguer(
      DialogueFichier,
      { nature },
      nature === 'versions' ? 'documents.version_ajoutee' : 'documents.piece_ajoutee',
    );
  }

  protected async relier(): Promise<void> {
    await this.dialoguer(DialogueRelation, {}, 'documents.relie');
  }

  protected async delier(id: number): Promise<void> {
    const confirme = await this.dialogues.confirmer({
      titre: this.traduction.t('documents.delier'),
      message: this.traduction.t('documents.delier_confirmation'),
      confirmer: this.traduction.t('documents.delier'),
      danger: true,
    });
    if (!confirme) return;
    try {
      this.appliquer(await firstValueFrom(this.api.supprimerRelation(this.uuid(), id)));
    } catch (erreur) {
      this.notifications.erreur(erreur);
    }
  }

  private async dialoguer<C>(composant: ComponentType<C>, supplement: object, succes: Cle): Promise<void> {
    const document = this.document();
    const options = this.options();
    if (!document || !options) return;
    const resultat = await this.dialogues.ouvrir<C, object, DocumentDetail>(
      composant,
      { document, options, ...supplement },
      { width: '720px' },
    );
    if (resultat) {
      this.notifications.succes(succes);
      this.appliquer(resultat);
    }
  }
}
