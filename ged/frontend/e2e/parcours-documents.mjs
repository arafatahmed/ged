// Parcours de recette des documents (lot 3), joué dans Chromium avec Playwright.
//
// Prérequis : la pile démarrée, un type de document dont une métadonnée « urgence » (liste
// « normale », « urgente ») et un agent qui peut créer des documents, avec son mot de passe temporaire.
//
//   GED_URL=https://localhost:8443 GED_IDENTIFIANT=agent.demo GED_MOT_DE_PASSE=<mot de passe temporaire> \
//   CHROMIUM=/chemin/vers/chrome node e2e/parcours-documents.mjs
//
// Variable facultative : GED_CAPTURES (dossier des captures).

import { mkdirSync } from 'node:fs';
import { deflateSync } from 'node:zlib';
import { chromium } from 'playwright-core';

const URL_GED = process.env.GED_URL ?? 'https://localhost:8443';
const IDENTIFIANT = process.env.GED_IDENTIFIANT ?? 'agent.demo';
const MOT_DE_PASSE = process.env.GED_MOT_DE_PASSE;
const CAPTURES = process.env.GED_CAPTURES ?? 'e2e/captures-documents';
const NOUVEAU = 'Nouveau-Mot-De-Passe-Recette-2026';

if (!MOT_DE_PASSE) {
  console.error('GED_MOT_DE_PASSE est obligatoire (mot de passe temporaire de l’agent).');
  process.exit(2);
}

/** Image PNG valide (dégradé), pour vérifier l'aperçu dans la fiche. */
function imagePng(largeur = 480, hauteur = 240) {
  const crcTable = Array.from({ length: 256 }, (_v, n) => {
    let c = n;
    for (let k = 0; k < 8; k++) c = c & 1 ? 0xedb88320 ^ (c >>> 1) : c >>> 1;
    return c >>> 0;
  });
  const crc = (octets) => {
    let c = 0xffffffff;
    for (const o of octets) c = crcTable[(c ^ o) & 0xff] ^ (c >>> 8);
    return (c ^ 0xffffffff) >>> 0;
  };
  const bloc = (type, donnees) => {
    const longueur = Buffer.alloc(4);
    longueur.writeUInt32BE(donnees.length);
    const corps = Buffer.concat([Buffer.from(type), donnees]);
    const somme = Buffer.alloc(4);
    somme.writeUInt32BE(crc(corps));
    return Buffer.concat([longueur, corps, somme]);
  };
  const entete = Buffer.alloc(13);
  entete.writeUInt32BE(largeur, 0);
  entete.writeUInt32BE(hauteur, 4);
  entete.set([8, 2, 0, 0, 0], 8);
  const lignes = [];
  for (let y = 0; y < hauteur; y++) {
    const ligne = Buffer.alloc(1 + largeur * 3);
    for (let x = 0; x < largeur; x++) ligne.set([31 + (x * 120) / largeur, 78 + (y * 80) / hauteur, 121], 1 + x * 3);
    lignes.push(ligne);
  }
  return Buffer.concat([
    Buffer.from([0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a]),
    bloc('IHDR', entete),
    bloc('IDAT', deflateSync(Buffer.concat(lignes))),
    bloc('IEND', Buffer.alloc(0)),
  ]);
}

const etapes = [];
const navigateur = await chromium.launch({ executablePath: process.env.CHROMIUM, args: ['--no-sandbox'] });
const page = await navigateur.newPage({ viewport: { width: 1360, height: 860 }, ignoreHTTPSErrors: true });
const erreurs = [];
page.on('pageerror', (e) => erreurs.push(e.message));
page.on('console', (m) => m.type() === 'error' && /Content Security Policy|NG0/.test(m.text()) && erreurs.push(m.text()));
mkdirSync(CAPTURES, { recursive: true });

async function etape(nom, action) {
  await action();
  await page.waitForTimeout(600);
  await page.screenshot({ path: `${CAPTURES}/${String(etapes.length + 1).padStart(2, '0')}-${nom}.png` });
  etapes.push(nom);
  console.log(`✔ ${nom}`);
}

try {
  await etape('changement-mot-de-passe', async () => {
    await page.goto(`${URL_GED}/connexion`);
    await page.fill('input[formcontrolname=identifiant]', IDENTIFIANT);
    await page.fill('input[formcontrolname=mot_de_passe]', MOT_DE_PASSE);
    await page.click('button[type=submit]');
    await page.waitForURL('**/compte/mot-de-passe');
    await page.fill('input[formcontrolname=ancien]', MOT_DE_PASSE);
    await page.fill('input[formcontrolname=nouveau]', NOUVEAU);
    await page.fill('input[formcontrolname=confirmation]', NOUVEAU);
    await page.click('form button[type=submit]');
    await page.waitForURL('**/compte');
  });
  await etape('liste-documents', async () => {
    await page.click('a[href="/documents"]');
    await page.waitForURL('**/documents');
    await page.waitForSelector('tr.mat-mdc-row');
  });
  await etape('nouveau-document', async () => {
    await page.click('a[href="/documents/nouveau"]');
    await page.waitForSelector('ged-depot-fichier');
    await page.setInputFiles('ged-depot-fichier input[type=file]', {
      name: 'organigramme.png',
      mimeType: 'image/png',
      buffer: imagePng(),
    });
    await page.fill('input[formcontrolname=titre]', 'Organigramme de la direction');
    await page.fill('textarea[formcontrolname=objet]', 'Organisation des services au 1er novembre.');
    const motCle = page.locator('mat-chip-grid input');
    await motCle.fill('organisation');
    await motCle.press('Enter');
    await page.locator('ged-champ-metadonnee mat-select').click();
    await page.getByRole('option', { name: 'urgente', exact: true }).click();
    await page.locator('ged-champ-metadonnee input').first().fill('Toutes les directions');
  });
  await etape('fiche-document', async () => {
    await page.click('button:has-text("Enregistrer le document")');
    await page.waitForURL(/\/documents\/[0-9a-f-]{36}$/);
    // La fiche se recharge seule pendant l'analyse antivirus.
    await page.waitForSelector('.pastilles ged-etat-fichier', { state: 'detached', timeout: 120000 });
    // La CSP de l'application interdit l'évaluation de code : pas de waitForFunction ici.
    const reponse = page.waitForResponse((r) => r.url().includes('/apercu/'));
    await page.click('button:has(mat-icon:text-is("visibility"))');
    if ((await reponse).status() !== 200) throw new Error(`aperçu : HTTP ${(await reponse).status()}`);
    await page.locator('.apercu img').waitFor({ state: 'visible' });
    await page.waitForTimeout(400);
    const cadre = await page.locator('.apercu img').boundingBox();
    if (!cadre || cadre.height < 50) throw new Error('aperçu : image non affichée');
  });
  await etape('fiche-arabe', async () => {
    await page.click('mat-button-toggle[value=ar] button');
    await page.locator('html[dir=rtl]').waitFor({ state: 'attached' });
  });
  await etape('liste-mobile', async () => {
    await page.setViewportSize({ width: 390, height: 844 });
    await page.goto(`${URL_GED}/documents`);
    await page.waitForSelector('tr.mat-mdc-row');
  });
} catch (erreur) {
  await page.screenshot({ path: `${CAPTURES}/echec.png` });
  console.error(`✘ échec après ${etapes.length} étape(s) : ${erreur.message}`);
  erreurs.push(erreur.message);
} finally {
  await navigateur.close();
}

if (erreurs.length) {
  console.error('Erreurs :', erreurs);
  process.exit(1);
}
console.log(`Parcours des documents réussi (${etapes.length} étapes), captures dans ${CAPTURES}.`);
