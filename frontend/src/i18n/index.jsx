// Bilinguisme FR / EN : toutes les chaînes de l'interface viennent de fr.js et en.js.
// Bascule instantanée (contexte React), langue mémorisée sur l'appareil.
import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react'
import en from './en'
import fr from './fr'

const DICTIONNAIRES = { fr, en }
const CLE_LANGUE = 'firstbreath-langue'
const LangueContexte = createContext(null)

function lireLangue() {
  try {
    const l = localStorage.getItem(CLE_LANGUE)
    return l === 'en' || l === 'fr' ? l : 'fr'
  } catch {
    return 'fr'
  }
}

// Remplace {nom} par params.nom ; une valeur fonction reçoit les paramètres (pluriels).
function traduire(langue, cle, params = {}) {
  const valeur = DICTIONNAIRES[langue]?.[cle] ?? DICTIONNAIRES.fr[cle] ?? cle
  const texte = typeof valeur === 'function' ? valeur(params) : valeur
  return String(texte).replace(/\{(\w+)\}/g, (_, nom) => (params[nom] ?? `{${nom}}`))
}

export function FournisseurLangue({ children }) {
  const [langue, setLangue] = useState(lireLangue)
  useEffect(() => {
    document.documentElement.lang = langue
    try { localStorage.setItem(CLE_LANGUE, langue) } catch { /* stockage indisponible : la langue reste en mémoire */ }
  }, [langue])
  const t = useCallback((cle, params) => traduire(langue, cle, params), [langue])
  const valeur = useMemo(() => ({ langue, setLangue, t }), [langue, t])
  return <LangueContexte.Provider value={valeur}>{children}</LangueContexte.Provider>
}

// eslint-disable-next-line react-refresh/only-export-components
export function useLangue() {
  return useContext(LangueContexte)
}
