import { useEffect } from 'react'
import { FournisseurConnexion } from './etat/connexion'
import { FournisseurConversation } from './etat/conversation'
import { FournisseurProfil, useProfil } from './etat/profil'
import { naviguer, useRoute } from './etat/route'
import { FournisseurLangue } from './i18n'
import Accueil from './pages/Accueil'
import Application from './pages/Application'
import APropos from './pages/APropos'
import Profil from './pages/Profil'

const ONGLETS = ['conversation', 'dossiers', 'tableau', 'reglages']

function Routeur() {
  const { morceaux } = useRoute()
  const { profil } = useProfil()
  const [page, onglet, identifiant] = morceaux
  const appSansProfil = page === 'app' && !profil
  const ongletValide = ONGLETS.includes(onglet) ? onglet : 'conversation'

  useEffect(() => {
    if (appSansProfil) naviguer('/profil')
  }, [appSansProfil])

  if (page === 'profil') return <Profil />
  if (page === 'a-propos') return <APropos />
  if (page === 'app' && profil) return <Application onglet={ongletValide} identifiant={identifiant} />
  return <Accueil />
}

export default function App() {
  return (
    <FournisseurLangue>
      <FournisseurProfil>
        <FournisseurConnexion>
          <FournisseurConversation>
            <Routeur />
          </FournisseurConversation>
        </FournisseurConnexion>
      </FournisseurProfil>
    </FournisseurLangue>
  )
}
