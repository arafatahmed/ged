import { TestBed } from '@angular/core/testing';

import { AR } from '../i18n/ar';
import { FR } from '../i18n/fr';
import { TraductionService } from './traduction.service';

describe('TraductionService', () => {
  let service: TraductionService;

  beforeEach(() => {
    localStorage.clear();
    TestBed.configureTestingModule({});
    service = TestBed.inject(TraductionService);
  });

  it('traduit en français par défaut et remplace les paramètres', () => {
    expect(service.t('menu.accueil')).toBe('Accueil');
    expect(service.t('compte.jusqu_au', { date: '3 mai' })).toBe("jusqu'au 3 mai");
  });

  it('bascule en arabe, met le document en RTL et mémorise le choix', () => {
    service.choisir('ar');
    TestBed.tick();
    expect(service.t('menu.accueil')).toBe('الرئيسية');
    expect(document.documentElement.dir).toBe('rtl');
    expect(document.documentElement.lang).toBe('ar');
    expect(localStorage.getItem('ged.langue')).toBe('ar');
  });

  it("applique la langue par défaut (compte ou institution) tant qu'aucun choix local n'existe", () => {
    service.langueParDefaut.set('ar');
    expect(service.langue()).toBe('ar');
    service.choisir('fr');
    expect(service.langue()).toBe('fr');
  });

  it('choisit le libellé arabe seulement en arabe et s’il est renseigné', () => {
    expect(service.libelle('Direction', 'مديرية')).toBe('Direction');
    service.choisir('ar');
    expect(service.libelle('Direction', 'مديرية')).toBe('مديرية');
    expect(service.libelle('Direction', '')).toBe('Direction');
  });

  it('garde des chiffres occidentaux en arabe', () => {
    service.choisir('ar');
    expect(service.locale()).toBe('ar-u-nu-latn');
  });

  it('conserve les paramètres {x} dans chaque traduction arabe', () => {
    const parametres = (texte: string) => (texte.match(/\{\w+\}/g) ?? []).sort().join();
    for (const cle of Object.keys(FR) as (keyof typeof FR)[]) {
      expect(parametres(AR[cle]), cle).toBe(parametres(FR[cle]));
    }
  });
});
