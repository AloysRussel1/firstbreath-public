// Routage par « # » (aucune dépendance) : #/accueil, #/profil, #/a-propos, #/app/<onglet>[/<id>].
import { useEffect, useState } from 'react'

function lire() {
  const chemin = window.location.hash.replace(/^#/, '') || '/accueil'
  const morceaux = chemin.split('/').filter(Boolean)
  return { chemin, morceaux }
}

export function naviguer(chemin) {
  if (window.location.hash !== `#${chemin}`) window.location.hash = chemin
}

export function useRoute() {
  const [route, setRoute] = useState(lire)
  useEffect(() => {
    const changer = () => {
      setRoute(lire())
      window.scrollTo(0, 0)
    }
    window.addEventListener('hashchange', changer)
    return () => window.removeEventListener('hashchange', changer)
  }, [])
  return route
}
