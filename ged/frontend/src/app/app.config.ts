import { provideHttpClient, withFetch, withInterceptors, withXsrfConfiguration } from '@angular/common/http';
import { ApplicationConfig, inject, provideAppInitializer, provideBrowserGlobalErrorListeners } from '@angular/core';
import { MatIconRegistry } from '@angular/material/icon';
import { MAT_FORM_FIELD_DEFAULT_OPTIONS } from '@angular/material/form-field';
import { MatPaginatorIntl } from '@angular/material/paginator';
import { provideRouter, withComponentInputBinding, withInMemoryScrolling, withViewTransitions } from '@angular/router';

import { routes } from './app.routes';
import { entetesIntercepteur, securiteIntercepteur } from './core/intercepteurs';
import { PaginationTraduite } from './core/pagination';
import { SessionService } from './core/session.service';

export const appConfig: ApplicationConfig = {
  providers: [
    provideBrowserGlobalErrorListeners(),
    provideRouter(
      routes,
      withComponentInputBinding(),
      withInMemoryScrolling({ scrollPositionRestoration: 'top' }),
      // Transitions animées entre pages (API View Transitions ; sans effet si le navigateur ne la gère pas).
      withViewTransitions({ skipInitialTransition: true }),
    ),
    provideHttpClient(
      withFetch(),
      // Jeton CSRF de Django : cookie « csrftoken » renvoyé dans l'en-tête X-CSRFToken.
      withXsrfConfiguration({ cookieName: 'csrftoken', headerName: 'X-CSRFToken' }),
      withInterceptors([entetesIntercepteur, securiteIntercepteur]),
    ),
    { provide: MAT_FORM_FIELD_DEFAULT_OPTIONS, useValue: { appearance: 'outline' } },
    { provide: MatPaginatorIntl, useClass: PaginationTraduite },
    provideAppInitializer(() => {
      inject(MatIconRegistry).setDefaultFontSetClass('material-symbols-outlined');
      // Charge la session (et le cookie CSRF) avant le premier affichage ; une erreur réseau n'empêche pas le démarrage.
      return inject(SessionService)
        .pret()
        .then(
          () => undefined,
          () => undefined,
        );
    }),
  ],
};
