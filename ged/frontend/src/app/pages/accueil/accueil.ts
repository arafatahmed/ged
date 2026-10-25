import { ChangeDetectionStrategy, Component, OnInit, computed, inject, signal } from '@angular/core';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';
import { RouterLink } from '@angular/router';
import { firstValueFrom } from 'rxjs';

import { ApiService } from '../../core/api.service';
import { BilinguePipe, TraduirePipe } from '../../core/pipes';
import { SessionService } from '../../core/session.service';
import { Cle } from '../../i18n/fr';
import { CarteIndicateur } from '../../partage/carte-indicateur';
import { Squelette } from '../../partage/etats';

interface Indicateur {
  cle: string;
  libelle: Cle;
  icone: string;
  teinte: 'primaire' | 'succes' | 'alerte' | 'avertissement';
}

const INDICATEURS: Indicateur[] = [
  { cle: 'comptes_actifs', libelle: 'accueil.comptes_actifs', icone: 'group', teinte: 'primaire' },
  { cle: 'unites', libelle: 'accueil.unites', icone: 'account_tree', teinte: 'succes' },
  { cle: 'roles', libelle: 'accueil.roles', icone: 'shield_person', teinte: 'primaire' },
  { cle: 'comptes_sans_mfa', libelle: 'accueil.sans_mfa', icone: 'gpp_maybe', teinte: 'avertissement' },
  { cle: 'comptes_verrouilles', libelle: 'accueil.verrouilles', icone: 'lock_person', teinte: 'alerte' },
  { cle: 'echecs_24h', libelle: 'accueil.echecs', icone: 'report', teinte: 'alerte' },
];

/** Tableau de bord : accueil personnalisé, indicateurs du périmètre, raccourcis. */
@Component({
  selector: 'ged-accueil',
  imports: [RouterLink, MatIconModule, MatButtonModule, TraduirePipe, BilinguePipe, CarteIndicateur, Squelette],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <section class="banniere" animate.enter="entree-fondu">
      <div class="banniere-texte">
        <p class="salutation">{{ salutation() | t }},</p>
        <h1>{{ session.utilisateur()?.prenom }} {{ session.utilisateur()?.nom }}</h1>
        <p>{{ session.institution()?.nom_fr | bilingue: session.institution()?.nom_ar }}</p>
      </div>
      <div class="banniere-deco" aria-hidden="true"><mat-icon>folder_managed</mat-icon></div>
    </section>

    @if (indicateurs(); as liste) {
      @if (liste.length) {
        <h2 class="titre-section">{{ 'accueil.indicateurs' | t }}</h2>
        <div class="indicateurs">
          @for (i of liste; track i.cle) {
            <ged-carte-indicateur
              animate.enter="entree-montee"
              [style.--rang]="$index"
              [valeur]="valeurs()[i.cle]"
              [libelle]="i.libelle | t"
              [icone]="i.icone"
              [teinte]="i.teinte"
            />
          }
        </div>
      }
    } @else {
      <div class="carte"><ged-squelette [lignes]="3" /></div>
    }

    <h2 class="titre-section">{{ 'accueil.raccourcis' | t }}</h2>
    <div class="raccourcis">
      @for (r of raccourcis(); track r.lien) {
        <a
          class="carte carte-interactive raccourci"
          [routerLink]="r.lien"
          animate.enter="entree-montee"
          [style.--rang]="$index"
        >
          <span class="icone"
            ><mat-icon>{{ r.icone }}</mat-icon></span
          >
          <span
            ><strong>{{ r.titre | t }}</strong
            ><span class="texte-attenue">{{ r.description | t }}</span></span
          >
          <mat-icon class="fleche icone-directionnelle">arrow_forward</mat-icon>
        </a>
      }
    </div>

    <section class="carte bientot" animate.enter="entree-montee" [style.--rang]="2">
      <mat-icon>rocket_launch</mat-icon>
      <div>
        <strong>{{ 'accueil.bientot_titre' | t }}</strong>
        <p class="texte-attenue">{{ 'accueil.bientot_texte' | t }}</p>
      </div>
    </section>
  `,
  styles: `
    .banniere {
      position: relative;
      overflow: hidden;
      display: flex;
      align-items: center;
      justify-content: space-between;
      padding: clamp(24px, 4vw, 40px);
      border-radius: 22px;
      color: white;
      margin-bottom: 28px;
      background:
        radial-gradient(circle at 85% 20%, color-mix(in srgb, var(--ged-secondaire) 70%, transparent), transparent 45%),
        linear-gradient(120deg, var(--ged-primaire), color-mix(in srgb, var(--ged-primaire) 60%, #0b1f33));
      box-shadow: 0 18px 40px -18px color-mix(in srgb, var(--ged-primaire) 70%, transparent);
    }
    .salutation {
      margin: 0;
      opacity: 0.85;
      font-size: 16px;
    }
    h1 {
      margin: 4px 0 8px;
      font-size: clamp(24px, 3.4vw, 34px);
      font-weight: 600;
    }
    .banniere-texte p:last-child {
      margin: 0;
      opacity: 0.8;
    }
    .banniere-deco mat-icon {
      font-size: 120px;
      width: 120px;
      height: 120px;
      opacity: 0.18;
      animation: flotte 6s ease-in-out infinite alternate;
    }
    @keyframes flotte {
      to {
        transform: translateY(-10px) rotate(-4deg);
      }
    }
    .titre-section {
      font-size: 16px;
      font-weight: 600;
      color: var(--ged-texte-attenue);
      margin: 8px 0 14px;
    }
    .indicateurs {
      display: grid;
      gap: 16px;
      grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
      margin-bottom: 28px;
    }
    .raccourcis {
      display: grid;
      gap: 16px;
      grid-template-columns: repeat(auto-fill, minmax(260px, 1fr));
      margin-bottom: 28px;
    }
    .raccourci {
      display: flex;
      align-items: center;
      gap: 14px;
      text-decoration: none;
      color: inherit;
      padding: 18px;
    }
    .raccourci strong,
    .raccourci .texte-attenue {
      display: block;
    }
    .raccourci .texte-attenue {
      font-size: 13px;
      margin-top: 2px;
    }
    .raccourci .icone {
      display: grid;
      place-items: center;
      width: 44px;
      height: 44px;
      flex: none;
      border-radius: 12px;
      background: var(--mat-sys-primary-container);
      color: var(--ged-primaire);
    }
    .fleche {
      margin-inline-start: auto;
      color: var(--ged-texte-attenue);
      transition: transform 200ms var(--ged-courbe);
    }
    .raccourci:hover .fleche {
      transform: translateX(calc(var(--sens, 1) * 4px));
    }
    [dir='rtl'] .raccourci:hover .fleche {
      transform: scaleX(-1) translateX(4px);
    }
    .bientot {
      display: flex;
      gap: 16px;
      align-items: center;
      background: linear-gradient(120deg, white, color-mix(in srgb, var(--ged-primaire) 5%, white));
    }
    .bientot mat-icon {
      color: var(--ged-primaire);
      font-size: 32px;
      width: 32px;
      height: 32px;
    }
    .bientot p {
      margin: 4px 0 0;
    }
    @media (max-width: 600px) {
      .banniere-deco {
        display: none;
      }
    }
  `,
})
export class Accueil implements OnInit {
  private readonly api = inject(ApiService);
  protected readonly session = inject(SessionService);
  protected readonly valeurs = signal<Record<string, number>>({});
  private readonly charge = signal(false);

  protected readonly indicateurs = computed(() =>
    this.charge() ? INDICATEURS.filter((i) => i.cle in this.valeurs()) : null,
  );

  protected readonly salutation = computed<Cle>(() => {
    const heure = new Date().getHours();
    return heure < 12 ? 'accueil.bonjour' : heure < 18 ? 'accueil.bon_apres_midi' : 'accueil.bonsoir';
  });

  protected readonly raccourcis = computed(() => {
    const droits = this.session.droits();
    const liste: { lien: string; icone: string; titre: Cle; description: Cle }[] = [
      { lien: '/compte', icone: 'manage_accounts', titre: 'menu.mon_compte', description: 'accueil.raccourci_compte' },
    ];
    if (droits.utilisateurs)
      liste.push({
        lien: '/administration/utilisateurs',
        icone: 'group',
        titre: 'menu.utilisateurs',
        description: 'accueil.raccourci_utilisateurs',
      });
    if (droits.organisation)
      liste.push({
        lien: '/administration/organisation',
        icone: 'account_tree',
        titre: 'menu.organisation',
        description: 'accueil.raccourci_organisation',
      });
    if (droits.roles)
      liste.push({
        lien: '/administration/roles',
        icone: 'shield_person',
        titre: 'menu.roles',
        description: 'accueil.raccourci_roles',
      });
    return liste;
  });

  async ngOnInit(): Promise<void> {
    try {
      this.valeurs.set((await firstValueFrom(this.api.tableauDeBord())).indicateurs);
    } finally {
      this.charge.set(true);
    }
  }
}
