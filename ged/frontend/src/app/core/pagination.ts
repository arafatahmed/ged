import { Injectable, effect, inject } from '@angular/core';
import { MatPaginatorIntl } from '@angular/material/paginator';

import { TraductionService } from './traduction.service';

/** Libellés de la pagination Material dans la langue de l'interface. */
@Injectable()
export class PaginationTraduite extends MatPaginatorIntl {
  private readonly traduction = inject(TraductionService);

  constructor() {
    super();
    effect(() => {
      this.traduction.langue();
      this.firstPageLabel = this.traduction.t('pagination.premiere');
      this.lastPageLabel = this.traduction.t('pagination.derniere');
      this.nextPageLabel = this.traduction.t('pagination.suivante');
      this.previousPageLabel = this.traduction.t('pagination.precedente');
      this.itemsPerPageLabel = this.traduction.t('pagination.par_page');
      this.changes.next();
    });
  }

  override getRangeLabel = (page: number, taille: number, total: number): string => {
    if (total === 0) return this.traduction.t('pagination.vide');
    const debut = page * taille + 1;
    const fin = Math.min(total, (page + 1) * taille);
    return this.traduction.t('pagination.plage', { debut, fin, total });
  };
}
