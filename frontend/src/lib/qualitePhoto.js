// Contrôle de qualité sur l'appareil, avant l'envoi : netteté et luminosité. Rien ne quitte le téléphone.
//
// Image réduite à 480 px de large, en niveaux de gris :
//   luminosité = moyenne des gris (0 à 255) ;
//   netteté    = 1000 × variance du laplacien / luminosité² (indépendante de l'éclairage global).
// Seuils calibrés sur les 48 pages de dev et leurs versions dégradées (extraction/degrader.py) :
//   netteté < 9    : 48/48 pages floues signalées, 0/48 originaux, 0 en JPEG compressé, rotation ou ombre ;
//   luminosité < 110 : 48/48 pages sombres signalées, 0/48 originaux (originaux entre 193 et 205) ;
//   luminosité > 235 : surexposition ou reflet (pas de version dégradée correspondante : seuil prudent).
const LARGEUR = 480
export const SEUILS = { nettete: 9, sombre: 110, claire: 235 }

async function pixelsGris(fichier) {
  const image = await createImageBitmap(fichier)
  const hauteur = Math.max(1, Math.round(image.height * LARGEUR / image.width))
  const toile = document.createElement('canvas')
  toile.width = LARGEUR
  toile.height = hauteur
  const ctx = toile.getContext('2d', { willReadFrequently: true })
  ctx.drawImage(image, 0, 0, LARGEUR, hauteur)
  image.close?.()
  const { data } = ctx.getImageData(0, 0, LARGEUR, hauteur)
  const gris = new Float32Array(LARGEUR * hauteur)
  for (let i = 0, j = 0; i < data.length; i += 4, j += 1) gris[j] = 0.299 * data[i] + 0.587 * data[i + 1] + 0.114 * data[i + 2]
  return { gris, largeur: LARGEUR, hauteur }
}

export function mesurer({ gris, largeur, hauteur }) {
  let somme = 0
  for (const g of gris) somme += g
  const luminosite = somme / gris.length
  let n = 0, moyenne = 0, m2 = 0
  for (let y = 1; y < hauteur - 1; y += 1) {
    for (let x = 1; x < largeur - 1; x += 1) {
      const i = y * largeur + x
      const lap = gris[i - 1] + gris[i + 1] + gris[i - largeur] + gris[i + largeur] - 4 * gris[i]
      n += 1
      const delta = lap - moyenne
      moyenne += delta / n
      m2 += delta * (lap - moyenne)
    }
  }
  const variance = n ? m2 / n : 0
  return { luminosite, nettete: (1000 * variance) / Math.max(luminosite, 1) ** 2 }
}

// Renvoie { problemes: ['floue' | 'sombre' | 'claire'], mesures } ; problemes vide si la photo convient.
export async function verifierQualite(fichier) {
  const mesures = mesurer(await pixelsGris(fichier))
  const problemes = []
  if (mesures.nettete < SEUILS.nettete) problemes.push('floue')
  if (mesures.luminosite < SEUILS.sombre) problemes.push('sombre')
  else if (mesures.luminosite > SEUILS.claire) problemes.push('claire')
  return { problemes, mesures }
}
