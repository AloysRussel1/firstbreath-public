// Seul fichier qui parle au serveur (routes de shared/CONTRAT.md et du backend).
const API_BASE = (import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000').replace(/\/$/, '')
const DELAI_MS = 15000

// Erreur réseau (serveur injoignable) : la capture reste en file d'attente et repartira plus tard.
export class HorsLigne extends Error {
  constructor() {
    super('Serveur injoignable')
    this.hors_ligne = true
  }
}

let identite = { sageFemmeId: 'sf_local', role: 'SAGE_FEMME' }
export function definirIdentite(nouvelle) {
  identite = { ...identite, ...nouvelle }
}

// « Simuler hors ligne » : coupe tous les appels, comme sur le terrain sans réseau.
let horsLigneSimule = false
export function simulerHorsLigne(actif) {
  horsLigneSimule = Boolean(actif)
}
export const estHorsLigneSimule = () => horsLigneSimule

async function requete(chemin, options = {}) {
  if (horsLigneSimule) throw new HorsLigne()
  const controleur = new AbortController()
  const minuterie = setTimeout(() => controleur.abort(), options.delai || DELAI_MS)
  let reponse
  try {
    reponse = await fetch(`${API_BASE}${chemin}`, {
      ...options,
      signal: controleur.signal,
      headers: { 'X-Sage-Femme-Id': identite.sageFemmeId, 'X-Role': identite.role, ...(options.headers || {}) },
    })
  } catch {
    throw new HorsLigne()
  } finally {
    clearTimeout(minuterie)
  }
  const corps = await reponse.json().catch(() => ({}))
  if (!reponse.ok) {
    const erreur = new Error(corps.detail || `Erreur du serveur (${reponse.status})`)
    erreur.statut = reponse.status
    throw erreur
  }
  return corps
}

const json = (corps) => ({ headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(corps) })

export const api = {
  sante: () => requete('/sante', { delai: 4000 }),
  schema: () => requete('/schema'),

  envoyerCapture(fichier, { sessionId, pageNo }) {
    const formulaire = new FormData()
    formulaire.append('image', fichier)
    formulaire.append('session_id', sessionId)
    formulaire.append('page_no', String(pageNo))
    formulaire.append('sage_femme_id', identite.sageFemmeId)
    return requete('/captures', { method: 'POST', body: formulaire, delai: 30000 })
  },
  traiter: (captureId) => requete(`/captures/${captureId}/traiter`, { method: 'POST' }),
  etat: (captureId) => requete(`/captures/${captureId}/etat`),

  dossier: (dossierId) => requete(`/dossiers/${dossierId}`),
  corrigerChamp: (dossierId, champ) => requete(`/dossiers/${dossierId}/champs`, { method: 'PATCH', ...json(champ) }),
  confirmerFiables: (dossierId, cles) => requete(`/dossiers/${dossierId}/confirmer`, { method: 'POST', ...json(cles ? { champs: cles } : {}) }),
  validation: (dossierId) => requete(`/dossiers/${dossierId}/validation`),
  valider: (dossierId) => requete(`/dossiers/${dossierId}/validate`, { method: 'POST' }),

  correspondances: ({ numero, code }) => {
    const params = new URLSearchParams()
    if (numero) params.set('numero_fiche', numero)
    if (code) params.set('code', code)
    return requete(`/patientes/correspondances?${params}`)
  },
  lier: (dossierId, choix) => requete(`/dossiers/${dossierId}/lier`, { method: 'POST', ...json(choix) }),

  listeDossiers: () => requete('/dossiers'),
  patientes: () => requete('/patientes'),
  historique: (dossierId) => requete(`/dossiers/${dossierId}/historique`),
  renumeriser: (dossierId, corps) => requete(`/dossiers/${dossierId}/renumerisation`, { method: 'POST', ...json(corps) }),
  tableauDeBord: (source = 'dossiers') => requete(`/tableau-de-bord?source=${encodeURIComponent(source)}`),
  retirerPage: (dossierId, pageNo) => requete(`/dossiers/${dossierId}/pages/${pageNo}/retirer`, { method: 'POST' }),
  deplacerCapture: (captureId, corps) => requete(`/captures/${captureId}/nouveau-registre`, { method: 'POST', ...json(corps) }),
  enregistrer: (dossierId) => requete(`/dossiers/${dossierId}/enregistrer`, { method: 'POST' }),
  synchroniser: ({ simulerPanne = false } = {}) => requete('/synchronisation', { method: 'POST', ...json({ simuler_panne: simulerPanne }) }),

  // Photo d'origine (accès selon le rôle) : renvoie un Blob.
  async image(captureId) {
    if (horsLigneSimule) throw new HorsLigne()
    let reponse
    try {
      reponse = await fetch(`${API_BASE}/captures/${captureId}/image`, {
        headers: { 'X-Sage-Femme-Id': identite.sageFemmeId, 'X-Role': identite.role },
      })
    } catch {
      throw new HorsLigne()
    }
    if (!reponse.ok) {
      const erreur = new Error(`Erreur du serveur (${reponse.status})`)
      erreur.statut = reponse.status
      throw erreur
    }
    return reponse.blob()
  },
}
