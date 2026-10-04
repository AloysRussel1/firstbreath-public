// Suit une requête média (ex. grand écran avec panneau latéral) et se met à jour au redimensionnement.
import { useEffect, useState } from 'react'

export function useRequeteMedia(requete) {
  const [correspond, setCorrespond] = useState(() => window.matchMedia?.(requete).matches ?? false)
  useEffect(() => {
    const liste = window.matchMedia?.(requete)
    if (!liste) return undefined
    const changer = () => setCorrespond(liste.matches)
    liste.addEventListener('change', changer)
    return () => liste.removeEventListener('change', changer)
  }, [requete])
  return correspond
}

export const GRAND_ECRAN = '(min-width: 1100px)'
