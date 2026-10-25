import { TestBed } from '@angular/core/testing';

import { PaginationTraduite } from './pagination';
import { TraductionService } from './traduction.service';

describe('PaginationTraduite', () => {
  it('affiche la plage dans la langue courante', () => {
    localStorage.clear();
    TestBed.configureTestingModule({ providers: [PaginationTraduite] });
    const pagination = TestBed.inject(PaginationTraduite);
    expect(pagination.getRangeLabel(1, 25, 60)).toBe('26 – 50 sur 60');
    expect(pagination.getRangeLabel(0, 25, 0)).toBe('0 sur 0');
    TestBed.inject(TraductionService).choisir('ar');
    expect(pagination.getRangeLabel(1, 25, 60)).toBe('26 – 50 من 60');
  });
});
