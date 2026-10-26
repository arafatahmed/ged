import { ChangeDetectionStrategy, Component, OnInit, inject, signal } from '@angular/core';
import { takeUntilDestroyed, toObservable } from '@angular/core/rxjs-interop';
import { FormsModule } from '@angular/forms';
import { MatButtonModule } from '@angular/material/button';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatIconModule } from '@angular/material/icon';
import { MatInputModule } from '@angular/material/input';
import { MatPaginatorModule, PageEvent } from '@angular/material/paginator';
import { MatProgressBarModule } from '@angular/material/progress-bar';
import { MatSelectModule } from '@angular/material/select';
import { MatTableModule } from '@angular/material/table';
import { MatTooltipModule } from '@angular/material/tooltip';
import { Router, RouterLink } from '@angular/router';
import { debounceTime, distinctUntilChanged, firstValueFrom, skip } from 'rxjs';

import { ApiService } from '../../core/api.service';
import { DocumentResume, OptionsDocuments, Page } from '../../core/modeles';
import { NotificationService } from '../../core/notification.service';
import { BilinguePipe, DateLocalePipe, TraduirePipe } from '../../core/pipes';
import { SessionService } from '../../core/session.service';
import { EntetePage } from '../../partage/entete-page';
import { EtatVide } from '../../partage/etats';
import { EtatFichier, PastilleConfidentialite } from './pastilles';

/** Documents visibles : recherche, filtres, tri et pagination côté serveur. */
@Component({
  selector: 'ged-documents',
  imports: [
    FormsModule,
    RouterLink,
    MatTableModule,
    MatPaginatorModule,
    MatFormFieldModule,
    MatInputModule,
    MatSelectModule,
    MatButtonModule,
    MatIconModule,
    MatProgressBarModule,
    MatTooltipModule,
    TraduirePipe,
    BilinguePipe,
    DateLocalePipe,
    EntetePage,
    EtatVide,
    PastilleConfidentialite,
    EtatFichier,
  ],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './documents.html',
  styleUrl: './documents.scss',
})
export class Documents implements OnInit {
  private readonly api = inject(ApiService);
  private readonly router = inject(Router);
  private readonly notifications = inject(NotificationService);
  protected readonly session = inject(SessionService);

  protected readonly page = signal<Page<DocumentResume> | null>(null);
  protected readonly options = signal<OptionsDocuments | null>(null);
  protected readonly chargement = signal(false);
  protected readonly recherche = signal('');
  protected readonly type = signal('');
  protected readonly statut = signal('');
  protected readonly tri = signal('');
  protected readonly colonnes = ['titre', 'type', 'unite', 'confidentialite', 'fichier', 'date'];

  constructor() {
    toObservable(this.recherche)
      .pipe(skip(1), debounceTime(300), distinctUntilChanged(), takeUntilDestroyed())
      .subscribe(() => this.recharger(1));
  }

  async ngOnInit(): Promise<void> {
    void firstValueFrom(this.api.optionsDocuments()).then((options) => this.options.set(options));
    await this.recharger(1);
  }

  protected async recharger(numero = 1): Promise<void> {
    this.chargement.set(true);
    try {
      this.page.set(
        await firstValueFrom(
          this.api.documents({
            q: this.recherche(),
            type: this.type(),
            statut: this.statut(),
            tri: this.tri(),
            page: numero,
          }),
        ),
      );
    } catch (erreur) {
      this.notifications.erreur(erreur);
    } finally {
      this.chargement.set(false);
    }
  }

  protected filtrer(cle: 'type' | 'statut' | 'tri', valeur: string): void {
    this[cle].set(valeur ?? '');
    void this.recharger(1);
  }

  protected changerPage(evenement: PageEvent): void {
    void this.recharger(evenement.pageIndex + 1);
  }

  protected ouvrir(document: DocumentResume): void {
    void this.router.navigate(['/documents', document.uuid]);
  }
}
