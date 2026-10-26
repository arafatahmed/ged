import { Pipe, PipeTransform, inject } from '@angular/core';

import { Cle } from '../i18n/fr';
import { TraductionService } from './traduction.service';

/** Traduction : {{ 'cle' | t }} ou {{ 'cle' | t: { nom: valeur } }}. Recalculée au changement de langue. */
@Pipe({ name: 't', pure: false })
export class TraduirePipe implements PipeTransform {
  private readonly traduction = inject(TraductionService);

  transform(cle: Cle, parametres?: Record<string, string | number>): string {
    return this.traduction.t(cle, parametres);
  }
}

/** Libellé bilingue : {{ objet.libelle_fr | bilingue: objet.libelle_ar }}. */
@Pipe({ name: 'bilingue', pure: false })
export class BilinguePipe implements PipeTransform {
  private readonly traduction = inject(TraductionService);

  transform(francais: string | null | undefined, arabe: string | null | undefined): string {
    return this.traduction.libelle(francais, arabe);
  }
}

const FORMATS: Record<string, Intl.DateTimeFormatOptions> = {
  date: { day: 'numeric', month: 'long', year: 'numeric' },
  court: { day: '2-digit', month: '2-digit', year: 'numeric' },
  dateHeure: { day: 'numeric', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit' },
};

/** Date dans la langue de l'interface : {{ valeur | dateLocale: 'dateHeure' }}. */
@Pipe({ name: 'dateLocale', pure: false })
export class DateLocalePipe implements PipeTransform {
  private readonly traduction = inject(TraductionService);

  transform(valeur: string | Date | null | undefined, format: keyof typeof FORMATS = 'date'): string {
    if (!valeur) return '—';
    const date = valeur instanceof Date ? valeur : new Date(valeur);
    if (Number.isNaN(date.getTime())) return '—';
    return new Intl.DateTimeFormat(this.traduction.locale(), FORMATS[format]).format(date);
  }
}

/** Taille d'un fichier lisible : {{ octets | tailleFichier }} (unités traduites). */
@Pipe({ name: 'tailleFichier', pure: false })
export class TailleFichierPipe implements PipeTransform {
  private readonly traduction = inject(TraductionService);

  transform(octets: number | null | undefined): string {
    if (octets === null || octets === undefined) return '—';
    const unites = ['taille.o', 'taille.ko', 'taille.mo', 'taille.go'] as const;
    let valeur = octets;
    let rang = 0;
    while (valeur >= 1024 && rang < unites.length - 1) {
      valeur /= 1024;
      rang++;
    }
    const nombre = new Intl.NumberFormat(this.traduction.locale(), { maximumFractionDigits: rang ? 1 : 0 }).format(
      valeur,
    );
    return `${nombre} ${this.traduction.t(unites[rang])}`;
  }
}
