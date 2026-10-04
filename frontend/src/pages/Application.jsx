import BarreOnglets from '../components/BarreOnglets'
import EnTete from '../components/EnTete'
import { useConversation } from '../etat/conversation'
import { useLangue } from '../i18n'
import Conversation from './Conversation'
import Dossiers from './Dossiers'
import Reglages from './Reglages'
import TableauBord from './TableauBord'
import VueDossier from './VueDossier'

const FILE = ['EN_FILE', 'A_TRAITER', 'ENVOI', 'QUALITE']

// Coque de l'application : en-tête, écran de l'onglet, barre d'onglets.
// La conversation est montée en permanence (masquée hors de son onglet) : rien ne se perd.
export default function Application({ onglet, identifiant }) {
  const { t } = useLangue()
  const { captures } = useConversation()
  const enFile = captures.filter((c) => FILE.includes(c.etat)).length
  // Les onglets disent « Messages », « Statistiques » (courts) ; l'écran garde son titre complet.
  const titre = { conversation: t('titre.conversation'), tableau: t('tableau.titre') }[onglet] || t(`nav.${onglet}`)

  return (
    <div className="application">
      <EnTete titre={titre} avecSimulation={onglet === 'conversation'} />
      <main className="ecran">
        <div className="ecran-conversation" hidden={onglet !== 'conversation'}><Conversation /></div>
        {onglet === 'dossiers' && (identifiant ? <VueDossier dossierId={identifiant} /> : <Dossiers />)}
        {onglet === 'tableau' && <TableauBord />}
        {onglet === 'reglages' && <Reglages />}
      </main>
      <BarreOnglets actif={onglet} badges={{ conversation: enFile }} />
    </div>
  )
}
