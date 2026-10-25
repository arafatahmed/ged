import { ChangeDetectionStrategy, Component, OnInit, inject, signal } from '@angular/core';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatIconModule } from '@angular/material/icon';
import { MatPaginatorModule, PageEvent } from '@angular/material/paginator';
import { MatProgressBarModule } from '@angular/material/progress-bar';
import { MatSelectModule } from '@angular/material/select';
import { MatTableModule } from '@angular/material/table';
import { firstValueFrom } from 'rxjs';

import { ApiService } from '../../core/api.service';
import { EvenementConnexion, Page } from '../../core/modeles';
import { DateLocalePipe, TraduirePipe } from '../../core/pipes';
import { TraductionService } from '../../core/traduction.service';
import { Cle } from '../../i18n/fr';
import { EntetePage } from '../../partage/entete-page';
import { EtatVide } from '../../partage/etats';

const LIBELLES: Record<string, Cle> = {
  'connexion.reussie': 'connexions.reussie',
  'connexion.echec': 'connexions.echec',
  'connexion.mfa_echec': 'connexions.mfa_echec',
  'connexion.refus_verrouille': 'connexions.refus_verrouille',
  'connexion.ip_bloquee': 'connexions.ip_bloquee',
  'compte.verrouillage': 'connexions.verrouillage',
  deconnexion: 'connexions.deconnexion',
  'deconnexion.inactivite': 'connexions.inactivite',
};
const ICONES: Record<string, string> = {
  'connexion.reussie': 'login',
  'connexion.echec': 'error',
  'connexion.mfa_echec': 'phonelink_erase',
  'connexion.refus_verrouille': 'lock',
  'connexion.ip_bloquee': 'block',
  'compte.verrouillage': 'lock_person',
  deconnexion: 'logout',
  'deconnexion.inactivite': 'schedule',
};

/** Journal des connexions (extrait du journal d'audit). */
@Component({
  selector: 'ged-connexions',
  imports: [
    MatTableModule,
    MatPaginatorModule,
    MatSelectModule,
    MatFormFieldModule,
    MatIconModule,
    MatProgressBarModule,
    TraduirePipe,
    DateLocalePipe,
    EntetePage,
    EtatVide,
  ],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <ged-entete-page [titre]="'connexions.titre' | t" [sousTitre]="'connexions.sous_titre' | t" icone="history" />
    <mat-form-field appearance="outline" subscriptSizing="dynamic" class="filtre">
      <mat-label>{{ 'connexions.evenement' | t }}</mat-label>
      <mat-select [value]="action()" (selectionChange)="filtrer($event.value)">
        <mat-option value="">{{ 'utilisateurs.tous' | t }}</mat-option>
        @for (a of page()?.actions ?? []; track a) {
          <mat-option [value]="a">{{ libelle(a) }}</mat-option>
        }
      </mat-select>
    </mat-form-field>
    <div class="tableau-conteneur resultats">
      @if (chargement()) {
        <mat-progress-bar mode="indeterminate" class="progression" />
      }
      @if (page(); as p) {
        @if (p.resultats.length) {
          <table mat-table [dataSource]="p.resultats">
            <ng-container matColumnDef="date">
              <th mat-header-cell *matHeaderCellDef>{{ 'connexions.date' | t }}</th>
              <td mat-cell *matCellDef="let e">{{ e.horodatage | dateLocale: 'dateHeure' }}</td>
            </ng-container>
            <ng-container matColumnDef="evenement">
              <th mat-header-cell *matHeaderCellDef>{{ 'connexions.evenement' | t }}</th>
              <td mat-cell *matCellDef="let e">
                <span class="evenement" [class]="'resultat-' + e.resultat"
                  ><mat-icon>{{ icone(e.action) }}</mat-icon
                  >{{ libelle(e.action) }}</span
                >
              </td>
            </ng-container>
            <ng-container matColumnDef="compte">
              <th mat-header-cell *matHeaderCellDef>{{ 'connexions.compte' | t }}</th>
              <td mat-cell *matCellDef="let e" class="ltr">{{ e.compte || '—' }}</td>
            </ng-container>
            <ng-container matColumnDef="ip">
              <th mat-header-cell *matHeaderCellDef>{{ 'connexions.ip' | t }}</th>
              <td mat-cell *matCellDef="let e" class="ltr texte-attenue">{{ e.adresse_ip || '—' }}</td>
            </ng-container>
            <tr mat-header-row *matHeaderRowDef="colonnes"></tr>
            <tr mat-row *matRowDef="let e; columns: colonnes; let i = index" animate.enter="entree-fondu"></tr>
          </table>
          <mat-paginator
            [length]="p.nombre"
            [pageSize]="25"
            [pageIndex]="p.page - 1"
            [hidePageSize]="true"
            (page)="changerPage($event)"
          />
        } @else {
          <ged-etat-vide icone="history" [message]="'connexions.aucun' | t" />
        }
      }
    </div>
  `,
  styles: `
    .filtre {
      width: min(320px, 100%);
      margin-bottom: 16px;
    }
    .resultats {
      position: relative;
      min-height: 120px;
    }
    .progression {
      position: absolute;
      inset-inline: 0;
      inset-block-start: 0;
    }
    .evenement {
      display: inline-flex;
      align-items: center;
      gap: 8px;
      font-weight: 500;
    }
    .evenement mat-icon {
      font-size: 20px;
      width: 20px;
      height: 20px;
    }
    .resultat-succes mat-icon {
      color: var(--ged-succes);
    }
    .resultat-refus mat-icon,
    .resultat-erreur mat-icon {
      color: var(--ged-alerte);
    }
  `,
})
export class Connexions implements OnInit {
  private readonly api = inject(ApiService);
  private readonly traduction = inject(TraductionService);
  protected readonly page = signal<(Page<EvenementConnexion> & { actions: string[] }) | null>(null);
  protected readonly action = signal('');
  protected readonly chargement = signal(false);
  protected readonly colonnes = ['date', 'evenement', 'compte', 'ip'];

  async ngOnInit(): Promise<void> {
    await this.charger(1);
  }

  protected libelle(action: string): string {
    return LIBELLES[action] ? this.traduction.t(LIBELLES[action]) : action;
  }
  protected icone(action: string): string {
    return ICONES[action] ?? 'info';
  }
  protected filtrer(action: string): void {
    this.action.set(action);
    void this.charger(1);
  }
  protected changerPage(evenement: PageEvent): void {
    void this.charger(evenement.pageIndex + 1);
  }

  private async charger(numero: number): Promise<void> {
    this.chargement.set(true);
    try {
      this.page.set(await firstValueFrom(this.api.connexions(numero, this.action())));
    } finally {
      this.chargement.set(false);
    }
  }
}
