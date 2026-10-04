// Coffre local chiffré : IndexedDB (dexie) + Web Crypto AES-GCM 256 bits.
// - La clé est générée sur l'appareil, non exportable (le navigateur ne la révèle jamais en clair).
// - Chaque écriture utilise un vecteur d'initialisation (IV) aléatoire de 12 octets.
// - Les photos sont stockées à part (chiffrées une seule fois) ; l'état de la conversation est un
//   document chiffré réécrit à chaque changement.
// Limite connue : la clé vit dans le même navigateur que les données (protection contre la lecture
// directe des fichiers, pas contre une personne qui utilise le navigateur déverrouillé). En production,
// elle serait dérivée d'un code personnel ou du coffre matériel du téléphone.
import Dexie from 'dexie'

const db = new Dexie('firstbreath')
db.version(1).stores({ cles: 'id', documents: 'id', photos: 'id' })

let clePromesse = null
function cle() {
  if (!clePromesse) {
    clePromesse = (async () => {
      const existante = await db.cles.get('principale')
      if (existante) return existante.cle
      const nouvelle = await crypto.subtle.generateKey({ name: 'AES-GCM', length: 256 }, false, ['encrypt', 'decrypt'])
      await db.cles.put({ id: 'principale', cle: nouvelle })
      return nouvelle
    })()
  }
  return clePromesse
}

async function chiffrer(octets) {
  const iv = crypto.getRandomValues(new Uint8Array(12))
  const donnees = await crypto.subtle.encrypt({ name: 'AES-GCM', iv }, await cle(), octets)
  return { iv, donnees }
}

async function dechiffrer({ iv, donnees }) {
  return crypto.subtle.decrypt({ name: 'AES-GCM', iv }, await cle(), donnees)
}

// ---------- Documents (objets JSON) ----------
export async function sauverDocument(id, objet) {
  const { iv, donnees } = await chiffrer(new TextEncoder().encode(JSON.stringify(objet)))
  await db.documents.put({ id, iv, donnees, maj: Date.now() })
}

export async function lireDocument(id) {
  const enreg = await db.documents.get(id)
  if (!enreg) return null
  return JSON.parse(new TextDecoder().decode(await dechiffrer(enreg)))
}

// ---------- Photos (Blob) ----------
export async function sauverPhoto(id, blob) {
  const { iv, donnees } = await chiffrer(await blob.arrayBuffer())
  await db.photos.put({ id, iv, donnees, type: blob.type || 'image/jpeg' })
}

export async function lirePhoto(id) {
  const enreg = await db.photos.get(id)
  if (!enreg) return null
  return new Blob([await dechiffrer(enreg)], { type: enreg.type })
}

export async function supprimerPhotos(ids) {
  await db.photos.bulkDelete(ids)
}

export async function effacerTout() {
  await Promise.all([db.documents.clear(), db.photos.clear()])
}

// Vérifie que le coffre est utilisable (navigation privée, stockage bloqué…).
export async function coffreDisponible() {
  try {
    await cle()
    return true
  } catch {
    return false
  }
}
