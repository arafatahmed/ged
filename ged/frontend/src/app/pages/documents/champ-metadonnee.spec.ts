import { FormRecord } from '@angular/forms';

import { DefinitionMetadonnee } from '../../core/modeles';
import { controleMetadonnee, valeursMetadonnees } from './champ-metadonnee';

const definition = (
  code: string,
  nature: DefinitionMetadonnee['nature'],
  obligatoire = false,
): DefinitionMetadonnee => ({
  code,
  nature,
  obligatoire,
  libelle_fr: code,
  libelle_ar: '',
  valeurs_liste: [],
  ordre: 0,
  actif: true,
});

describe('Métadonnées personnalisées', () => {
  it('rend obligatoire le contrôle d’une métadonnée obligatoire', () => {
    expect(controleMetadonnee(definition('nature', 'liste', true)).hasError('required')).toBe(true);
    expect(controleMetadonnee(definition('note', 'texte')).valid).toBe(true);
    expect(controleMetadonnee(definition('montant', 'nombre'), 12).value).toBe('12');
  });

  it('omet les champs vides et convertit les nombres', () => {
    const definitions = [definition('montant', 'nombre'), definition('objet', 'texte'), definition('vide', 'texte')];
    const groupe = new FormRecord({
      montant: controleMetadonnee(definitions[0], '1250'),
      objet: controleMetadonnee(definitions[1], '  Achat  '),
      vide: controleMetadonnee(definitions[2], '   '),
    });
    expect(valeursMetadonnees(definitions, groupe)).toEqual({ montant: 1250, objet: 'Achat' });
  });
});
