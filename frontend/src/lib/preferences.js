// Préférences locales de l'appareil (aucune donnée de patiente).
const CLE_QUALITE = 'firstbreath-controle-qualite'

export function controleQualiteActif() {
  try { return localStorage.getItem(CLE_QUALITE) !== '0' } catch { return true }
}

export function definirControleQualite(actif) {
  try { localStorage.setItem(CLE_QUALITE, actif ? '1' : '0') } catch { /* stockage indisponible */ }
}

// Démonstration : simule une panne du système de santé central pendant la synchronisation.
const CLE_PANNE = 'firstbreath-panne-centrale'
export function panneCentraleSimulee() {
  try { return localStorage.getItem(CLE_PANNE) === '1' } catch { return false }
}
export function definirPanneCentrale(active) {
  try { localStorage.setItem(CLE_PANNE, active ? '1' : '0') } catch { /* stockage indisponible */ }
}

// Clés locales de l'application, effacées avec les données chiffrées (le profil et la langue sont conservés).
export const CLES_LOCALES = ['firstbreath-session']
