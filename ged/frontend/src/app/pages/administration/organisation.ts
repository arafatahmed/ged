import { ChangeDetectionStrategy, Component, OnInit, computed, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { MatButtonModule } from '@angular/material/button';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatIconModule } from '@angular/material/icon';
import { MatInputModule } from '@angular/material/input';
import { MatMenuModule } from '@angular/material/menu';
import { MatSlideToggleModule } from '@angular/material/slide-toggle';
import { MatTabsModule } from '@angular/material/tabs';
import { MatTooltipModule } from '@angular/material/tooltip';
import { NgTemplateOutlet } from '@angular/common';
import { firstValueFrom } from 'rxjs';

import { ApiService } from '../../core/api.service';
import { TypeUnite, Unite } from '../../core/modeles';
import { NotificationService } from '../../core/notification.service';
import { BilinguePipe, TraduirePipe } from '../../core/pipes';
import { SessionService } from '../../core/session.service';
import { TraductionService } from '../../core/traduction.service';
import { DialoguesService } from '../../partage/dialogues.service';
import { EntetePage } from '../../partage/entete-page';
import { EtatVide, Squelette } from '../../partage/etats';
import { DialogueTypeUnite, DialogueUnite, DonneesTypeUnite, DonneesUnite } from './dialogues-organisation';

interface Noeud {
  unite: Unite;
  enfants: Noeud[];
}

/** Organisation : arbre des unités (dépliable, filtrable) et types d'unité. */
@Component({
  selector: 'ged-organisation',
  imports: [
    NgTemplateOutlet,
    FormsModule,
    MatTabsModule,
    MatButtonModule,
    MatIconModule,
    MatMenuModule,
    MatTooltipModule,
    MatFormFieldModule,
    MatInputModule,
    MatSlideToggleModule,
    TraduirePipe,
    BilinguePipe,
    EntetePage,
    EtatVide,
    Squelette,
  ],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './organisation.html',
  styleUrl: './organisation.scss',
})
export class Organisation implements OnInit {
  private readonly api = inject(ApiService);
  private readonly dialogues = inject(DialoguesService);
  private readonly notifications = inject(NotificationService);
  protected readonly traduction = inject(TraductionService);
  protected readonly session = inject(SessionService);

  protected readonly unites = signal<Unite[] | null>(null);
  protected readonly types = signal<TypeUnite[]>([]);
  protected readonly tousLesTypes = signal<TypeUnite[] | null>(null);
  protected readonly ouvertes = signal(new Set<string>());
  protected readonly filtre = signal('');
  protected readonly inactives = signal(false);

  protected readonly arbre = computed<Noeud[]>(() => {
    const liste = (this.unites() ?? []).filter((u) => this.inactives() || u.actif);
    const noeuds = new Map<string, Noeud>(liste.map((u) => [u.uuid, { unite: u, enfants: [] }]));
    const racines: Noeud[] = [];
    for (const noeud of noeuds.values()) {
      const parent = noeud.unite.parent ? noeuds.get(noeud.unite.parent) : undefined;
      (parent ? parent.enfants : racines).push(noeud);
    }
    const terme = this.filtre().trim().toLowerCase();
    if (!terme) return racines;
    const correspond = (n: Noeud): Noeud | null => {
      const enfants = n.enfants.map(correspond).filter((e): e is Noeud => e !== null);
      const texte = `${n.unite.code} ${n.unite.sigle} ${n.unite.libelle_fr} ${n.unite.libelle_ar}`.toLowerCase();
      return texte.includes(terme) || enfants.length ? { unite: n.unite, enfants } : null;
    };
    return racines.map(correspond).filter((n): n is Noeud => n !== null);
  });

  async ngOnInit(): Promise<void> {
    await this.charger();
    if (this.session.droits().types_unite) await this.chargerTypes();
  }

  private async charger(): Promise<void> {
    const donnees = await firstValueFrom(this.api.unites());
    this.unites.set(donnees.unites);
    this.types.set(donnees.types);
    if (!this.ouvertes().size) {
      this.ouvertes.set(new Set(donnees.unites.filter((u) => u.profondeur < 1).map((u) => u.uuid)));
    }
  }

  private async chargerTypes(): Promise<void> {
    this.tousLesTypes.set(await firstValueFrom(this.api.typesUnite()));
  }

  protected estOuverte(uuid: string): boolean {
    return !!this.filtre().trim() || this.ouvertes().has(uuid);
  }

  protected basculer(uuid: string): void {
    this.ouvertes.update((ensemble) => {
      const copie = new Set(ensemble);
      if (!copie.delete(uuid)) copie.add(uuid);
      return copie;
    });
  }

  protected toutDeplier(ouvrir: boolean): void {
    this.ouvertes.set(ouvrir ? new Set((this.unites() ?? []).map((u) => u.uuid)) : new Set());
  }

  protected async editer(unite: Unite | null, parent: string | null = null): Promise<void> {
    const donnees: DonneesUnite = {
      unite,
      parent,
      unites: this.unites() ?? [],
      types: this.types(),
      enregistrer: (corps, uuid) => this.api.enregistrerUnite(corps, uuid),
    };
    const resultat = await this.dialogues.ouvrir<DialogueUnite, DonneesUnite, Unite>(DialogueUnite, donnees, {
      width: '720px',
    });
    if (resultat) {
      if (parent) this.ouvertes.update((e) => new Set([...e, parent]));
      this.notifications.succes('organisation.unite_enregistree');
      await this.charger();
    }
  }

  protected async desactiver(unite: Unite): Promise<void> {
    const confirme = await this.dialogues.confirmer({
      titre: this.traduction.t('organisation.desactiver_titre'),
      message: this.traduction.t('organisation.desactiver_message', {
        unite: this.traduction.libelle(unite.libelle_fr, unite.libelle_ar),
      }),
      confirmer: this.traduction.t('action.desactiver'),
      danger: true,
    });
    if (!confirme) return;
    try {
      await firstValueFrom(this.api.desactiverUnite(unite.uuid));
      this.notifications.succes('organisation.unite_desactivee');
      await this.charger();
    } catch (erreur) {
      this.notifications.erreur(erreur);
    }
  }

  protected async editerType(type: TypeUnite | null): Promise<void> {
    const donnees: DonneesTypeUnite = { type, enregistrer: (corps, id) => this.api.enregistrerTypeUnite(corps, id) };
    if (await this.dialogues.ouvrir(DialogueTypeUnite, donnees)) {
      this.notifications.succes('organisation.type_enregistre');
      await Promise.all([this.chargerTypes(), this.charger()]);
    }
  }
}
