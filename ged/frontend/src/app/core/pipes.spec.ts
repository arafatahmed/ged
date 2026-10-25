import { TestBed } from '@angular/core/testing';

import { DateLocalePipe } from './pipes';
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
