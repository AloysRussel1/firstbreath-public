import { useState } from 'react'
import { useLangue } from '../i18n'
import { estDouteux } from '../lib/format'

const ATTENTE = ['QUALITE', 'EN_FILE', 'ENVOI', 'A_TRAITER', 'CAPTURE']
const ECHEC = ['ECHEC_TRAITEMENT', 'REVISION_MANUELLE_REQUISE', 'REFUSEE']

// État d'une page pour l'affichage (icône, jamais de couleur de statut).
function etatPage(c, page, seuil) {
  if (c.etat === 'EN_FILE') return 'horsLigne'
  if (ATTENTE.includes(c.etat)) return 'attente'
  if (c.etat === 'EN_ATTENTE_IA') return 'lecture'
  if (c.etat === 'DOUBLON_SUSPECTE') return 'doublon'
  if (c.etat === 'ABANDONNEE') return 'ecartee'
  if (ECHEC.includes(c.etat)) return 'echec'
  if (page && page.champs.some((x) => estDouteux(x, seuil))) return 'aVerifier'
  return 'ok'
}

function IconeEtat({ etat }) {
  const trait = { fill: 'none', stroke: 'currentColor', strokeWidth: 2, strokeLinecap: 'round', strokeLinejoin: 'round' }
  const formes = {
    attente: <><circle cx="8" cy="8" r="6" {...trait} /><path d="M8 5v3l2 1.5" {...trait} /></>,
    lecture: <><circle cx="4" cy="8" r="1.4" fill="currentColor" /><circle cx="8" cy="8" r="1.4" fill="currentColor" /><circle cx="12" cy="8" r="1.4" fill="currentColor" /></>,
    aVerifier: <><circle cx="8" cy="8" r="6" {...trait} strokeDasharray="2.5 2" /><path d="M6.6 6.4a1.5 1.5 0 1 1 2 1.4c-.4.2-.6.5-.6 1v.4" {...trait} /><circle cx="8" cy="11.6" r=".6" fill="currentColor" /></>,
    ok: <path d="M3.5 8.5l3 3 6-7" {...trait} />,
    doublon: <><rect x="2.5" y="4.5" width="7" height="9" rx="1" {...trait} /><path d="M6.5 2.5h6a1 1 0 0 1 1 1v8" {...trait} /></>,
    echec: <><circle cx="8" cy="8" r="6" {...trait} /><path d="M8 4.8v3.8M8 11.2v.1" {...trait} /></>,
    ecartee: <><circle cx="8" cy="8" r="6" {...trait} /><path d="M4 12L12 4" {...trait} /></>,
    horsLigne: <><path d="M2.5 6.5a8 8 0 0 1 11 0M5 9a4.5 4.5 0 0 1 6 0" {...trait} /><circle cx="8" cy="11.8" r="1" fill="currentColor" /><path d="M2.5 2.5l11 11" {...trait} /></>,
  }
  return <svg viewBox="0 0 16 16" width="12" height="12" aria-hidden="true">{formes[etat]}</svg>
}

// File des pages : une ligne de résumé et des pastilles numérotées sur une seule ligne ;
// un toucher sur le résumé déplie la liste détaillée (doublon suspecté : [Retirer]).
export default function FilePages({ captures, dossier, seuil, occupe, onRetirer, onNouveauRegistre, onOuvrirDossier }) {
  const { t } = useLangue()
  const [ouvert, setOuvert] = useState(false)
  const [legende, setLegende] = useState(false)
  const lignes = captures.map((c) => {
    const page = dossier?.pages?.find((p) => p.page_no === c.pageNo)
    const type = page?.type_page || c.typePage
    return { c, page, type, etat: etatPage(c, page, seuil) }
  })
  const compter = (e) => lignes.filter((l) => l.etat === e).length
  const resume = [
    t('pages.nombre', { n: captures.length }),
    compter('aVerifier') && t('pages.aVerifier', { n: compter('aVerifier') }),
    (compter('attente') + compter('lecture') + compter('horsLigne')) && t('pages.enCours', { n: compter('attente') + compter('lecture') + compter('horsLigne') }),
    compter('doublon') && t('pages.doublons', { n: compter('doublon') }),
    compter('echec') && t('pages.echecs', { n: compter('echec') }),
  ].filter(Boolean).join(' · ')
  const etiquette = (l) => `${l.type ? `${t(`type.${l.type}`)} (${t('commun.page', { n: l.c.pageNo })})` : t('commun.page', { n: l.c.pageNo })} : ${t(`pages.etat.${l.etat}`)}`

  return (
    <div className="file-pages">
      <div className="file-pages-ligne">
        <button type="button" className="file-pages-resume" aria-expanded={ouvert} onClick={() => setOuvert(!ouvert)}>
          <span>{resume}</span>
          <svg viewBox="0 0 16 16" width="14" height="14" aria-hidden="true" className={ouvert ? 'chevron ouvert' : 'chevron'}>
            <path d="M4 6l4 4 4-4" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
          </svg>
        </button>
        <ol className="pastilles" aria-label={t('conv.pagesPrises')}>
          {lignes.map((l) => (
            <li key={l.c.localId} className={`pastille-page ${l.etat}`} title={etiquette(l)} aria-label={etiquette(l)}>
              <span aria-hidden="true">{l.c.pageNo}</span>
              <i><IconeEtat etat={l.etat} /></i>
            </li>
          ))}
        </ol>
        <button type="button" className="bouton-legende" aria-expanded={legende} aria-label={t('pages.legende')} title={t('pages.legende')}
          onClick={() => setLegende(!legende)}>?</button>
        {onOuvrirDossier && (
          <button type="button" className="ouvrir-dossier" disabled={!dossier} onClick={onOuvrirDossier}>{t('conv.dossier')}</button>
        )}
      </div>
      {legende && (
        <ul className="legende-pastilles" aria-label={t('pages.legende')}>
          {['ok', 'aVerifier', 'doublon', 'attente', 'horsLigne', 'lecture', 'echec'].map((e) => (
            <li key={e}><span className={`pastille-page ${e}`} aria-hidden="true"><span>1</span><i><IconeEtat etat={e} /></i></span>{t(`pages.etat.${e}`)}</li>
          ))}
        </ul>
      )}
      {ouvert && (
        <div className="file-pages-detail">
          <ul>
            {lignes.map((l) => (
              <li key={l.c.localId}>
                <span className={`pastille-page ${l.etat}`} aria-hidden="true"><span>{l.c.pageNo}</span><i><IconeEtat etat={l.etat} /></i></span>
                <span className="file-pages-texte">
                  <b>{l.type ? t(`type.${l.type}`) : t('commun.page', { n: l.c.pageNo })}</b>
                  <small>{l.type ? `${t('commun.page', { n: l.c.pageNo })} · ` : ''}{t(`pages.etat.${l.etat}`)}</small>
                </span>
                {l.etat === 'doublon' && (
                  <button type="button" className="lien-bouton" disabled={occupe} onClick={() => { onRetirer(l.c.localId); setOuvert(false) }}>
                    {t('pages.retirer')}
                  </button>
                )}
              </li>
            ))}
          </ul>
          <button type="button" className="lien-bouton" onClick={() => { setOuvert(false); onNouveauRegistre() }}>+ {t('conv.nouveauRegistre')}</button>
        </div>
      )}
    </div>
  )
}
