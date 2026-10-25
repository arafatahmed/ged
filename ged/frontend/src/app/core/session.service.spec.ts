import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';

import { Session } from './modeles';
import { SessionService } from './session.service';
import { TraductionService } from './traduction.service';

const INSTITUTION = {
  nom_fr: 'Ministère',
  nom_ar: 'وزارة',
  sigle: 'MIN',
  couleur_primaire: '#123456',
  couleur_secondaire: '#654321',
  langue_defaut: 'ar' as const,
  format_date: 'd/m/Y',
  logo: false,
};

describe('SessionService', () => {
  let service: SessionService;
  let http: HttpTestingController;

  beforeEach(() => {
    localStorage.clear();
    TestBed.configureTestingModule({ providers: [provideHttpClient(), provideHttpClientTesting()] });
    service = TestBed.inject(SessionService);
    http = TestBed.inject(HttpTestingController);
  });

  afterEach(() => http.verify());

  it('charge la session une seule fois, applique la langue et les couleurs de l’institution', async () => {
    const premier = service.pret();
    const second = service.pret();
    http
      .expectOne('/api/v1/session/')
      .flush({ authentifie: false, etape: null, utilisateur: null, institution: INSTITUTION });
    await Promise.all([premier, second]);
    expect(service.authentifie()).toBe(false);
    expect(TestBed.inject(TraductionService).langue()).toBe('ar');
    expect(document.documentElement.style.getPropertyValue('--ged-primaire')).toBe('#123456');
  });

  it('impose le changement de mot de passe avant la double authentification', () => {
    const base: Session = { authentifie: true, etape: null, utilisateur: null, institution: null };
    service.appliquer({ ...base, exigences: { changer_mot_de_passe: true, activer_mfa: true } });
    expect(service.pageImposee()).toBe('/compte/mot-de-passe');
    service.appliquer({ ...base, exigences: { changer_mot_de_passe: false, activer_mfa: true } });
    expect(service.pageImposee()).toBe('/compte/double-authentification');
    service.appliquer({ ...base, exigences: { changer_mot_de_passe: false, activer_mfa: false } });
    expect(service.pageImposee()).toBeNull();
  });

  it('calcule la visibilité de l’administration à partir des droits', () => {
    const droits = { organisation: false, types_unite: false, utilisateurs: true, roles: false, connexions: false };
    service.appliquer({ authentifie: true, etape: null, utilisateur: null, institution: null, droits });
    expect(service.administration()).toBe(true);
    service.oublier();
    expect(service.authentifie()).toBe(false);
    expect(service.administration()).toBe(false);
  });
});
