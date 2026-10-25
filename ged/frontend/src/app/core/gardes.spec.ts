import { TestBed } from '@angular/core/testing';
import { ActivatedRouteSnapshot, Router, RouterStateSnapshot, UrlTree, provideRouter } from '@angular/router';

import { anonymeGarde, authentifieGarde, droitGarde } from './gardes';
import { Session } from './modeles';
import { SessionService } from './session.service';

class SessionFactice {
  etat: Session = { authentifie: false, etape: null, utilisateur: null, institution: null };
  pret = () => Promise.resolve(this.etat);
  authentifie = () => this.etat.authentifie;
  droits = () =>
    this.etat.droits ?? {
      organisation: false,
      types_unite: false,
      utilisateurs: false,
      roles: false,
      connexions: false,
    };
  pageImposee = () => (this.etat.exigences?.changer_mot_de_passe ? '/compte/mot-de-passe' : null);
}

describe('Gardes de navigation', () => {
  let session: SessionFactice;
  const route = {} as ActivatedRouteSnapshot;
  const vers = (url: string) => ({ url }) as RouterStateSnapshot;
  const executer = (garde: typeof authentifieGarde, url: string) =>
    TestBed.runInInjectionContext(() => garde(route, vers(url))) as Promise<boolean | UrlTree> | boolean | UrlTree;
  const enTexte = (resultat: boolean | UrlTree) =>
    resultat instanceof UrlTree ? TestBed.inject(Router).serializeUrl(resultat) : resultat;

  beforeEach(() => {
    session = new SessionFactice();
    TestBed.configureTestingModule({ providers: [provideRouter([]), { provide: SessionService, useValue: session }] });
  });

  it('renvoie un visiteur vers la connexion en gardant la page demandée', async () => {
    expect(enTexte(await executer(authentifieGarde, '/administration/roles'))).toBe(
      '/connexion?suivant=%2Fadministration%2Froles',
    );
    expect(enTexte(await executer(authentifieGarde, '/'))).toBe('/connexion');
  });

  it('impose la page de mot de passe tant que le mot de passe temporaire n’est pas changé', async () => {
    session.etat = {
      ...session.etat,
      authentifie: true,
      exigences: { changer_mot_de_passe: true, activer_mfa: false },
    };
    expect(enTexte(await executer(authentifieGarde, '/compte'))).toBe('/compte/mot-de-passe');
    expect(await executer(authentifieGarde, '/compte/mot-de-passe')).toBe(true);
  });

  it('écarte un utilisateur connecté de la page de connexion', async () => {
    expect(await executer(anonymeGarde, '/connexion')).toBe(true);
    session.etat = { ...session.etat, authentifie: true };
    expect(enTexte(await executer(anonymeGarde, '/connexion'))).toBe('/');
  });

  it('réserve chaque rubrique d’administration au droit correspondant', () => {
    expect(enTexte(executer(droitGarde('roles'), '/administration/roles') as UrlTree)).toBe('/acces-refuse');
    session.etat = {
      ...session.etat,
      droits: { organisation: false, types_unite: false, utilisateurs: false, roles: true, connexions: false },
    };
    expect(executer(droitGarde('roles'), '/administration/roles')).toBe(true);
  });
});
