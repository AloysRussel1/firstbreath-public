// Rendu des textes de la conversation, stockés sous forme { cle, params } pour suivre la langue choisie.
// Paramètres spéciaux : { cle } (texte imbriqué), [ … ] (liste séparée par des virgules), { typePage }, { etat }, { champs: [clés] },
// { champ, valeur } (valeur lue mise en forme selon le schéma).
import { definitionChamp, formaterValeur, libelleChamp } from './format'

export function rendreTexte(x, contexte) {
  if (x === null || x === undefined) return ''
  if (typeof x === 'string' || typeof x === 'number') return String(x)
  const { t } = contexte
  if (x.cle) {
    const params = {}
    for (const [nom, v] of Object.entries(x.params || {})) params[nom] = rendreParametre(v, contexte)
    return t(x.cle, params)
  }
  return rendreParametre(x, contexte)
}

function rendreParametre(v, contexte) {
  const { t, langue, schema } = contexte
  if (v === null || v === undefined || typeof v !== 'object') return v
  if (Array.isArray(v)) return v.map((x) => rendreParametre(x, contexte)).join(', ')
  if (v.cle) return rendreTexte(v, contexte)
  if (v.typePage) return t(`type.${v.typePage}`)
  if (v.etat) return t(`etat.${v.etat}`)
  if (Array.isArray(v.champs)) return v.champs.map((cle) => libelleChamp(schema, cle, langue, t)).join(', ')
  if (v.champ) return formaterValeur(definitionChamp(schema, v.champ), v.valeur, t)
  return ''
}
