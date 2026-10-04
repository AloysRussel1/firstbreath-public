// Connexion au serveur : vérifiée toutes les 5 s (jamais bloquante) ; « Simuler hors ligne » mémorisé.
import { createContext, useContext, useEffect, useMemo, useState } from 'react'
import { api, simulerHorsLigne } from '../api'

const INTERVALLE_MS = 5000
const CLE_SIMULE = 'firstbreath-hors-ligne-simule'
const ConnexionContexte = createContext(null)

function lireSimule() {
  try { return localStorage.getItem(CLE_SIMULE) === '1' } catch { return false }
}

export function FournisseurConnexion({ children }) {
  const [connecte, setConnecte] = useState(null)
  const [simule, setSimule] = useState(() => {
    const valeur = lireSimule()
    simulerHorsLigne(valeur)
    return valeur
  })
  const [verification, setVerification] = useState(0)

  useEffect(() => {
    let actif = true
    const verifier = () => api.sante().then(() => actif && setConnecte(true)).catch(() => actif && setConnecte(false))
    verifier()
    const minuterie = setInterval(verifier, INTERVALLE_MS)
    return () => { actif = false; clearInterval(minuterie) }
  }, [verification])

  const valeur = useMemo(() => ({
    connecte: connecte && !simule,
    verifie: connecte !== null || simule,
    simule,
    basculerSimulation() {
      const nouveau = !simule
      simulerHorsLigne(nouveau)
      try { localStorage.setItem(CLE_SIMULE, nouveau ? '1' : '0') } catch { /* stockage indisponible */ }
      setSimule(nouveau)
      setConnecte(nouveau ? false : null)
      setVerification((v) => v + 1) // nouvelle vérification immédiate
    },
  }), [connecte, simule])

  return <ConnexionContexte.Provider value={valeur}>{children}</ConnexionContexte.Provider>
}

// eslint-disable-next-line react-refresh/only-export-components
export function useConnexion() {
  return useContext(ConnexionContexte)
}
