import { useEffect, useRef, useState } from 'react'
import { useLangue } from '../i18n'
import { definitionChamp, formaterValeur, libelleChamp, raisonDoute } from '../lib/format'
import StatutBadge from './StatutBadge'

// Photo de la page en grand, au-dessus de tout ; Échap, le bouton ou un toucher la ferment.
function Visionneuse({ url, titre, onFermer }) {
  const { t } = useLangue()
  const fermer = useRef(null)
  useEffect(() => { fermer.current?.focus() }, [])
  return (
    <div className="visionneuse" role="dialog" aria-modal="true" aria-label={titre}
      onClick={onFermer} onKeyDown={(e) => { if (e.key === 'Escape') onFermer() }}>
      <img src={url} alt={titre} />
      <button ref={fermer} type="button" className="bouton" onClick={onFermer}>{t('question.fermerPhoto')}</button>
    </div>
  )
}

// Une question de l'agent sur UN champ douteux : ce qu'il a lu, pourquoi il doute (une phrase), réponses rapides.
// Les 4 réponses ont exactement la même taille et le même poids visuel : aucune n'est mise en avant,
// pour ne pas pousser à confirmer sans vérifier (biais d'automatisation).
export default function CarteQuestion({ champ, schema, seuil, numero, total, pageNo, photoUrl, reponse, occupe, onRepondre, onCorriger }) {
  const { t, langue } = useLangue()
  const [photoOuverte, setPhotoOuverte] = useState(false)
  const definition = definitionChamp(schema, champ.champ)
  const libelle = libelleChamp(schema, champ.champ, langue, t)
  const valeurLue = champ.valeur !== null && champ.valeur !== undefined
  const raison = raisonDoute(champ, seuil)
  const progression = t('question.numero', { numero, total })

  if (reponse) {
    return (
      <div className="question repondue">
        <span className="question-numero">{progression}</span> · <span dir="auto">{libelle}</span>
      </div>
    )
  }

  return (
    <article className="question carte-papier" aria-label={`${progression} : ${libelle}`}>
      <header className="question-tete">
        <span className="question-numero">{progression}</span>
        <StatutBadge statut={champ.statut} />
      </header>

      <div className="question-corps">
        {photoUrl && (
          <button type="button" className="question-photo" onClick={() => setPhotoOuverte(true)} aria-label={t('question.photo')}>
            <img src={photoUrl} alt="" />
            <span className="tampon">{t('commun.page', { n: pageNo })}</span>
          </button>
        )}
        <div className="question-texte">
          <p className="question-libelle" dir="auto">{libelle}</p>
          {valeurLue
            ? <p className="question-lu">{t('question.lu')} <b className="valeur-lue" dir="auto">{formaterValeur(definition, champ.valeur, t)}</b></p>
            : <p className="question-lu">{t('question.pasLu')}</p>}
          <p className="question-raison">{raison ? t(raison.cle, raison.params) : t('question.verifier')}</p>
        </div>
      </div>

      <div className="reponses" role="group" aria-label={t('question.reponses')}>
        <button type="button" className="reponse" disabled={occupe || !valeurLue} title={valeurLue ? '' : t('question.rienAConfirmer')}
          onClick={() => onRepondre({ action: 'confirmer' })}>
          <span aria-hidden="true">✓</span> {t('question.confirmer')}
        </button>
        <button type="button" className="reponse" disabled={occupe} onClick={onCorriger}>
          <span aria-hidden="true">✎</span> {t('question.corriger')}
        </button>
        <button type="button" className="reponse" disabled={occupe} onClick={() => onRepondre({ action: 'vide' })}>
          <span aria-hidden="true">–</span> {t('question.vide')}
        </button>
        <button type="button" className="reponse" disabled={occupe} onClick={() => onRepondre({ action: 'reprendre' })}>
          <span aria-hidden="true">↺</span> {t('question.reprendre')}
        </button>
      </div>
      {photoOuverte && <Visionneuse url={photoUrl} titre={t('commun.page', { n: pageNo })} onFermer={() => setPhotoOuverte(false)} />}
    </article>
  )
}
