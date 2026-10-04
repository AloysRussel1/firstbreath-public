import { useCallback, useState } from 'react'
import { api } from '../api'
import { useConnexion } from '../etat/connexion'
import { useDonnees } from '../etat/donnees'
import { useLangue } from '../i18n'

const SEROLOGIES = ['vih', 'syphilis', 'hepatite_c']

// Tuile d'indicateur clé : un grand chiffre, son libellé, un complément.
function Tuile({ valeur, libelle, complement }) {
  return (
    <div className="tuile">
      <b>{valeur}</b>
      <span>{libelle}</span>
      {complement && <small>{complement}</small>}
    </div>
  )
}

// Répartition en barres horizontales simples ; une seule note si des lignes sont masquées.
function Repartition({ indicateur }) {
  const { t, langue } = useLangue()
  const nombre = (x) => new Intl.NumberFormat(langue === 'en' ? 'en-GB' : 'fr-FR', { maximumFractionDigits: 1 }).format(x)
  const unite = indicateur.unite ? ` ${indicateur.unite}` : ''
  const libelle = (c) => {
    if (c.min === null) return `${t('tableau.moins', { max: nombre(c.max) })}${unite}`
    if (c.max === null) return `${t('tableau.auMoins', { min: nombre(c.min) })}${unite}`
    return `${t('tableau.entre', { min: nombre(c.min), max: nombre(c.max) })}${unite}`
  }
  const total = indicateur.dossiers_mesures.effectif
  return (
    <article className="indicateur carte-papier">
      <h3>{t(`indic.${indicateur.id}`)}</h3>
      {!indicateur.disponible ? (
        <p className="aide">{t('tableau.nonDisponible')}</p>
      ) : !total ? (
        <p className="aide">{t('tableau.tropPeu')}</p>
      ) : (
        <>
          <p className="aide">{t('tableau.mesures', { n: total })}</p>
          <ul className="barres">
            {indicateur.cases.map((c, i) => (
              <li key={i}>
                <span className="barre-libelle">{libelle(c)}</span>
                <span className="barre-piste" aria-hidden="true">
                  {!c.masque && <span className="barre" style={{ width: `${Math.max(1.5, (100 * c.effectif) / total)}%` }} />}
                </span>
                <span className="barre-valeur">{c.masque ? '—' : `${nombre((100 * c.effectif) / total)} % (${c.effectif})`}</span>
              </li>
            ))}
          </ul>
          {indicateur.masquage && <p className="note-masque">{t('tableau.noteMasque')}</p>}
        </>
      )}
    </article>
  )
}

// Tableau de bord : tendances anonymes pour le système de santé, jamais une patiente en particulier.
export default function TableauBord() {
  const { t, langue } = useLangue()
  const { connecte } = useConnexion()
  const [source, setSource] = useState('dossiers')
  const charger = useCallback(() => api.tableauDeBord(source), [source])
  const { donnees, chargement, horsLigne, erreur } = useDonnees(`tableau-de-bord:${source}`, charger, connecte)
  const pct = (x) => (x === null || x === undefined ? null : `${new Intl.NumberFormat(langue === 'en' ? 'en-GB' : 'fr-FR', { maximumFractionDigits: 1 }).format(x)} %`)
  const indic = Object.fromEntries((donnees?.indicateurs || []).map((i) => [i.id, i]))
  const depistage = Object.fromEntries((donnees?.depistage || []).map((d) => [d.id, d]))
  const peuDeDossiers = source === 'dossiers' && donnees?.dossiers?.masque
  const masquageCles = SEROLOGIES.some((s) => depistage[s] && (depistage[s].positifs.masque || depistage[s].depistees.masque))

  return (
    <section className="ecran-contenu tableau">
      <div className="carte-papier tableau-explication">
        <h2>{t('tableau.aQuoiSert')}</h2>
        <p>{t('tableau.explication')}</p>
      </div>

      <div className="tableau-source" role="radiogroup" aria-label={t('tableau.source')}>
        {['dossiers', 'demo'].map((s) => (
          <button key={s} type="button" role="radio" aria-checked={source === s} onClick={() => setSource(s)}>
            {t(s === 'dossiers' ? 'tableau.sourceDossiers' : 'tableau.sourceDemo')}
          </button>
        ))}
      </div>

      {donnees?.synthetique && <p className="bandeau-demo" role="note">{t('tableau.bandeauDemo')}</p>}
      {horsLigne && <p className="bandeau-hors-ligne" role="status">{donnees ? t('dossiers.horsLigne') : t('tableau.horsLigne')}</p>}
      {erreur && <p className="erreur" role="alert">{erreur.message}</p>}
      {chargement && !donnees && <p className="aide">{t('commun.chargement')}</p>}

      {peuDeDossiers && (
        <div className="carte-papier proposer-demo">
          <p>{t('tableau.proposerDemo')}</p>
          <button type="button" className="bouton" onClick={() => setSource('demo')}>{t('tableau.voirDemo')}</button>
        </div>
      )}

      {donnees && (
        <>
          <h2 className="tableau-titre">{t('tableau.cles')}</h2>
          <div className="tuiles">
            <Tuile valeur={donnees.dossiers.masque ? '—' : donnees.dossiers.effectif}
              libelle={t(donnees.synthetique ? 'tableau.lignesDemo' : 'tableau.dossiersValides')} />
            {SEROLOGIES.map((s) => depistage[s] && (
              <Tuile key={s}
                valeur={pct(depistage[s].part_depistees) || '—'}
                libelle={t('tableau.depistees', { test: t(`indic.${s}`) })}
                complement={t('tableau.positifs', { part: pct(depistage[s].part_positifs) || '—' })} />
            ))}
          </div>
          {masquageCles && <p className="note-masque">{t('tableau.noteMasque')}</p>}

          <h2 className="tableau-titre">{t('tableau.tension')}</h2>
          <div className="indicateurs">
            {indic.tension_systolique && <Repartition indicateur={indic.tension_systolique} />}
            {indic.tension_diastolique && <Repartition indicateur={indic.tension_diastolique} />}
          </div>

          <h2 className="tableau-titre">{t('tableau.temperature')}</h2>
          <div className="indicateurs">
            {indic.temperature_mere && <Repartition indicateur={indic.temperature_mere} />}
            {indic.temperature_nouveau_ne && <Repartition indicateur={indic.temperature_nouveau_ne} />}
          </div>
          <p className="aide">{t('tableau.seuil', { seuil: donnees.seuil_anonymat })}</p>
        </>
      )}
    </section>
  )
}
