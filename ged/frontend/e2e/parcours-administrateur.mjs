// Parcours de recette de bout en bout, joué dans Chromium avec Playwright.
//
// Prérequis : une base neuve avec l'institution et le premier administrateur
// (commandes initialiser_ged et creer_administrateur), Django et le frontend démarrés.
//
//   GED_URL=http://localhost:4200 GED_MOT_DE_PASSE=<mot de passe temporaire> \
//   CHROMIUM=/chemin/vers/chrome npm run e2e
//
// Variables facultatives : GED_IDENTIFIANT (admin par défaut), GED_CAPTURES (dossier des captures).

import { createHmac } from 'node:crypto';
import { mkdirSync } from 'node:fs';
import { chromium } from 'playwright-core';

const URL_GED = process.env.GED_URL ?? 'http://localhost:4200';
const IDENTIFIANT = process.env.GED_IDENTIFIANT ?? 'admin';
const MOT_DE_PASSE = process.env.GED_MOT_DE_PASSE;
const CAPTURES = process.env.GED_CAPTURES ?? 'e2e/captures';
const NOUVEAU = 'Nouveau-Mot-De-Passe-Recette-2026';

if (!MOT_DE_PASSE) {
  console.error('GED_MOT_DE_PASSE est obligatoire (mot de passe temporaire affiché par creer_administrateur).');
  process.exit(2);
}

function base32(texte) {
  const alphabet = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ234567';
  let bits = '';
  for (const c of texte.replace(/\s|=/g, '')) bits += alphabet.indexOf(c).toString(2).padStart(5, '0');
  const octets = [];
  for (let i = 0; i + 8 <= bits.length; i += 8) octets.push(parseInt(bits.slice(i, i + 8), 2));
  return Buffer.from(octets);
}

function codeTotp(secret) {
  const compteur = Buffer.alloc(8);
  compteur.writeBigUInt64BE(BigInt(Math.floor(Date.now() / 30000)));
  const empreinte = createHmac('sha1', base32(secret)).update(compteur).digest();
  const decalage = empreinte[empreinte.length - 1] & 15;
  return String((empreinte.readUInt32BE(decalage) & 0x7fffffff) % 1_000_000).padStart(6, '0');
}

const etapes = [];
const navigateur = await chromium.launch({ executablePath: process.env.CHROMIUM, args: ['--no-sandbox'] });
const page = await navigateur.newPage({ viewport: { width: 1360, height: 860 } });
const erreurs = [];
page.on('pageerror', (e) => erreurs.push(e.message));
page.on('console', (m) => m.type() === 'error' && /Content Security Policy|NG0/.test(m.text()) && erreurs.push(m.text()));
mkdirSync(CAPTURES, { recursive: true });

async function etape(nom, action) {
  await action();
  await page.waitForTimeout(500);
  await page.screenshot({ path: `${CAPTURES}/${String(etapes.length + 1).padStart(2, '0')}-${nom}.png` });
  etapes.push(nom);
  console.log(`✔ ${nom}`);
}

try {
  await etape('connexion', async () => {
    await page.goto(`${URL_GED}/`);
    await page.waitForURL('**/connexion**');
  });
  await etape('enrolement-mfa', async () => {
    await page.fill('input[formcontrolname=identifiant]', IDENTIFIANT);
    await page.fill('input[formcontrolname=mot_de_passe]', MOT_DE_PASSE);
    await page.click('button[type=submit]');
    await page.waitForSelector('p.secret code');
  });
  await etape('codes-de-secours', async () => {
    const secret = (await page.textContent('p.secret code')).trim();
    await page.fill('input.champ-code', codeTotp(secret));
    await page.waitForSelector('.reussite');
  });
  await etape('mot-de-passe', async () => {
    await page.click('.reussite button');
    await page.waitForURL('**/compte/mot-de-passe');
    await page.fill('input[formcontrolname=ancien]', MOT_DE_PASSE);
    await page.fill('input[formcontrolname=nouveau]', NOUVEAU);
    await page.fill('input[formcontrolname=confirmation]', NOUVEAU);
    await page.click('form button[type=submit]');
    await page.waitForURL('**/compte');
  });
  await etape('creation-unite', async () => {
    await page.goto(`${URL_GED}/administration/organisation`);
    await page.click('ged-entete-page button');
    await page.waitForTimeout(600);
    await page.click('mat-dialog-container mat-select[formcontrolname=type]');
    await page.getByRole('option', { name: 'Direction', exact: true }).click();
    await page.click('mat-dialog-container mat-select[formcontrolname=parent]');
    await page.locator('mat-option').first().click();
    await page.fill('mat-dialog-container input[formcontrolname=code]', 'recette');
    await page.fill('mat-dialog-container input[formcontrolname=sigle]', 'REC');
    await page.fill('mat-dialog-container input[formcontrolname=libelle_fr]', 'Direction de recette');
    await page.click('mat-dialog-actions button.mat-mdc-unelevated-button');
    await page.waitForSelector('mat-dialog-container', { state: 'detached' });
    await page.click('button:has-text("Tout déplier")');
    await page.waitForSelector('text=Direction de recette');
  });
  await etape('creation-compte', async () => {
    await page.goto(`${URL_GED}/administration/utilisateurs`);
    await page.click('ged-entete-page button');
    await page.waitForSelector('mat-dialog-container input[formcontrolname=identifiant]');
    // Laisse le dialogue terminer son ouverture (il place le focus sur le premier champ).
    await page.waitForTimeout(600);
    await page.fill('mat-dialog-container input[formcontrolname=identifiant]', 'agent.recette');
    await page.fill('mat-dialog-container input[formcontrolname=nom]', 'Recette');
    await page.fill('mat-dialog-container input[formcontrolname=prenom]', 'Agent');
    await page.click('mat-dialog-container mat-select[formcontrolname=unite]');
    await page.click('mat-option:has-text("REC")');
    await page.click('mat-dialog-container mat-select[formcontrolname=role]');
    await page.click('mat-option:has-text("bureau")');
    await page.click('mat-dialog-actions button.mat-mdc-unelevated-button');
    await page.waitForSelector('ged-dialogue-secret');
    await page.click('ged-dialogue-secret button[mat-dialog-close]');
    await page.waitForURL('**/administration/utilisateurs/*');
  });
  await etape('interface-arabe', async () => {
    await page.click('mat-button-toggle[value=ar] button');
    await page.locator('html[dir=rtl]').waitFor({ state: 'attached' });
  });
  await etape('deconnexion', async () => {
    await page.click('button.profil');
    await page.locator('.mat-mdc-menu-content button').last().click();
    await page.waitForURL('**/connexion');
  });
  if (erreurs.length) throw new Error(`Erreurs dans la page :\n${erreurs.join('\n')}`);
  console.log(`Parcours réussi : ${etapes.length} étapes, captures dans ${CAPTURES}.`);
} catch (erreur) {
  await page.screenshot({ path: `${CAPTURES}/echec.png` });
  console.error(`✘ Échec après « ${etapes.at(-1) ?? 'démarrage'} » : ${erreur.message}`);
  process.exitCode = 1;
} finally {
  await navigateur.close();
}
