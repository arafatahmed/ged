import { ChangeDetectionStrategy, Component, OnInit, inject, signal } from '@angular/core';
import { toObservable, takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { FormsModule } from '@angular/forms';
import { MatButtonModule } from '@angular/material/button';
import { MatChipsModule } from '@angular/material/chips';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatIconModule } from '@angular/material/icon';
import { MatInputModule } from '@angular/material/input';
import { MatPaginatorModule, PageEvent } from '@angular/material/paginator';
import { MatProgressBarModule } from '@angular/material/progress-bar';
import { MatSelectModule } from '@angular/material/select';
import { MatTableModule } from '@angular/material/table';
import { MatTooltipModule } from '@angular/material/tooltip';
import { Router } from '@angular/router';
import { debounceTime, distinctUntilChanged, firstValueFrom, skip } from 'rxjs';

import { ApiService } from '../../core/api.service';
import { OptionsUtilisateurs, Page, UtilisateurResume } from '../../core/modeles';
import { NotificationService } from '../../core/notification.service';
import { DateLocalePipe, TraduirePipe } from '../../core/pipes';
import { TraductionService } from '../../core/traduction.service';
import { DialoguesService } from '../../partage/dialogues.service';
import { EntetePage } from '../../partage/entete-page';
import { EtatVide } from '../../partage/etats';
import { DialogueUtilisateur } from './dialogue-utilisateur';

/** Comptes du périmètre : recherche, filtres, tri, pagination côté serveur. */
@Component({
  selector: 'ged-utilisateurs',
  imports: [
    FormsModule,
    MatTableModule,
    MatPaginatorModule,
    MatFormFieldModule,
    MatInputModule,
    MatSelectModule,
    MatChipsModule,
    MatButtonModule,
    MatIconModule,
    MatProgressBarModule,
    MatTooltipModule,
    TraduirePipe,
    DateLocalePipe,
    EntetePage,
    EtatVide,
  ],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './utilisateurs.html',
  styleUrl: './utilisateurs.scss',
})
export class Utilisateurs implements OnInit {
  private readonly api = inject(ApiService);
  private readonly router = inject(Router);
  private readonly dialogues = inject(DialoguesService);
  private readonly notifications = inject(NotificationService);
  private readonly traduction = inject(TraductionService);

  protected readonly page = signal<Page<UtilisateurResume> | null>(null);
  protected readonly options = signal<OptionsUtilisateurs | null>(null);
  protected readonly chargement = signal(false);
  protected readonly recherche = signal('');
  protected readonly statut = signal('');
  protected readonly unite = signal('');
  protected readonly tri = signal('nom');
  protected readonly numero = signal(1);
  protected readonly colonnes = ['nom', 'identifiant', 'statut', 'mfa', 'connexion'];
  protected readonly urlRevue = this.api.urlRevueHabilitations;

  constructor() {
    toObservable(this.recherche)
      .pipe(skip(1), debounceTime(300), distinctUntilChanged(), takeUntilDestroyed())
      .subscribe(() => this.recharger(1));
  }

  async ngOnInit(): Promise<void> {
    void firstValueFrom(this.api.optionsUtilisateurs()).then((options) => this.options.set(options));
    await this.recharger(1);
  }

  protected async recharger(numero = this.numero()): Promise<void> {
    this.numero.set(numero);
    this.chargement.set(true);
    try {
      this.page.set(
        await firstValueFrom(
          this.api.utilisateurs({
            q: this.recherche(),
            statut: this.statut(),
            unite: this.unite(),
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

  protected filtrer(cle: 'statut' | 'unite' | 'tri', valeur: string): void {
    this[cle].set(valeur ?? '');
    void this.recharger(1);
  }

  protected changerPage(evenement: PageEvent): void {
    void this.recharger(evenement.pageIndex + 1);
  }

  protected ouvrir(compte: UtilisateurResume): void {
    void this.router.navigate(['/administration/utilisateurs', compte.uuid]);
  }

  protected async creer(): Promise<void> {
    const resultat = await this.dialogues.ouvrir<
      DialogueUtilisateur,
      null,
      { compte: UtilisateurResume; motDePasse: string }
    >(DialogueUtilisateur, null, { width: '760px' });
    if (!resultat) return;
    await this.dialogues.secret({
      titre: this.traduction.t('utilisateurs.compte_cree'),
      message: this.traduction.t('utilisateurs.compte_cree_message', { identifiant: resultat.compte.identifiant }),
      valeurs: [resultat.motDePasse],
    });
    await this.router.navigate(['/administration/utilisateurs', resultat.compte.uuid]);
  }
}
