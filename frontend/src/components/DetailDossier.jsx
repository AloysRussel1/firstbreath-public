import { useEffect, useRef, useState } from 'react'
import Compositeur from './Compositeur'
import { useLangue } from '../i18n'
import { definitionChamp, estDouteux, estFiable, libelleChamp } from '../lib/format'
import { IconeRetour } from './Icones'
import SectionsPage from './SectionsDossier'

// Pages du dossier + pages en saisie manuelle. Une page en cours de saisie existe déjà sur le serveur dès le
// premier champ enregistré : ses champs encore vides restent affichés pour que la saisie soit complète.
function pagesDe(dossier, pagesEnSaisie) {
  const connues = dossier?.pages || []
  const fusionnees = connues.map((page) => {
    const saisie = pagesEnSaisie.find((p) => p.page_no === page.page_no)
    if (!saisie) return page
    const enregistres = new Map(page.champs.map((c) => [c.champ, c]))
    return { ...page, champs: saisie.champs.map((c) => enregistres.get(c.champ) || c).concat(page.champs.filter((c) => !saisie.champs.some((s) => s.champ === c.champ))) }
  })
  return [...fusionnees, ...pagesEnSaisie.filter((p) => !connues.some((q) => q.page_no === p.page_no))].sort((a, b) => a.page_no - b.page_no)
}

// Contenu du dossier en cours : résumé, pages par sections, actions. Utilisé dans le panneau latéral
// (grand écran, à côté du fil) et dans la fenêtre ouverte depuis la conversation (téléphone, tablette).
export function ContenuDossier({ dossier, pagesEnSaisie = [], schema, seuil, occupe, onCorriger, onToutConfirmer, onValider, entete = null,
  requis = [], filtre = false, onFiltre = () => {} }) {
  const { t, langue } = useLangue()
  const [saisie, setSaisie] = useState(null)
  const editer = (champ, page) => setSaisie({
    titre: t('saisie.saisir', { champ: libelleChamp(schema, champ.champ, langue, t) }),
    definition: definitionChamp(schema, champ.champ),
    valeurInitiale: champ.valeur,
    onEnvoyer: (valeur) => onCorriger(champ, page, { valeur }),
    onVide: () => onCorriger(champ, page, { vide: true }),
  })
  const toutes = pagesDe(dossier, pagesEnSaisie)
  // Champs restants : douteux, ou obligatoires pas encore sûrs.
  const sur = (c) => c.valeur !== null && c.valeur !== undefined && c.statut === 'CONNU' && (c.confiance >= seuil || c.confirme || c.source === 'manual')
  const restant = (c) => estDouteux(c, seuil) || (requis.includes(c.champ) && !sur(c) && !c.saisie)
  const nbRestants = toutes.reduce((n, p) => n + p.champs.filter(restant).length, 0)
  const actif = filtre && nbRestants > 0
  const pages = actif ? toutes.map((p) => ({ ...p, champs: p.champs.filter(restant) })).filter((p) => p.champs.length) : toutes
  const tous = toutes.flatMap((p) => p.champs)
  const fiablesAConfirmer = tous.filter((c) => estFiable(c, seuil) && !c.confirme && c.source !== 'manual').length
  const douteux = tous.filter((c) => estDouteux(c, seuil)).length
  return (
    <>
      {entete}
      <div className="contenu-resume">
        <p role="status">{t('detail.resume', { etat: dossier ? t(`etat.${dossier.etat}`) : t('detail.nouveau'), total: tous.length, douteux })}</p>
        {nbRestants > 0 && (
          <div className="filtre-dossier" role="radiogroup" aria-label={t('detail.filtre')}>
            <button type="button" role="radio" aria-checked={!actif} onClick={() => onFiltre(false)}>{t('detail.tout')}</button>
            <button type="button" role="radio" aria-checked={actif} onClick={() => onFiltre(true)}>{t('detail.aVerifier', { n: nbRestants })}</button>
          </div>
        )}
      </div>
      <div className={`panneau-corps ${actif ? 'filtre-actif' : ''}`}>
        {pages.length === 0 && <p className="aide">{t('detail.vide')}</p>}
        {pages.map((p) => {
          const douteuxPage = p.champs.filter((c) => estDouteux(c, seuil)).length
          const capture = [...(dossier?.captures || [])].reverse().find((c) => c.page_no === p.page_no)
          const enSaisie = pagesEnSaisie.some((s) => s.page_no === p.page_no)
          return (
            <details key={`${p.page_no}-${actif}`} className="resume-page" open={enSaisie || actif}>
              <summary>
                <b>{t(`type.${p.type_page}`)}</b>
                <span>
                  {t('commun.page', { n: p.page_no })} · 
                  {t('section.compte', { n: p.champs.length })}
                  {douteuxPage > 0 ? <strong> · {t('section.aVerifier', { n: douteuxPage })}</strong> : ''}
                  {capture?.etat ? ` · ${t(`etat.${capture.etat}`)}` : enSaisie ? ` · ${t('detail.saisieManuelle')}` : ''}
                </span>
              </summary>
              <SectionsPage page={p} schema={schema} seuil={seuil} occupe={occupe} onEditer={onCorriger ? editer : null} toutOuvert={actif} />
            </details>
          )
        })}
      </div>
      {saisie ? <Compositeur saisie={saisie} onFermer={() => setSaisie(null)} /> : (
      <footer className="panneau-pied">
        {fiablesAConfirmer > 0 && (
          <div className="pied-tout-confirmer">
            <button type="button" disabled={occupe} onClick={onToutConfirmer}>{t('detail.toutConfirmer', { n: fiablesAConfirmer })}</button>
            <p className="aide">{t('aide.toutConfirmer')}</p>
          </div>
        )}
        <button type="button" disabled={occupe || !dossier} onClick={onValider}>{t('detail.valider')}</button>
      </footer>
      )}
    </>
  )
}

// Fenêtre plein écran du dossier (« Voir le détail », saisie manuelle). Échap ou le bouton retour la ferment.
export default function DetailDossier({ onFermer, ...props }) {
  const { t } = useLangue()
  const retour = useRef(null)
  useEffect(() => { retour.current?.focus() }, [])
  return (
    <div className="panneau" role="dialog" aria-modal="true" aria-label={t('detail.titre')}
      onKeyDown={(e) => { if (e.key === 'Escape') onFermer() }}>
      <header className="panneau-tete">
        <button ref={retour} type="button" className="retour" onClick={onFermer} aria-label={t('detail.revenir')}><IconeRetour /></button>
        <b>{t('detail.titre')}</b>
      </header>
      <ContenuDossier {...props} />
    </div>
  )
}
