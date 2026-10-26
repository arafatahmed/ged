import { Routes } from '@angular/router';

import { anonymeGarde, authentifieGarde, documentsGarde, droitGarde } from './core/gardes';

export const routes: Routes = [
  {
    path: 'connexion',
    canActivate: [anonymeGarde],
    loadComponent: () => import('./pages/connexion/connexion').then((m) => m.Connexion),
  },
  {
    path: '',
    canActivate: [authentifieGarde],
    canActivateChild: [authentifieGarde],
    loadComponent: () => import('./coque/coque').then((m) => m.Coque),
    children: [
      { path: '', loadComponent: () => import('./pages/accueil/accueil').then((m) => m.Accueil) },
      { path: 'compte', loadComponent: () => import('./pages/compte/compte').then((m) => m.Compte) },
      {
        path: 'compte/mot-de-passe',
        loadComponent: () => import('./pages/compte/mot-de-passe').then((m) => m.MotDePasse),
      },
      {
        path: 'compte/double-authentification',
        loadComponent: () => import('./pages/compte/double-authentification').then((m) => m.DoubleAuthentification),
      },
      {
        path: 'documents',
        canActivate: [documentsGarde('consulter')],
        loadComponent: () => import('./pages/documents/documents').then((m) => m.Documents),
      },
      {
        path: 'documents/nouveau',
        canActivate: [documentsGarde('creer')],
        loadComponent: () => import('./pages/documents/nouveau-document').then((m) => m.NouveauDocument),
      },
      {
        path: 'documents/:uuid',
        canActivate: [documentsGarde('consulter')],
        loadComponent: () => import('./pages/documents/document').then((m) => m.FicheDocument),
      },
      {
        path: 'administration',
        children: [
          { path: '', pathMatch: 'full', redirectTo: '/' },
          {
            path: 'organisation',
            canActivate: [droitGarde('organisation')],
            loadComponent: () => import('./pages/administration/organisation').then((m) => m.Organisation),
          },
          {
            path: 'postes',
            canActivate: [droitGarde('organisation')],
            loadComponent: () => import('./pages/administration/postes').then((m) => m.Postes),
          },
          {
            path: 'utilisateurs',
            canActivate: [droitGarde('utilisateurs')],
            loadComponent: () => import('./pages/administration/utilisateurs').then((m) => m.Utilisateurs),
          },
          {
            path: 'utilisateurs/:uuid',
            canActivate: [droitGarde('utilisateurs')],
            loadComponent: () => import('./pages/administration/utilisateur').then((m) => m.Utilisateur),
          },
          {
            path: 'roles',
            canActivate: [droitGarde('roles')],
            loadComponent: () => import('./pages/administration/roles').then((m) => m.Roles),
          },
          {
            path: 'types-document',
            canActivate: [droitGarde('types_document')],
            loadComponent: () => import('./pages/administration/types-document').then((m) => m.TypesDocument),
          },
          {
            path: 'connexions',
            canActivate: [droitGarde('connexions')],
            loadComponent: () => import('./pages/administration/connexions').then((m) => m.Connexions),
          },
        ],
      },
      {
        path: 'acces-refuse',
        loadComponent: () => import('./pages/erreurs').then((m) => m.PageErreur),
        data: { code: '403', icone: 'block', titre: 'erreur.refuse_titre', message: 'erreur.refuse_message' },
      },
      { path: '**', loadComponent: () => import('./pages/erreurs').then((m) => m.PageErreur) },
    ],
  },
];
