import { useState } from 'react'
import { useLangue } from '../i18n'
import { datePosterieure, definitionChamp, estDouteux, formaterValeur, infosVisite, libelleChamp, sectionDe } from '../lib/format'
import EditeurValeur from './EditeurValeur'
import StatutBadge from './StatutBadge'

// Un seul indicateur par champ : « vérifié par la sage-femme » (coche dans un carré) ou le statut de lecture.
function IndicateurChamp({ champ }) {
  const { t } = useLangue()
  if (champ.confirme || champ.source === 'manual') {
    return (
      <span className="statut st-verifie" title={t('detail.verifieTitre')}>
        <span className="statut-icone" aria-hidden="true">✓</span>
        <span className="sr-only">{t('detail.verifieTitre')}</span>
      </span>
    )
  }
  return <StatutBadge statut={champ.statut} compact />
}

// Correction d'un champ : éditeur typé + « vide sur le papier ». Partagé par les lignes et le tableau des visites.
function Edition({ champ, schema, occupe, onCorriger, onFermer }) {
  const { t } = useLangue()
  const definition = definitionChamp(schema, champ.champ)
  return (
    <div className="ligne-edition">
      <EditeurValeur
        definition={definition}
        valeurInitiale={champ.valeur}
        onAnnuler={onFermer}
        onValider={async (valeur) => {
          const r = await onCorriger(champ, { valeur })
          if (r?.ok) onFermer()
          return r
        }}
      />
      <button type="button" className="lien-texte" disabled={occupe} onClick={async () => { if ((await onCorriger(champ, { vide: true }))?.ok) onFermer() }}>
        {t('editeur.marquerVide')}
      </button>
    </div>
  )
}

// Ligne compacte « libellé : valeur » avec l'icône de statut ; un toucher ouvre la correction (si onCorriger).
function LigneChamp({ champ, schema, seuil, occupe, onCorriger, onEditer, dateCapture, sansColonne = false }) {
  const { t, langue } = useLangue()
  const [ouvert, setOuvert] = useState(false)
  const definition = definitionChamp(schema, champ.champ)
  const libelle = libelleChamp(schema, champ.champ, langue, t, !sansColonne)
  const douteux = estDouteux(champ, seuil)
  const contenu = (
    <>
      <span className="ligne-libelle" dir="auto">{libelle}</span>
      <span className="ligne-valeur" dir="auto">
        {formaterValeur(definition, champ.valeur, t)}
        {datePosterieure(champ, dateCapture) && <small className="avertissement-date">{t('dossiers.datePosterieure')}</small>}
      </span>
      <span className="ligne-statut"><IndicateurChamp champ={champ} /></span>
    </>
  )
  return (
    <li className={`ligne ${douteux ? 'douteuse' : ''} ${ouvert ? 'ouverte' : ''}`}>
      {onEditer
        ? <button type="button" className="ligne-bouton" onClick={() => onEditer(champ)}>{contenu}</button>
        : onCorriger
          ? <button type="button" className="ligne-bouton" onClick={() => setOuvert(!ouvert)} aria-expanded={ouvert}>{contenu}</button>
          : <div className="ligne-bouton lecture">{contenu}</div>}
      {ouvert && onCorriger && <Edition champ={champ} schema={schema} occupe={occupe} onCorriger={onCorriger} onFermer={() => setOuvert(false)} />}
    </li>
  )
}

// Visites : vrai tableau sur grand écran (une colonne par visite faite), cartes sur téléphone.
// Les deux rendus existent ; une requête de conteneur choisit selon la largeur réellement disponible.
function Visites({ champs, schema, seuil, occupe, onCorriger, onEditer, dateCapture }) {
  const { t, langue } = useLangue()
  const [edition, setEdition] = useState(null)
  const parVisite = new Map()
  for (const c of champs) {
    const v = infosVisite(c.champ)
    if (!parVisite.has(v.index)) parVisite.set(v.index, new Map())
    parVisite.get(v.index).set(v.cle, c)
  }
  const index = schema?.visites?.index || []
  const nom = (i) => (index[i] ? t(`visite.${index[i]}`) : `${i + 1}`)
  const faites = [...parVisite.entries()].filter(([, cs]) => [...cs.values()].some((c) => c.statut !== 'NON_APPLICABLE')).sort((a, b) => a[0] - b[0])
  const nonFaites = [...parVisite.keys()].filter((i) => !faites.some(([j]) => j === i)).sort((a, b) => a - b)
  const cles = Object.keys(schema?.visites?.champs || {}).filter((cle) => faites.some(([, cs]) => cs.has(cle)))
  const champEdite = edition && champs.find((c) => c.champ === edition)

  return (
    <div className="visites">
      {faites.length > 0 && (
        <div className="visites-tableau">
          <table>
            <caption className="sr-only">{t('section.Visites')}</caption>
            <thead>
              <tr>
                <th scope="col"><span className="sr-only">{t('detail.champ')}</span></th>
                {faites.map(([i]) => <th key={i} scope="col">{nom(i)}</th>)}
              </tr>
            </thead>
            <tbody>
              {cles.map((cle) => (
                <tr key={cle}>
                  <th scope="row" dir="auto">{libelleChamp(schema, `grossesse.visites[0].${cle}`, langue, t, false)}</th>
                  {faites.map(([i, cs]) => {
                    const c = cs.get(cle)
                    if (!c) return <td key={i} />
                    const douteux = estDouteux(c, seuil)
                    const valeur = (
                      <>
                        <span dir="auto">
                          {formaterValeur(definitionChamp(schema, c.champ), c.valeur, t)}
                          {datePosterieure(c, dateCapture) && <small className="avertissement-date">{t('dossiers.datePosterieure')}</small>}
                        </span>
                        {(c.statut !== 'CONNU' || c.confirme || c.source === 'manual') && <IndicateurChamp champ={c} />}
                      </>
                    )
                    return (
                      <td key={i} className={douteux ? 'douteuse' : ''}>
                        {onEditer
                          ? <button type="button" onClick={() => onEditer(c)}
                            aria-label={`${libelleChamp(schema, c.champ, langue, t)} : ${formaterValeur(definitionChamp(schema, c.champ), c.valeur, t)}`}>{valeur}</button>
                          : onCorriger
                          ? <button type="button" aria-pressed={edition === c.champ} aria-label={`${libelleChamp(schema, c.champ, langue, t)} : ${formaterValeur(definitionChamp(schema, c.champ), c.valeur, t)}`}
                            onClick={() => setEdition(edition === c.champ ? null : c.champ)}>{valeur}</button>
                          : valeur}
                      </td>
                    )
                  })}
                </tr>
              ))}
            </tbody>
          </table>
          {champEdite && onCorriger && (
            <div className="visites-edition">
              <b dir="auto">{libelleChamp(schema, champEdite.champ, langue, t)}</b>
              <Edition champ={champEdite} schema={schema} occupe={occupe} onCorriger={onCorriger} onFermer={() => setEdition(null)} />
            </div>
          )}
        </div>
      )}
      <div className="visites-cartes">
        {faites.map(([i, cs]) => {
          const liste = [...cs.values()]
          const douteux = liste.some((c) => estDouteux(c, seuil))
          return (
            <details key={i} className="carte-visite" open={douteux}>
              <summary>
                <b>{nom(i)}</b>
                <span>{formaterValeur({ type: 'date' }, cs.get('date_venue')?.valeur ?? null, t)}</span>
                {douteux && <StatutBadge statut="A_REVISER" compact />}
              </summary>
              <ul>{liste.map((c) => <LigneChamp key={c.champ} champ={c} schema={schema} seuil={seuil} occupe={occupe} onCorriger={onCorriger} onEditer={onEditer} dateCapture={dateCapture} sansColonne />)}</ul>
            </details>
          )
        })}
      </div>
      {nonFaites.length > 0 && <p className="aide">{t('detail.visitesNonFaites', { liste: nonFaites.map(nom).join(', ') })}</p>}
    </div>
  )
}

// Une page du dossier, par sections repliables (nombre de champs et de points à vérifier dans l'en-tête).
// onCorriger(champ, page, changement) facultatif : sans lui, lecture seule.
export default function SectionsPage({ page, schema, seuil, occupe, onCorriger, onEditer = null, entete = null, toutOuvert = false, dateCapture = null }) {
  const { t } = useLangue()
  const sections = new Map()
  for (const c of page.champs) {
    const nom = sectionDe(c.champ)
    if (!sections.has(nom)) sections.set(nom, [])
    sections.get(nom).push(c)
  }
  const corriger = onCorriger ? (champ, changement) => onCorriger(champ, page, changement) : null
  const editer = onEditer ? (champ) => onEditer(champ, page) : null
  const peuDeSections = sections.size <= 2
  return (
    <section className="page-detail">
      <h3>{t(`type.${page.type_page}`)} <small className="photo-rang">{t('commun.page', { n: page.page_no })}</small></h3>
      {entete}
      {[...sections.entries()].map(([nom, champs]) => {
        const douteux = champs.filter((c) => estDouteux(c, seuil)).length
        const total = nom === 'Visites' ? champs.filter((c) => c.statut !== 'NON_APPLICABLE').length : champs.length
        return (
          <details key={`${nom}-${toutOuvert}`} className="section-detail" open={toutOuvert || douteux > 0 || peuDeSections}>
            <summary>
              <h4>{t(`section.${nom}`)}</h4>
              <span className="section-compte">
                {t('section.compte', { n: total })}
                {douteux > 0 && <b> · {t('section.aVerifier', { n: douteux })}</b>}
              </span>
            </summary>
            {nom === 'Visites'
              ? <Visites champs={champs} schema={schema} seuil={seuil} occupe={occupe} onCorriger={corriger} onEditer={editer} dateCapture={dateCapture} />
              : <ul className="lignes">{champs.map((c) => <LigneChamp key={c.champ} champ={c} schema={schema} seuil={seuil} occupe={occupe} onCorriger={corriger} onEditer={editer} dateCapture={dateCapture} />)}</ul>}
          </details>
        )
      })}
    </section>
  )
}
