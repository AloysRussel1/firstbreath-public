import { useEffect, useState } from 'react'
import { useConversation } from '../etat/conversation'
import { naviguer } from '../etat/route'
import { useLangue } from '../i18n'
import { IconeAppareil, IconeConversation, IconeDossier, IconeReglages, IconeTableau } from './Icones'

const AVANT = [
  { id: 'conversation', icone: IconeConversation },
  { id: 'dossiers', icone: IconeDossier },
]
const APRES = [
  { id: 'tableau', icone: IconeTableau },
  { id: 'reglages', icone: IconeReglages },
]

// Clavier virtuel ouvert : la fenêtre visible rétrécit nettement (Android et iOS).
function useClavierOuvert() {
  const [ouvert, setOuvert] = useState(false)
  useEffect(() => {
    const vv = window.visualViewport
    if (!vv) return undefined
    const maj = () => setOuvert(window.innerHeight - vv.height > 120)
    vv.addEventListener('resize', maj)
    return () => vv.removeEventListener('resize', maj)
  }, [])
  return ouvert
}

// Barre d'onglets du bas : 4 onglets (icône au-dessus du libellé) et, au centre, le bouton appareil photo.
// Masquée quand la zone de saisie ou le clavier est ouvert (le CSS gère la zone de saisie).
export default function BarreOnglets({ actif, badges = {} }) {
  const { t } = useLangue()
  const { ouvrirAppareil } = useConversation()
  const clavier = useClavierOuvert()

  // Depuis un autre onglet : retour à la conversation, puis prise de photo (dans le même geste, pour le navigateur).
  const photographier = () => {
    if (actif !== 'conversation') naviguer('/app/conversation')
    ouvrirAppareil()
  }
  const onglet = ({ id, icone: Icone }) => {
    const libelle = t(`nav.${id}`)
    const badge = badges[id] > 0 ? badges[id] : 0
    return (
      <a key={id} href={`#/app/${id}`} className={`onglet ${actif === id ? 'actif' : ''}`} aria-current={actif === id ? 'page' : undefined}
        aria-label={badge ? t('nav.avecFile', { onglet: libelle, n: badge }) : libelle}>
        <span className="onglet-icone" aria-hidden="true"><Icone taille={24} />{badge > 0 && <span className="badge">{badge}</span>}</span>
        <span className="onglet-libelle" aria-hidden="true">{libelle}</span>
      </a>
    )
  }

  return (
    <nav className="onglets" aria-label={t('nav.principale')} hidden={clavier}>
      <div className="onglets-rangee">
        {AVANT.map(onglet)}
        <div className="onglet-photo">
          <button type="button" className="bouton-photo" onClick={photographier} aria-label={t('conv.photo')}>
            <IconeAppareil taille={26} />
          </button>
        </div>
        {APRES.map(onglet)}
      </div>
    </nav>
  )
}
