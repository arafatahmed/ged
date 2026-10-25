import { ChangeDetectionStrategy, Component, OnInit, computed, inject, input, signal } from '@angular/core';
import { NonNullableFormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { MatButtonModule } from '@angular/material/button';
import { MatCheckboxModule } from '@angular/material/checkbox';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatIconModule } from '@angular/material/icon';
import { MatInputModule } from '@angular/material/input';
import { MatSelectModule } from '@angular/material/select';
import { MatTabsModule } from '@angular/material/tabs';
import { MatTooltipModule } from '@angular/material/tooltip';
import { RouterLink } from '@angular/router';
import { Observable, firstValueFrom } from 'rxjs';

import { ApiService } from '../../core/api.service';
import { OptionsUtilisateurs, UtilisateurDetail } from '../../core/modeles';
import { NotificationService, erreursChamps } from '../../core/notification.service';
import { BilinguePipe, DateLocalePipe, TraduirePipe } from '../../core/pipes';
import { TraductionService } from '../../core/traduction.service';
import { Cle } from '../../i18n/fr';
import { DialogueDelegation, DonneesDelegation } from '../../partage/dialogue-delegation';
import { DialoguesService } from '../../partage/dialogues.service';
import { EtatVide, Squelette } from '../../partage/etats';

function aujourdHui(): string {
  const date = new Date();
  return new Date(date.getTime() - date.getTimezoneOffset() * 60000).toISOString().slice(0, 10);
}

/** Fiche d'un compte : profil, affectations, actions de sécurité, sessions et délégations. */
@Component({
  selector: 'ged-utilisateur',
  imports: [
    RouterLink,
    ReactiveFormsModule,
    MatTabsModule,
    MatFormFieldModule,
    MatInputModule,
    MatSelectModule,
    MatCheckboxModule,
    MatButtonModule,
    MatIconModule,
    MatTooltipModule,
    TraduirePipe,
    BilinguePipe,
    DateLocalePipe,
    EtatVide,
    Squelette,
  ],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './utilisateur.html',
  styleUrl: './utilisateur.scss',
})
export class Utilisateur implements OnInit {
  /** Fourni par le routeur (withComponentInputBinding). */
  readonly uuid = input.required<string>();

  private readonly api = inject(ApiService);
  private readonly dialogues = inject(DialoguesService);
  private readonly notifications = inject(NotificationService);
  protected readonly traduction = inject(TraductionService);
  private readonly fb = inject(NonNullableFormBuilder);

  protected readonly compte = signal<UtilisateurDetail | null>(null);
  protected readonly options = signal<OptionsUtilisateurs | null>(null);
  protected readonly introuvable = signal(false);
  protected readonly envoi = signal(false);
  protected readonly erreursProfil = signal<Record<string, string>>({});
  protected readonly erreursAffectation = signal<Record<string, string>>({});

  protected readonly profil = this.fb.group({
    nom: ['', Validators.required],
    prenom: ['', Validators.required],
    nom_ar: [''],
    courriel: ['', Validators.email],
    langue: [''],
    niveau_habilitation: [0],
  });
  protected readonly affectation = this.fb.group({
    unite: ['', Validators.required],
    role: ['', Validators.required],
    poste: [null as number | null],
    etendue_sous_unites: [false],
    date_debut: [aujourdHui(), Validators.required],
    date_fin: [''],
  });

  protected readonly postesDeLUnite = computed(() =>
    (this.options()?.postes ?? []).filter((p) => p.unite === this.uniteChoisie()),
  );
  private readonly uniteChoisie = signal('');
  protected readonly enCours = computed(() => (this.compte()?.affectations ?? []).filter((a) => a.active));
  protected readonly passees = computed(() => (this.compte()?.affectations ?? []).filter((a) => !a.active));

  async ngOnInit(): Promise<void> {
    this.affectation.controls.unite.valueChanges.subscribe((valeur) => {
      this.uniteChoisie.set(valeur);
      this.affectation.controls.poste.setValue(null);
    });
    try {
      const [compte, options] = await Promise.all([
        firstValueFrom(this.api.utilisateur(this.uuid())),
        firstValueFrom(this.api.optionsUtilisateurs()),
      ]);
      this.options.set(options);
      this.afficher(compte);
    } catch {
      this.introuvable.set(true);
    }
  }

  private afficher(compte: UtilisateurDetail): void {
    this.compte.set(compte);
    this.profil.reset({
      nom: compte.nom,
      prenom: compte.prenom,
      nom_ar: compte.nom_ar,
      courriel: compte.courriel,
      langue: compte.langue,
      niveau_habilitation: compte.niveau_habilitation,
    });
  }

  protected niveauxProposes() {
    const niveaux = this.options()?.niveaux ?? [];
    const actuel = this.compte()?.niveau_habilitation ?? 0;
    return niveaux.some((n) => n.valeur === actuel)
      ? niveaux
      : [...niveaux, { valeur: actuel, libelle: String(actuel) }];
  }

  protected async enregistrerProfil(): Promise<void> {
    await this.appeler(
      this.api.modifierUtilisateur(this.uuid(), this.profil.getRawValue()),
      'utilisateur.profil_enregistre',
      this.erreursProfil,
    );
  }

  protected async ajouterAffectation(): Promise<void> {
    const valeurs = this.affectation.getRawValue();
    const corps = { ...valeurs, date_fin: valeurs.date_fin || null };
    if (
      await this.appeler(
        this.api.ajouterAffectation(this.uuid(), corps),
        'utilisateur.affectation_ajoutee',
        this.erreursAffectation,
      )
    ) {
      this.affectation.reset({
        unite: '',
        role: '',
        poste: null,
        etendue_sous_unites: false,
        date_debut: aujourdHui(),
        date_fin: '',
      });
    }
  }

  protected async cloturer(uuid: string, libelle: string): Promise<void> {
    const confirme = await this.dialogues.confirmer({
      titre: this.traduction.t('utilisateur.cloturer_titre'),
      message: this.traduction.t('utilisateur.cloturer_message', { role: libelle }),
      confirmer: this.traduction.t('utilisateur.cloturer'),
    });
    if (confirme) await this.appeler(this.api.cloturerAffectation(uuid), 'utilisateur.affectation_cloturee');
  }

  protected async action(
    code: string,
    message: Cle,
    confirmation?: { titre: Cle; texte: Cle; danger?: boolean; motif?: boolean },
  ): Promise<void> {
    let corps = {};
    if (confirmation) {
      const reponse = await this.dialogues.confirmer({
        titre: this.traduction.t(confirmation.titre),
        message: this.traduction.t(confirmation.texte, { nom: this.compte()?.prenom + ' ' + this.compte()?.nom }),
        confirmer: this.traduction.t('action.confirmer'),
        danger: confirmation.danger,
        champ: confirmation.motif ? this.traduction.t('utilisateur.motif') : undefined,
      });
      if (!reponse) return;
      if (typeof reponse === 'string') corps = { motif: reponse };
    }
    await this.appeler(this.api.actionUtilisateur(this.uuid(), code, corps), message);
  }

  protected async reinitialiserMotDePasse(): Promise<void> {
    const confirme = await this.dialogues.confirmer({
      titre: this.traduction.t('utilisateur.mdp_titre'),
      message: this.traduction.t('utilisateur.mdp_confirmation'),
      confirmer: this.traduction.t('action.confirmer'),
    });
    if (!confirme) return;
    try {
      const resultat = await firstValueFrom(this.api.reinitialiserMotDePasse(this.uuid()));
      this.afficher(resultat.utilisateur);
      await this.dialogues.secret({
        titre: this.traduction.t('utilisateur.mdp_titre'),
        message: this.traduction.t('utilisateur.mdp_message'),
        valeurs: [resultat.mot_de_passe],
      });
    } catch (erreur) {
      this.notifications.erreur(erreur);
    }
  }

  protected async deleguer(): Promise<void> {
    const donnees: DonneesDelegation = {
      titre: this.traduction.t('delegation.titre_pour', { nom: `${this.compte()?.prenom} ${this.compte()?.nom}` }),
      options: () => this.api.optionsDelegationDe(this.uuid()),
      enregistrer: (corps) => this.api.creerDelegationPour(this.uuid(), corps),
    };
    if (await this.dialogues.ouvrir(DialogueDelegation, donnees)) {
      this.notifications.succes('delegation.enregistree');
      this.afficher(await firstValueFrom(this.api.utilisateur(this.uuid())));
    }
  }

  private async appeler(
    appel: Observable<UtilisateurDetail>,
    message: Cle,
    erreurs?: ReturnType<typeof signal<Record<string, string>>>,
  ): Promise<boolean> {
    this.envoi.set(true);
    erreurs?.set({});
    try {
      this.afficher(await firstValueFrom(appel));
      this.notifications.succes(message);
      return true;
    } catch (erreur) {
      const champs = erreursChamps(erreur);
      if (erreurs && Object.keys(champs).length && !champs['__all__']) {
        erreurs.set(champs);
      } else {
        this.notifications.erreur(erreur);
      }
      return false;
    } finally {
      this.envoi.set(false);
    }
  }
}
