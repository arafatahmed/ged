import { inject } from '@angular/core';
import { CanActivateFn, Router } from '@angular/router';

import { Droits, DroitsDocuments } from './modeles';
import { SessionService } from './session.service';

/** Pages réservées aux utilisateurs connectés ; impose le changement de mot de passe ou la MFA en attente. */
export const authentifieGarde: CanActivateFn = async (_route, etat) => {
  const session = inject(SessionService);
  const router = inject(Router);
  await session.pret().catch(() => null);
  if (!session.authentifie()) {
    return router.createUrlTree(['/connexion'], { queryParams: etat.url !== '/' ? { suivant: etat.url } : {} });
  }
  const imposee = session.pageImposee();
  if (imposee && !etat.url.startsWith(imposee)) {
    return router.parseUrl(imposee);
  }
  return true;
};

/** La page de connexion n'a pas de sens pour un utilisateur déjà connecté. */
export const anonymeGarde: CanActivateFn = async () => {
  // inject() n'est permis qu'avant le premier await.
  const session = inject(SessionService);
  const router = inject(Router);
  await session.pret().catch(() => null);
  return session.authentifie() ? router.parseUrl('/') : true;
};

/** Rubrique d'administration : masquée côté interface, le serveur refuse de toute façon sans le droit. */
export function droitGarde(droit: keyof Droits): CanActivateFn {
  return () => {
    const session = inject(SessionService);
    return session.droits()[droit] ? true : inject(Router).parseUrl('/acces-refuse');
  };
}

/** Pages des documents : même principe, selon les droits documentaires de la session. */
export function documentsGarde(droit: keyof DroitsDocuments): CanActivateFn {
  return () => {
    const session = inject(SessionService);
    return session.documents()[droit] ? true : inject(Router).parseUrl('/acces-refuse');
  };
}
