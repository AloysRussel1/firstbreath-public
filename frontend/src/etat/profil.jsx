// Profil de la personne connectée : identifiant professionnel et rôle, mémorisés sur l'appareil
// et envoyés au serveur dans X-Sage-Femme-Id et X-Role (via api.definirIdentite).
import { createContext, useContext, useEffect, useMemo, useState } from 'react'
import { definirIdentite } from '../api'
import { ROLES } from '../lib/roles'

const CLE_PROFIL = 'firstbreath-profil'
const ProfilContexte = createContext(null)

function lireProfil() {
  try {
    const p = JSON.parse(localStorage.getItem(CLE_PROFIL) || 'null')
    if (p && typeof p.sageFemmeId === 'string' && ROLES.includes(p.role)) return p
  } catch { /* profil illisible : on repart de zéro */ }
  return null
}

export function FournisseurProfil({ children }) {
  const [profil, setProfil] = useState(lireProfil)
  useEffect(() => {
    if (profil) definirIdentite({ sageFemmeId: profil.sageFemmeId, role: profil.role })
  }, [profil])
  const valeur = useMemo(() => ({
    profil,
    enregistrer(nouveau) {
      try { localStorage.setItem(CLE_PROFIL, JSON.stringify(nouveau)) } catch { /* stockage indisponible */ }
      definirIdentite({ sageFemmeId: nouveau.sageFemmeId, role: nouveau.role })
      setProfil(nouveau)
    },
  }), [profil])
  return <ProfilContexte.Provider value={valeur}>{children}</ProfilContexte.Provider>
}

// eslint-disable-next-line react-refresh/only-export-components
export function useProfil() {
  return useContext(ProfilContexte)
}
