import { HttpClient, provideHttpClient, withInterceptors } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { Router, provideRouter } from '@angular/router';

import { entetesIntercepteur, securiteIntercepteur } from './intercepteurs';
import { SessionService } from './session.service';
import { TraductionService } from './traduction.service';

describe('Intercepteurs HTTP', () => {
  let http: HttpClient;
  let controleur: HttpTestingController;
  let router: Router;
  const session = { oublier: vi.fn(), recharger: vi.fn(() => Promise.resolve()) };

  beforeEach(() => {
    localStorage.clear();
    TestBed.configureTestingModule({
      providers: [
        provideRouter([]),
        provideHttpClient(withInterceptors([entetesIntercepteur, securiteIntercepteur])),
        provideHttpClientTesting(),
        { provide: SessionService, useValue: session },
      ],
    });
    http = TestBed.inject(HttpClient);
    controleur = TestBed.inject(HttpTestingController);
    router = TestBed.inject(Router);
    vi.spyOn(router, 'navigate').mockResolvedValue(true);
    vi.spyOn(router, 'navigateByUrl').mockResolvedValue(true);
  });

  afterEach(() => controleur.verify());

  it('transmet la langue de l’interface à l’API', () => {
    TestBed.inject(TraductionService).choisir('ar');
    http.get('/api/v1/compte/').subscribe();
    expect(controleur.expectOne('/api/v1/compte/').request.headers.get('X-Langue')).toBe('ar');
  });

  it('renvoie vers la connexion quand la session a expiré', () => {
    http.get('/api/v1/compte/').subscribe({ error: () => undefined });
    controleur
      .expectOne('/api/v1/compte/')
      .flush({ code: 'session_expiree' }, { status: 401, statusText: 'Unauthorized' });
    expect(session.oublier).toHaveBeenCalled();
    expect(router.navigate).toHaveBeenCalledWith(['/connexion'], { queryParams: { expiree: 1 } });
  });

  it('impose la double authentification quand l’API l’exige', async () => {
    http.get('/api/v1/compte/').subscribe({ error: () => undefined });
    controleur.expectOne('/api/v1/compte/').flush({ code: 'mfa_requise' }, { status: 403, statusText: 'Forbidden' });
    await Promise.resolve();
    expect(session.recharger).toHaveBeenCalled();
    await Promise.resolve();
    expect(router.navigateByUrl).toHaveBeenCalledWith('/compte/double-authentification');
  });
});
