import { ChangeDetectionStrategy, Component, OnInit, inject, signal } from '@angular/core';
import { NonNullableFormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { MatButtonModule } from '@angular/material/button';
import { MatButtonToggleModule } from '@angular/material/button-toggle';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatIconModule } from '@angular/material/icon';
import { MatInputModule } from '@angular/material/input';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';
import { ActivatedRoute, Router } from '@angular/router';
import { firstValueFrom } from 'rxjs';

import { ApiService } from '../../core/api.service';
import { Enrolement, Langue, Session } from '../../core/modeles';
import { erreursChamps, messageErreur } from '../../core/notification.service';
import { BilinguePipe, TraduirePipe } from '../../core/pipes';
import { SessionService } from '../../core/session.service';
import { TraductionService } from '../../core/traduction.service';

type Etape = 'identifiants' | 'mfa' | 'enrolement' | 'codes';

/** Connexion en étapes : mot de passe, puis code TOTP ou activation de la double authentification. */
@Component({
  selector: 'ged-connexion',
  imports: [
    ReactiveFormsModule,
    MatFormFieldModule,
    MatInputModule,
    MatButtonModule,
    MatIconModule,
    MatProgressSpinnerModule,
    MatButtonToggleModule,
    TraduirePipe,
    BilinguePipe,
  ],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './connexion.html',
  styleUrl: './connexion.scss',
})
export class Connexion implements OnInit {
  private readonly api = inject(ApiService);
  protected readonly session = inject(SessionService);
  protected readonly traduction = inject(TraductionService);
  private readonly router = inject(Router);
  private readonly route = inject(ActivatedRoute);
  private readonly fb = inject(NonNullableFormBuilder);

  protected readonly etape = signal<Etape>('identifiants');
  protected readonly envoi = signal(false);
  protected readonly erreur = signal('');
  protected readonly secousse = signal(0);
  protected readonly motDePasseVisible = signal(false);
  protected readonly enrolement = signal<Enrolement | null>(null);
  protected readonly codesSecours = signal<string[]>([]);
  protected readonly sessionExpiree = this.route.snapshot.queryParamMap.has('expiree');

  protected readonly identifiants = this.fb.group({
    identifiant: ['', Validators.required],
    mot_de_passe: ['', Validators.required],
  });
  protected readonly code = this.fb.control('', [Validators.required, Validators.minLength(6)]);

  async ngOnInit(): Promise<void> {
    const session = await this.session.pret().catch(() => null);
    if (session?.etape) await this.allerA(session.etape);
  }

  protected changerLangue(langue: Langue): void {
    this.traduction.choisir(langue);
  }

  protected async seConnecter(): Promise<void> {
    if (this.identifiants.invalid) {
      this.identifiants.markAllAsTouched();
      return;
    }
    const { identifiant, mot_de_passe } = this.identifiants.getRawValue();
    await this.executer(async () => {
      const session = await firstValueFrom(this.api.connexion(identifiant, mot_de_passe));
      this.identifiants.controls.mot_de_passe.reset();
      await this.suite(session);
    });
  }

  protected async verifierCode(): Promise<void> {
    if (this.code.invalid) return;
    await this.executer(async () => {
      if (this.etape() === 'enrolement') {
        const resultat = await firstValueFrom(this.api.confirmerEnrolement(this.code.value));
        this.session.appliquer(resultat.session);
        this.codesSecours.set(resultat.codes_secours);
        this.etape.set('codes');
      } else {
        await this.suite(await firstValueFrom(this.api.verification(this.code.value)));
      }
      this.code.reset();
    });
  }

  /** Soumission automatique dès que les 6 chiffres sont saisis. */
  protected saisieCode(): void {
    if (/^\d{6}$/.test(this.code.value.replace(/\s/g, '')) && !this.envoi()) void this.verifierCode();
  }

  protected recommencer(): void {
    void firstValueFrom(this.api.deconnexion()).then((session) => this.session.appliquer(session));
    this.code.reset();
    this.erreur.set('');
    this.etape.set('identifiants');
  }

  protected async continuer(): Promise<void> {
    await this.entrer();
  }

  private async suite(session: Session): Promise<void> {
    this.session.appliquer(session);
    if (session.authentifie) {
      await this.entrer();
    } else if (session.etape) {
      await this.allerA(session.etape);
    }
  }

  private async allerA(etape: 'mfa' | 'enrolement'): Promise<void> {
    this.erreur.set('');
    if (etape === 'enrolement') {
      this.enrolement.set(await firstValueFrom(this.api.enrolement()));
    }
    this.etape.set(etape);
  }

  private async entrer(): Promise<void> {
    const suivant = this.route.snapshot.queryParamMap.get('suivant') ?? '';
    if (suivant.startsWith('/administration-technique/')) {
      window.location.assign(suivant);
      return;
    }
    const interne = suivant.startsWith('/') && !suivant.startsWith('//') ? suivant : '/';
    await this.router.navigateByUrl(this.session.pageImposee() ?? interne);
  }

  private async executer(action: () => Promise<void>): Promise<void> {
    this.envoi.set(true);
    this.erreur.set('');
    try {
      await action();
    } catch (erreur) {
      const code = (erreur as { error?: { code?: string } }).error?.code;
      if (code === 'etape_expiree') {
        this.etape.set('identifiants');
      }
      const champs = erreursChamps(erreur);
      this.erreur.set(champs['code'] ?? messageErreur(erreur) ?? this.traduction.t('erreur.inattendue'));
      this.secousse.update((n) => n + 1);
      this.code.reset();
    } finally {
      this.envoi.set(false);
    }
  }
}
