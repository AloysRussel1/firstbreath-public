// Saisie -> format du schéma (lib/saisie.js), avec les vraies définitions de shared/schema_champs.json.
// Lancer : npm test (node --test, sans dépendance).
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { test } from 'node:test'
import { erreurServeur, normaliserSaisie, texteInitial } from '../src/lib/saisie.js'

const schema = JSON.parse(readFileSync(new URL('../../shared/schema_champs.json', import.meta.url), 'utf-8'))
const champs = Object.values(schema.pages).flatMap((p) => [...p.champs, ...(p.visites?.champs || [])])
const def = (cle) => {
  const d = champs.find((c) => c.cle === cle)
  assert.ok(d, `${cle} absent du schéma`)
  return d
}
const ok = (d, brut, attendu) => assert.deepEqual(normaliserSaisie(d, brut), { valeur: attendu }, `« ${brut} »`)
const ko = (d, brut, cle) => assert.equal(normaliserSaisie(d, brut).erreur?.cle, `erreurSaisie.${cle}`, `« ${brut} »`)

test('date : JJ/MM/AAAA converti en AAAA-MM-JJ, date impossible refusée', () => {
  const d = def('grossesse.ddr')
  assert.equal(d.type, 'date')
  ok(d, '15/01/2026', '2026-01-15')
  ok(d, '5/1/2026', '2026-01-05')
  ok(d, '15-01-2026', '2026-01-15')
  ok(d, '15.01.26', '2026-01-15')
  ok(d, ' 2026-01-15 ', '2026-01-15')
  ko(d, '31/02/2026', 'date')
  ko(d, '2026/15/01', 'date')
  ko(d, 'janvier', 'date')
  ko(d, '', 'vide')
  assert.equal(texteInitial(d, '2026-01-15'), '15/01/2026')
})

test('nombre : virgule décimale en point, unité ignorée, entier strict', () => {
  const decimal = def('poids_kg')
  assert.equal(decimal.type, 'decimal')
  ok(decimal, '62,5', 62.5)
  ok(decimal, '62.5 kg', 62.5)
  ok(decimal, '1 250', 1250)
  ok(decimal, 70, 70)
  ko(decimal, 'abc', 'decimal')
  ko(decimal, '6,2,5', 'decimal')
  const entier = def('profil.age')
  assert.equal(entier.type, 'entier')
  ok(entier, '28', 28)
  ok(entier, '28 ans', 28)
  ok(entier, '28,0', 28)
  ko(entier, '28,5', 'entier')
  ko(entier, 'vingt', 'entier')
})

test('tension : « 11/7 » (cmHg) converti en « 110/70 »', () => {
  const d = def('tension')
  assert.equal(d.type, 'tension')
  ok(d, '11/7', '110/70')
  ok(d, '11,5/7', '115/70')
  ok(d, '110/70', '110/70')
  ok(d, '110 / 70 mmHg', '110/70')
  ok(d, '12-8', '120/80')
  ko(d, '110', 'tension')
  ko(d, '110/', 'tension')
  ko(d, '1100/70', 'tension')
})

test('choix : code ou libellé lisible converti en code du schéma', () => {
  const d = def('identification.type_etablissement')
  assert.equal(d.type, 'choix')
  ok(d, 'CSC', 'CSC')
  ok(d, 'csc', 'CSC')
  const mode = def('identification.mode_couverture')
  ok(mode, 'Mobile', 'MOBILE')
  ko(d, 'Hôpital', 'choix')
})

test('liste de cases : codes ou libellés, doublons retirés, case inconnue refusée', () => {
  const d = def('identification.types_risque')
  assert.equal(d.type, 'liste_choix')
  ok(d, ['HTA', 'ANEMIE'], ['HTA', 'ANEMIE'])
  ok(d, 'pré-éclampsie, hta, HTA', ['PRE_ECLAMPSIE', 'HTA'])
  ok(d, [], [])
  ko(d, ['HTA', 'ASTHME'], 'liste')
})

test('oui/non et texte : jamais de téléphone ni de CIN', () => {
  const b = def('identification.grossesse_a_risque')
  ok(b, true, true)
  ok(b, 'non', false)
  ko(b, 'peut-être', 'booleen')
  const texte = def('identification.numero_fiche')
  ok(texte, ' 2026-A16-002 ', '2026-A16-002')
  ko(texte, '06 12 34 56 78', 'identifiant')
  ko(texte, 'AB123456', 'identifiant')
})

test('refus du serveur traduit en message simple selon le type', () => {
  assert.equal(erreurServeur(def('grossesse.ddr'), 'Invalid field value.').cle, 'erreurSaisie.date')
  assert.equal(erreurServeur(def('tension'), 'Invalid field value.').cle, 'erreurSaisie.tension')
  assert.equal(erreurServeur(def('identification.numero_fiche'), 'Direct patient identifiers cannot be stored.').cle, 'erreurSaisie.identifiant')
  assert.equal(erreurServeur(def('identification.numero_fiche'), 'Invalid field value.').cle, 'msg.valeurRefusee')
  // « vaccination » contient « cin » : ce n'est pas un refus d'identifiant.
  assert.equal(erreurServeur(def('grossesse.ddr'), "Invalid field value: vaccination.x : valeur 'a' ne respecte pas le type date").cle, 'erreurSaisie.date')
})
