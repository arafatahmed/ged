import { HttpErrorResponse, HttpInterceptorFn } from '@angular/common/http';
import { inject } from '@angular/core';
import { Router } from '@angular/router';
import { catchError, throwError } from 'rxjs';

import { SessionService } from './session.service';
import { TraductionService } from './traduction.service';

/** Transmet la langue de l'interface : les messages d'erreur de l'API arrivent traduits. */
export const entetesIntercepteur: HttpInterceptorFn = (requete, suivant) => {
  const langue = inject(TraductionService).langue();
  return suivant(requete.clone({ setHeaders: { 'X-Langue': langue, 'X-Requested-With': 'XMLHttpRequest' } }));
};

/** Réagit aux refus de sécurité de l'API : session expirée, mot de passe à changer, MFA à activer. */
export const securiteIntercepteur: HttpInterceptorFn = (requete, suivant) => {
  const router = inject(Router);
  const session = inject(SessionService);
  return suivant(requete).pipe(
    catchError((erreur: HttpErrorResponse) => {
      const code = (erreur.error as { code?: string } | null)?.code;
      if (erreur.status === 401 && code === 'session_expiree') {
        session.oublier();
        void router.navigate(['/connexion'], { queryParams: { expiree: 1 } });
      } else if (erreur.status === 403 && code === 'changement_mot_de_passe_requis') {
        void session.recharger().then(() => router.navigateByUrl('/compte/mot-de-passe'));
      } else if (erreur.status === 403 && code === 'mfa_requise') {
        void session.recharger().then(() => router.navigateByUrl('/compte/double-authentification'));
      }
      return throwError(() => erreur);
    }),
  );
};
