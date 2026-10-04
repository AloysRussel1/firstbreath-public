import { useEffect, useState } from 'react'
import { useLangue } from '../i18n'
import EditeurValeur from './EditeurValeur'
import SaisieCode from './SaisieCode'

// Hauteur du clavier virtuel quand le navigateur ne redimensionne pas la page (iOS) : la zone remonte d'autant.
function useDecalageClavier() {
  const [decalage, setDecalage] = useState(0)
  useEffect(() => {
    const vv = window.visualViewport
    if (!vv) return undefined
    const maj = () => setDecalage(Math.max(0, Math.round(window.innerHeight - vv.height - vv.offsetTop)))
    vv.addEventListener('resize', maj)
    vv.addEventListener('scroll', maj)
    return () => { vv.removeEventListener('resize', maj); vv.removeEventListener('scroll', maj) }
  }, [])
  return decalage
}

// Zone de saisie fixée en bas, comme dans WhatsApp : champ large adapté au type de valeur, [Envoyer], [Annuler].
// saisie = { titre, type: 'champ' | 'code', definition, valeurInitiale, onEnvoyer(valeur), onVide? }
// onEnvoyer peut renvoyer false (valeur refusée) : la zone reste ouverte.
export default function Compositeur({ saisie, onFermer }) {
  const { t } = useLangue()
  const decalage = useDecalageClavier()
  const envoyer = async (valeur) => {
    if ((await saisie.onEnvoyer(valeur)) !== false) onFermer()
  }
  return (
    <div className="compositeur" role="region" aria-label={saisie.titre}
      style={decalage ? { transform: `translateY(-${decalage}px)` } : undefined}
      onKeyDown={(e) => { if (e.key === 'Escape') onFermer() }}>
      <div className="compositeur-tete">
        <b dir="auto">{saisie.titre}</b>
        {saisie.onVide && (
          <button type="button" className="lien-texte" onClick={async () => { if ((await saisie.onVide()) !== false) onFermer() }}>
            {t('question.vide')}
          </button>
        )}
      </div>
      {saisie.type === 'code'
        ? <SaisieCode onSoumettre={envoyer} onAnnuler={onFermer} libelle={t('commun.envoyer')} />
        : <EditeurValeur definition={saisie.definition} valeurInitiale={saisie.valeurInitiale} onValider={envoyer} onAnnuler={onFermer}
          libelleValider={t('commun.envoyer')} variante="dans-compositeur" />}
    </div>
  )
}
