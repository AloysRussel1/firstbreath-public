// Saisie de la sage-femme -> valeur au format du schéma (shared/valider.py), avant tout envoi au serveur.
// normaliserSaisie renvoie { valeur } ou { erreur: { cle } } (clé i18n « erreurSaisie.* », en français simple).

const TELEPHONE = /\b0[5-7](?:[ .-]?\d{2}){4}\b/
const CIN = /\b[A-Z]{1,2}\d{5,6}\b/
const ESPACES = /\s/g // \s couvre aussi les espaces insécables
// Unité recopiée après un nombre (« 38,5 kg », « 39 SA », « 12 % ») : ignorée.
const UNITE = /[a-zA-Zµ°%/]+\.?$/

const refus = (cle) => ({ erreur: { cle: `erreurSaisie.${cle}` } })
const sansAccent = (s) => String(s).normalize('NFD').replace(/\p{M}/gu, '').toLowerCase().replace(/[\s_'’-]+/g, ' ').trim()

function nombre(brut) {
  const s = String(brut).replace(ESPACES, '').replace(UNITE, '').replace(',', '.')
  return /^-?\d+(\.\d+)?$/.test(s) ? Number(s) : null
}

// JJ/MM/AAAA (aussi JJ-MM-AAAA, JJ.MM.AAAA, année sur 2 chiffres) ou AAAA-MM-JJ -> AAAA-MM-JJ, date réelle.
export function normaliserDate(brut) {
  const s = String(brut).trim()
  let j, m, a
  let r = /^(\d{4})-(\d{1,2})-(\d{1,2})$/.exec(s)
  if (r) [, a, m, j] = r
  else if ((r = /^(\d{1,2})[/.-](\d{1,2})[/.-](\d{2}|\d{4})$/.exec(s))) [, j, m, a] = r
  else return null
  if (a.length === 2) a = `20${a}`
  const iso = `${a}-${m.padStart(2, '0')}-${j.padStart(2, '0')}`
  const d = new Date(`${iso}T00:00:00Z`)
  return !Number.isNaN(d.getTime()) && d.toISOString().slice(0, 10) === iso ? iso : null
}

// « 110/70 », « 110 / 70 », « 110-70 » ; en centimètres de mercure (« 11/7 », « 11,5/7 ») -> « 110/70 », « 115/70 ».
export function normaliserTension(brut) {
  const r = /^(\d{1,3}(?:[.,]\d)?)\s*(?:\/|-|sur)\s*(\d{1,3}(?:[.,]\d)?)\s*(?:mm\s*hg|cm\s*hg)?$/i.exec(String(brut).trim())
  if (!r) return null
  let [s, d] = [r[1], r[2]].map((x) => Number(x.replace(',', '.')))
  if (s < 30) s = Math.round(s * 10)
  if (d < 20) d = Math.round(d * 10)
  if (!Number.isInteger(s) || !Number.isInteger(d)) return null
  const v = `${s}/${d}`
  return /^\d{2,3}\/\d{2,3}$/.test(v) ? v : null
}

// Choix : le code du schéma, ou son libellé lisible (« csc », « Pre eclampsie », « pré-éclampsie »).
function codeChoix(definition, brut) {
  const cible = sansAccent(brut)
  return (definition?.choix || []).find((c) => sansAccent(c) === cible) ?? null
}

export function normaliserSaisie(definition, brut) {
  const type = definition?.type || 'texte'
  if (type === 'liste_choix') {
    const elements = Array.isArray(brut) ? brut : String(brut ?? '').split(/[,;]/).map((x) => x.trim()).filter(Boolean)
    const codes = elements.map((x) => codeChoix(definition, x))
    return codes.includes(null) ? refus('liste') : { valeur: [...new Set(codes)] }
  }
  if (type === 'liste_objets') return Array.isArray(brut) ? { valeur: brut } : refus('vide')
  if (type === 'booleen') {
    if (typeof brut === 'boolean') return { valeur: brut }
    const s = sansAccent(brut ?? '')
    if (['oui', 'yes', 'vrai', 'true', '1'].includes(s)) return { valeur: true }
    if (['non', 'no', 'faux', 'false', '0'].includes(s)) return { valeur: false }
    return refus('booleen')
  }
  if (brut === null || brut === undefined || String(brut).trim() === '') return refus('vide')
  if (type === 'entier') {
    const n = typeof brut === 'number' ? brut : nombre(brut)
    return Number.isInteger(n) ? { valeur: n } : refus('entier')
  }
  if (type === 'decimal') {
    const n = typeof brut === 'number' ? brut : nombre(brut)
    return n !== null && Number.isFinite(n) ? { valeur: n } : refus('decimal')
  }
  if (type === 'date') {
    const v = normaliserDate(brut)
    return v ? { valeur: v } : refus('date')
  }
  if (type === 'tension') {
    const v = normaliserTension(brut)
    return v ? { valeur: v } : refus('tension')
  }
  if (type === 'choix') {
    const v = codeChoix(definition, brut)
    return v ? { valeur: v } : refus('choix')
  }
  const texte = String(brut).trim()
  // Jamais de téléphone ni de CIN dans le dossier (même règle que le serveur).
  return TELEPHONE.test(texte) || CIN.test(texte) ? refus('identifiant') : { valeur: texte }
}

// Erreur du serveur (422) pour une valeur déjà normalisée : même message simple que la saisie.
export function erreurServeur(definition, detail = '') {
  if (/identifier|t[ée]l[ée]phone/i.test(detail) || /\bCIN\b/.test(detail)) return { cle: 'erreurSaisie.identifiant' }
  const type = definition?.type
  const parType = { date: 'date', entier: 'entier', decimal: 'decimal', tension: 'tension', choix: 'choix', liste_choix: 'liste', booleen: 'booleen' }
  return { cle: parType[type] ? `erreurSaisie.${parType[type]}` : 'msg.valeurRefusee' }
}

// Valeur du schéma -> texte affiché dans la zone de saisie (date ISO -> JJ/MM/AAAA).
export function texteInitial(definition, valeur) {
  if (valeur === null || valeur === undefined) return ''
  if (definition?.type === 'date') {
    const r = /^(\d{4})-(\d{2})-(\d{2})$/.exec(String(valeur))
    if (r) return `${r[3]}/${r[2]}/${r[1]}`
  }
  return String(valeur)
}
