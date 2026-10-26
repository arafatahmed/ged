import { BreakpointObserver } from '@angular/cdk/layout';
import { BidiModule } from '@angular/cdk/bidi';
import { ChangeDetectionStrategy, Component, computed, inject } from '@angular/core';
import { toSignal } from '@angular/core/rxjs-interop';
import { MatButtonModule } from '@angular/material/button';
import { MatButtonToggleModule } from '@angular/material/button-toggle';
import { MatDividerModule } from '@angular/material/divider';
import { MatIconModule } from '@angular/material/icon';
import { MatListModule } from '@angular/material/list';
import { MatMenuModule } from '@angular/material/menu';
import { MatSidenavModule } from '@angular/material/sidenav';
import { MatToolbarModule } from '@angular/material/toolbar';
import { MatTooltipModule } from '@angular/material/tooltip';
import { Router, RouterLink, RouterLinkActive, RouterOutlet } from '@angular/router';
import { map } from 'rxjs';

import { Langue } from '../core/modeles';
import { BilinguePipe, TraduirePipe } from '../core/pipes';
import { SessionService } from '../core/session.service';
import { TraductionService } from '../core/traduction.service';
import { Cle } from '../i18n/fr';

interface EntreeMenu {
  lien: string;
  icone: string;
  libelle: Cle;
  visible: () => boolean;
}

/** Coque de l'application connectée : barre supérieure, menu latéral, contenu animé. */
@Component({
  selector: 'ged-coque',
  imports: [
    BidiModule,
    RouterOutlet,
    RouterLink,
    RouterLinkActive,
    MatSidenavModule,
    MatToolbarModule,
    MatListModule,
    MatIconModule,
    MatButtonModule,
    MatMenuModule,
    MatDividerModule,
    MatTooltipModule,
    MatButtonToggleModule,
    TraduirePipe,
    BilinguePipe,
  ],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './coque.html',
  styleUrl: './coque.scss',
})
export class Coque {
  protected readonly session = inject(SessionService);
  protected readonly traduction = inject(TraductionService);
  private readonly router = inject(Router);

  protected readonly mobile = toSignal(
    inject(BreakpointObserver)
      .observe('(max-width: 959px)')
      .pipe(map((etat) => etat.matches)),
    { initialValue: false },
  );

  protected readonly initiales = computed(() => {
    const utilisateur = this.session.utilisateur();
    return utilisateur ? `${utilisateur.prenom.charAt(0)}${utilisateur.nom.charAt(0)}`.toUpperCase() : '';
  });

  private readonly droits = this.session.droits;
  protected readonly principal: EntreeMenu[] = [
    { lien: '/', icone: 'space_dashboard', libelle: 'menu.accueil', visible: () => true },
    {
      lien: '/documents',
      icone: 'folder_open',
      libelle: 'menu.documents',
      visible: () => this.session.documents().consulter,
    },
    { lien: '/compte', icone: 'manage_accounts', libelle: 'menu.mon_compte', visible: () => true },
  ];
  protected readonly administration: EntreeMenu[] = [
    {
      lien: '/administration/organisation',
      icone: 'account_tree',
      libelle: 'menu.organisation',
      visible: () => this.droits().organisation,
    },
    {
      lien: '/administration/postes',
      icone: 'badge',
      libelle: 'menu.postes',
      visible: () => this.droits().organisation,
    },
    {
      lien: '/administration/utilisateurs',
      icone: 'group',
      libelle: 'menu.utilisateurs',
      visible: () => this.droits().utilisateurs,
    },
    {
      lien: '/administration/roles',
      icone: 'shield_person',
      libelle: 'menu.roles',
      visible: () => this.droits().roles,
    },
    {
      lien: '/administration/types-document',
      icone: 'category',
      libelle: 'menu.types_document',
      visible: () => this.droits().types_document,
    },
    {
      lien: '/administration/connexions',
      icone: 'history',
      libelle: 'menu.connexions',
      visible: () => this.droits().connexions,
    },
  ];

  protected changerLangue(langue: Langue): void {
    this.traduction.choisir(langue);
  }

  protected async deconnecter(): Promise<void> {
    await this.session.deconnecter();
    await this.router.navigateByUrl('/connexion');
  }
}
