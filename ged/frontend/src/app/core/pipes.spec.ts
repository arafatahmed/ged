import { TestBed } from '@angular/core/testing';

import { DateLocalePipe, TailleFichierPipe } from './pipes';
import { TraductionService } from './traduction.service';

describe('DateLocalePipe', () => {
  beforeEach(() => {
    localStorage.clear();
    TestBed.configureTestingModule({});
  });

  it('formate la date dans la langue courante et gère les valeurs absentes', () => {
    const pipe = TestBed.runInInjectionContext(() => new DateLocalePipe());
    expect(pipe.transform(null)).toBe('—');
    expect(pipe.transform('pas une date')).toBe('—');
    expect(pipe.transform('2026-05-03T10:00:00Z', 'court')).toBe('03/05/2026');
    TestBed.inject(TraductionService).choisir('ar');
    expect(pipe.transform('2026-05-03T10:00:00Z', 'court')).toMatch(/2026/);
  });
});

describe('TailleFichierPipe', () => {
  beforeEach(() => {
    localStorage.clear();
    TestBed.configureTestingModule({});
  });

  it('choisit l’unité et traduit son libellé', () => {
    const pipe = TestBed.runInInjectionContext(() => new TailleFichierPipe());
    expect(pipe.transform(null)).toBe('—');
    expect(pipe.transform(512)).toBe('512 o');
    expect(pipe.transform(1536)).toBe('1,5 Ko');
    expect(pipe.transform(5 * 1024 * 1024)).toBe('5 Mo');
    TestBed.inject(TraductionService).choisir('ar');
    expect(pipe.transform(5 * 1024 * 1024)).toContain('م.ب');
  });
});
