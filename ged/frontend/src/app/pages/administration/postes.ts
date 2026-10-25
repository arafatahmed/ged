import { ChangeDetectionStrategy, Component, OnInit, computed, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { MatButtonModule } from '@angular/material/button';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatIconModule } from '@angular/material/icon';
import { MatInputModule } from '@angular/material/input';
import { MatTableModule } from '@angular/material/table';
import { firstValueFrom } from 'rxjs';

import { ApiService } from '../../core/api.service';
import { Poste, Unite } from '../../core/modeles';
import { NotificationService } from '../../core/notification.service';
import { BilinguePipe, TraduirePipe } from '../../core/pipes';
import { DialoguesService } from '../../partage/dialogues.service';
import { EntetePage } from '../../partage/entete-page';
import { EtatVide, Squelette } from '../../partage/etats';
import { DialoguePoste, DonneesPoste } from './dialogues-organisation';

/** Postes et hiérarchie (le poste supérieur sert à l'escalade). */
@Component({
  selector: 'ged-postes',
  imports: [
    FormsModule,
    MatTableModule,
    MatButtonModule,
    MatIconModule,
    MatFormFieldModule,
    MatInputModule,
    TraduirePipe,
    BilinguePipe,
    EntetePage,
    EtatVide,
    Squelette,
  ],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <ged-entete-page [titre]="'postes.titre' | t" [sousTitre]="'postes.sous_titre' | t" icone="badge">
      <button mat-flat-button (click)="editer(null)"><mat-icon>add</mat-icon>{{ 'postes.nouveau' | t }}</button>
    </ged-entete-page>
    <mat-form-field appearance="outline" subscriptSizing="dynamic" class="recherche">
      <mat-icon matPrefix>search</mat-icon>
      <mat-label>{{ 'action.rechercher' | t }}</mat-label>
      <input matInput [ngModel]="filtre()" (ngModelChange)="filtre.set($event)" />
    </mat-form-field>
    @if (postes() === null) {
      <div class="carte"><ged-squelette /></div>
    } @else if (!visibles().length) {
      <div class="carte"><ged-etat-vide icone="badge" [message]="'postes.aucun' | t" /></div>
    } @else {
      <div class="tableau-conteneur" animate.enter="entree-montee">
        <table mat-table [dataSource]="visibles()">
          <ng-container matColumnDef="intitule">
            <th mat-header-cell *matHeaderCellDef>{{ 'champ.intitule' | t }}</th>
            <td mat-cell *matCellDef="let p">
              <strong>{{ p.intitule_fr | bilingue: p.intitule_ar }}</strong>
            </td>
          </ng-container>
          <ng-container matColumnDef="unite">
            <th mat-header-cell *matHeaderCellDef>{{ 'champ.unite' | t }}</th>
            <td mat-cell *matCellDef="let p">{{ p.unite_libelle }}</td>
          </ng-container>
          <ng-container matColumnDef="superieur">
            <th mat-header-cell *matHeaderCellDef>{{ 'postes.superieur' | t }}</th>
            <td mat-cell *matCellDef="let p">{{ p.superieur_libelle ?? '—' }}</td>
          </ng-container>
          <ng-container matColumnDef="statut">
            <th mat-header-cell *matHeaderCellDef>{{ 'champ.statut' | t }}</th>
            <td mat-cell *matCellDef="let p">
              <span class="pastille" [class.succes]="p.actif" [class.alerte]="!p.actif">{{
                (p.actif ? 'champ.actif' : 'champ.inactif') | t
              }}</span>
            </td>
          </ng-container>
          <tr mat-header-row *matHeaderRowDef="colonnes"></tr>
          <tr mat-row *matRowDef="let p; columns: colonnes" class="ligne-cliquable" (click)="editer(p)"></tr>
        </table>
      </div>
    }
  `,
  styles: `
    .recherche {
      width: min(360px, 100%);
      margin-bottom: 16px;
    }
  `,
})
export class Postes implements OnInit {
  private readonly api = inject(ApiService);
  private readonly dialogues = inject(DialoguesService);
  private readonly notifications = inject(NotificationService);
  protected readonly postes = signal<Poste[] | null>(null);
  private readonly unites = signal<Unite[]>([]);
  protected readonly filtre = signal('');
  protected readonly colonnes = ['intitule', 'unite', 'superieur', 'statut'];
  protected readonly visibles = computed(() => {
    const terme = this.filtre().trim().toLowerCase();
    return (this.postes() ?? []).filter(
      (p) => !terme || `${p.intitule_fr} ${p.intitule_ar} ${p.unite_libelle}`.toLowerCase().includes(terme),
    );
  });

  async ngOnInit(): Promise<void> {
    const [postes, unites] = await Promise.all([firstValueFrom(this.api.postes()), firstValueFrom(this.api.unites())]);
    this.postes.set(postes);
    this.unites.set(unites.unites.filter((u) => u.actif));
  }

  protected async editer(poste: Poste | null): Promise<void> {
    const donnees: DonneesPoste = {
      poste,
      unites: this.unites(),
      postes: this.postes() ?? [],
      enregistrer: (corps, id) => this.api.enregistrerPoste(corps, id),
    };
    if (await this.dialogues.ouvrir(DialoguePoste, donnees, { width: '680px' })) {
      this.notifications.succes('postes.enregistre');
      this.postes.set(await firstValueFrom(this.api.postes()));
    }
  }
}
