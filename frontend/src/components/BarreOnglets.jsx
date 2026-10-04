import { useLangue } from '../i18n'
import { IconeConversation, IconeDossier, IconeReglages, IconeTableau } from './Icones'

const ONGLETS = [
  { id: 'conversation', icone: IconeConversation },
  { id: 'dossiers', icone: IconeDossier },
  { id: 'tableau', icone: IconeTableau },
  { id: 'reglages', icone: IconeReglages },
]

// Barre d'onglets du bas, à portée de pouce.
export default function BarreOnglets({ actif, badges = {} }) {
  const { t } = useLangue()
  return (
    <nav className="onglets" aria-label="Navigation">
      {ONGLETS.map(({ id, icone: Icone }) => (
        <a key={id} href={`#/app/${id}`} className={`onglet ${actif === id ? 'actif' : ''}`} aria-current={actif === id ? 'page' : undefined}>
          <span className="onglet-icone"><Icone taille={24} />{badges[id] > 0 && <span className="badge">{badges[id]}</span>}</span>
          <span>{t(`nav.${id}`)}</span>
        </a>
      ))}
    </nav>
  )
}
