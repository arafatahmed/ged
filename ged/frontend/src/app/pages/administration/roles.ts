import { ChangeDetectionStrategy, Component, OnInit, computed, inject, signal } from '@angular/core';
import { NonNullableFormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { MatButtonModule } from '@angular/material/button';
import { MatCheckboxModule } from '@angular/material/checkbox';
import { MAT_DIALOG_DATA, MatDialogModule, MatDialogRef } from '@angular/material/dialog';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatIconModule } from '@angular/material/icon';
import { MatInputModule } from '@angular/material/input';
import { MatSlideToggleModule } from '@angular/material/slide-toggle';
import { MatTooltipModule } from '@angular/material/tooltip';
import { firstValueFrom } from 'rxjs';

import { ApiService } from '../../core/api.service';
import { PermissionCatalogue, Role } from '../../core/modeles';
import { NotificationService, erreursChamps, messageErreur } from '../../core/notification.service';
import { BilinguePipe, TraduirePipe } from '../../core/pipes';
import { DialoguesService } from '../../partage/dialogues.service';
import { EntetePage } from '../../partage/entete-page';
import { Squelette } from '../../partage/etats';

interface DonneesRole {
  role: Role | null;
  permissions: PermissionCatalogue[];
}

/** Édition d'un rôle : libellés, double authentification, permissions groupées. */
@Component({
  selector: 'ged-dialogue-role',
  imports: [
    ReactiveFormsModule,
    MatDialogModule,
    MatButtonModule,
    MatFormFieldModule,
    MatInputModule,
    MatCheckboxModule,
    MatSlideToggleModule,
    MatIconModule,
    TraduirePipe,
  ],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <h2 mat-dialog-title>{{ (donnees.role ? 'roles.modifier' : 'roles.nouveau') | t }}</h2>
    <mat-dialog-content>
      @if (erreurGenerale()) {
        <p class="erreur" role="alert"><mat-icon>error</mat-icon>{{ erreurGenerale() }}</p>
      }
      @if (donnees.role?.systeme) {
        <p class="texte-attenue petit">{{ 'roles.systeme_aide' | t }}</p>
      }
      <form [formGroup]="formulaire" class="formulaire-grille" novalidate>
        <mat-form-field appearance="outline">
          <mat-label>{{ 'organisation.code' | t }}</mat-label>
          <input matInput formControlName="code" dir="ltr" [readonly]="!!donnees.role?.systeme" />
          @if (erreurs()['code']) {
            <mat-error>{{ erreurs()['code'] }}</mat-error>
          }
        </mat-form-field>
        <mat-form-field appearance="outline">
          <mat-label>{{ 'champ.libelle_fr' | t }}</mat-label>
          <input matInput formControlName="libelle_fr" dir="ltr" />
        </mat-form-field>
        <mat-form-field appearance="outline">
          <mat-label>{{ 'champ.libelle_ar' | t }}</mat-label>
          <input matInput formControlName="libelle_ar" dir="rtl" />
        </mat-form-field>
        <mat-form-field appearance="outline">
          <mat-label>{{ 'champ.description' | t }}</mat-label>
          <input matInput formControlName="description" />
        </mat-form-field>
        <mat-slide-toggle formControlName="mfa_requis">{{ 'roles.mfa_requis' | t }}</mat-slide-toggle>
        <mat-slide-toggle formControlName="actif">{{ 'champ.actif' | t }}</mat-slide-toggle>
      </form>
      <h3>
        {{ 'roles.permissions' | t }} <span class="pastille info">{{ selection().size }}</span>
      </h3>
      <div class="groupes">
        @for (groupe of groupes(); track groupe.nom) {
          <fieldset>
            <legend>
              <mat-checkbox
                [checked]="toutCoche(groupe.permissions)"
                [indeterminate]="partiel(groupe.permissions)"
                (change)="cocherGroupe(groupe.permissions, $event.checked)"
              >
                {{ groupe.nom }}
              </mat-checkbox>
            </legend>
            @for (p of groupe.permissions; track p.code) {
              <mat-checkbox [checked]="selection().has(p.code)" (change)="basculer(p.code)">
                {{ p.description }} <code class="ltr code">{{ p.code }}</code>
              </mat-checkbox>
            }
          </fieldset>
        }
      </div>
    </mat-dialog-content>
    <mat-dialog-actions align="end">
      <button mat-button mat-dialog-close>{{ 'action.annuler' | t }}</button>
      <button mat-flat-button [disabled]="envoi() || formulaire.invalid" (click)="enregistrer()">
        {{ 'action.enregistrer' | t }}
      </button>
    </mat-dialog-actions>
  `,
  styles: `
    h3 {
      display: flex;
      align-items: center;
      gap: 8px;
      font-size: 15px;
      margin: 16px 0 8px;
    }
    .groupes {
      display: grid;
      gap: 12px;
      grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
    }
    fieldset {
      border: 1px solid var(--ged-bordure);
      border-radius: 14px;
      padding: 4px 12px 10px;
      display: grid;
    }
    legend {
      font-weight: 600;
      padding: 0 4px;
    }
    .code {
      font-size: 11px;
      color: var(--ged-texte-attenue);
    }
    .erreur {
      display: flex;
      gap: 8px;
      align-items: center;
      color: var(--ged-alerte);
    }
    .petit {
      font-size: 13px;
    }
  `,
})
export class DialogueRole {
  protected readonly donnees = inject<DonneesRole>(MAT_DIALOG_DATA);
  private readonly reference = inject(MatDialogRef<DialogueRole, Role>);
  private readonly api = inject(ApiService);
  protected readonly selection = signal(new Set(this.donnees.role?.permissions ?? []));
  protected readonly envoi = signal(false);
  protected readonly erreurs = signal<Record<string, string>>({});
  protected readonly erreurGenerale = signal('');
  protected readonly formulaire = inject(NonNullableFormBuilder).group({
    code: [this.donnees.role?.code ?? '', [Validators.required, Validators.pattern(/^[-a-zA-Z0-9_]+$/)]],
    libelle_fr: [this.donnees.role?.libelle_fr ?? '', Validators.required],
    libelle_ar: [this.donnees.role?.libelle_ar ?? ''],
    description: [this.donnees.role?.description ?? ''],
    mfa_requis: [this.donnees.role?.mfa_requis ?? false],
    actif: [this.donnees.role?.actif ?? true],
  });
  protected readonly groupes = computed(() => {
    const parGroupe = new Map<string, PermissionCatalogue[]>();
    for (const p of this.donnees.permissions) parGroupe.set(p.groupe, [...(parGroupe.get(p.groupe) ?? []), p]);
    return [...parGroupe].map(([nom, permissions]) => ({ nom, permissions }));
  });

  protected basculer(code: string): void {
    this.selection.update((ensemble) => {
      const copie = new Set(ensemble);
      if (!copie.delete(code)) copie.add(code);
      return copie;
    });
  }
  protected toutCoche(liste: PermissionCatalogue[]): boolean {
    return liste.every((p) => this.selection().has(p.code));
  }
  protected partiel(liste: PermissionCatalogue[]): boolean {
    return !this.toutCoche(liste) && liste.some((p) => this.selection().has(p.code));
  }
  protected cocherGroupe(liste: PermissionCatalogue[], coche: boolean): void {
    this.selection.update((ensemble) => {
      const copie = new Set(ensemble);
      for (const p of liste) coche ? copie.add(p.code) : copie.delete(p.code);
      return copie;
    });
  }

  protected async enregistrer(): Promise<void> {
    this.envoi.set(true);
    this.erreurs.set({});
    this.erreurGenerale.set('');
    try {
      const corps = { ...this.formulaire.getRawValue(), permissions: [...this.selection()] };
      this.reference.close(await firstValueFrom(this.api.enregistrerRole(corps, this.donnees.role?.uuid)));
    } catch (erreur) {
      const champs = erreursChamps(erreur);
      this.erreurs.set(champs);
      this.erreurGenerale.set(champs['__all__'] ?? (Object.keys(champs).length ? '' : messageErreur(erreur)));
    } finally {
      this.envoi.set(false);
    }
  }
}

/** Rôles de l'institution et leurs permissions. */
@Component({
  selector: 'ged-roles',
  imports: [MatButtonModule, MatIconModule, MatTooltipModule, TraduirePipe, BilinguePipe, EntetePage, Squelette],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <ged-entete-page [titre]="'roles.titre' | t" [sousTitre]="'roles.sous_titre' | t" icone="shield_person">
      <button mat-flat-button (click)="editer(null)"><mat-icon>add</mat-icon>{{ 'roles.nouveau' | t }}</button>
    </ged-entete-page>
    @if (roles(); as liste) {
      <div class="roles">
        @for (r of liste; track r.uuid) {
          <button
            class="carte carte-interactive role"
            [class.inactif]="!r.actif"
            (click)="editer(r)"
            animate.enter="entree-montee"
            [style.--rang]="$index"
          >
            <div class="ligne">
              <span class="icone"
                ><mat-icon>{{ r.code.startsWith('administrateur') ? 'admin_panel_settings' : 'badge' }}</mat-icon></span
              >
              <span class="espace"></span>
              @if (r.mfa_requis) {
                <mat-icon class="mfa" [matTooltip]="'roles.mfa_requis' | t">shield_lock</mat-icon>
              }
              @if (r.systeme) {
                <span class="pastille">{{ 'roles.systeme' | t }}</span>
              }
              @if (!r.actif) {
                <span class="pastille alerte">{{ 'champ.inactif' | t }}</span>
              }
            </div>
            <strong class="nom">{{ r.libelle_fr | bilingue: r.libelle_ar }}</strong>
            <span class="texte-attenue ltr code">{{ r.code }}</span>
            <div class="jauge" aria-hidden="true">
              <span [style.width.%]="(r.permissions.length / total()) * 100"></span>
            </div>
            <div class="ligne texte-attenue pied">
              <span>{{ 'roles.nombre_permissions' | t: { nombre: r.permissions.length } }}</span>
              <span class="espace"></span>
              <span><mat-icon inline>person</mat-icon> {{ r.titulaires ?? 0 }}</span>
            </div>
          </button>
        }
      </div>
    } @else {
      <div class="carte"><ged-squelette /></div>
    }
  `,
  styles: `
    .roles {
      display: grid;
      gap: 16px;
      grid-template-columns: repeat(auto-fill, minmax(260px, 1fr));
    }
    .role {
      display: grid;
      gap: 6px;
      text-align: start;
      font: inherit;
      color: inherit;
      cursor: pointer;
    }
    .role.inactif {
      opacity: 0.6;
    }
    .icone {
      display: grid;
      place-items: center;
      width: 42px;
      height: 42px;
      border-radius: 12px;
      background: var(--mat-sys-primary-container);
      color: var(--ged-primaire);
    }
    .mfa {
      color: var(--ged-succes);
    }
    .nom {
      font-size: 16px;
      margin-top: 6px;
    }
    .code {
      font-size: 12px;
    }
    .jauge {
      height: 6px;
      border-radius: 999px;
      background: #eef1f6;
      overflow: hidden;
      margin-top: 8px;
    }
    .jauge span {
      display: block;
      height: 100%;
      border-radius: inherit;
      transition: width 600ms var(--ged-courbe);
      background: linear-gradient(90deg, var(--ged-primaire), var(--ged-secondaire));
    }
    .pied {
      font-size: 13px;
    }
  `,
})
export class Roles implements OnInit {
  private readonly api = inject(ApiService);
  private readonly dialogues = inject(DialoguesService);
  private readonly notifications = inject(NotificationService);
  protected readonly roles = signal<Role[] | null>(null);
  private readonly permissions = signal<PermissionCatalogue[]>([]);
  protected readonly total = computed(() => Math.max(1, this.permissions().length));

  async ngOnInit(): Promise<void> {
    await this.charger();
  }

  private async charger(): Promise<void> {
    const donnees = await firstValueFrom(this.api.roles());
    this.roles.set(donnees.roles);
    this.permissions.set(donnees.permissions);
  }

  protected async editer(role: Role | null): Promise<void> {
    const resultat = await this.dialogues.ouvrir<DialogueRole, DonneesRole, Role>(
      DialogueRole,
      { role, permissions: this.permissions() },
      { width: '880px' },
    );
    if (resultat) {
      this.notifications.succes('roles.enregistre');
      await this.charger();
    }
  }
}
