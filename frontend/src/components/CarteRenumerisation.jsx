import { useState } from 'react'
import { useLangue } from '../i18n'
import { definitionChamp, formaterValeur, libelleChamp } from '../lib/format'

// Renumérisation compacte : un tableau des SEULS champs qui diffèrent (champ, dossier existant, nouvelle photo,
// choix), des actions groupées et un choix ligne par ligne. Les champs identiques sont repliés.
// Rien n'est choisi à la place de la sage-femme : par défaut, le dossier existant est conservé.
export default function CarteRenumerisation({ message, schema, reponse, occupe, onAppliquer }) {
  const { t, langue } = useLangue()
  const [nouvelles, setNouvelles] = useState(() => new Set())
  const fige = reponse !== undefined
  const retenues = fige ? new Set(reponse) : nouvelles
  const libelle = (cle) => libelleChamp(schema, cle, langue, t)
  const valeur = (cle, v) => formaterValeur(definitionChamp(schema, cle), v, t)
  const choisir = (cle, prendre) => setNouvelles((n) => {
    const suivant = new Set(n)
    if (prendre) suivant.add(cle)
    else suivant.delete(cle)
    return suivant
  })
  const identiques = message.identiques || []

  return (
    <div className="renum">
      {!fige && (
        <div className="renum-groupe" role="group" aria-label={t('renum.actionsGroupees')}>
          <button type="button" disabled={occupe} onClick={() => setNouvelles(new Set())}>{t('renum.toutGarder')}</button>
          <button type="button" disabled={occupe} onClick={() => setNouvelles(new Set(message.lignes.map((l) => l.cle)))}>{t('renum.toutPrendre')}</button>
        </div>
      )}
      <div className="renum-entete-etroit" aria-hidden="true"><span>{t('renum.ancienne')}</span><span>{t('renum.nouvelle')}</span></div>
      <table className="renum-table">
        <thead>
          <tr>
            <th scope="col">{t('renum.champ')}</th>
            <th scope="col">{t('renum.ancienne')}</th>
            <th scope="col">{t('renum.nouvelle')}</th>
            <th scope="col">{t('renum.choix')}</th>
          </tr>
        </thead>
        <tbody>
          {message.lignes.map((l) => {
            const prendre = retenues.has(l.cle)
            return (
              <tr key={l.cle}>
                <th scope="row" dir="auto">{libelle(l.cle)}</th>
                <td className={prendre ? '' : 'retenue'} dir="auto">{valeur(l.cle, l.ancienne)}</td>
                <td className={prendre ? 'retenue' : ''} dir="auto">{valeur(l.cle, l.nouvelle)}</td>
                <td>
                  <div className="renum-choix" role="radiogroup" aria-label={libelle(l.cle)}>
                    {/* Large : « Garder / Remplacer ». Étroit : les boutons portent directement les deux valeurs. */}
                    <button type="button" role="radio" aria-checked={!prendre} disabled={fige || occupe} onClick={() => choisir(l.cle, false)}
                      aria-label={`${t('renum.garder')} : ${valeur(l.cle, l.ancienne)}`}>
                      <span className="choix-court">{t('renum.garder')}</span><span className="choix-valeur" dir="auto">{valeur(l.cle, l.ancienne)}</span>
                    </button>
                    <button type="button" role="radio" aria-checked={prendre} disabled={fige || occupe} onClick={() => choisir(l.cle, true)}
                      aria-label={`${t('renum.remplacer')} : ${valeur(l.cle, l.nouvelle)}`}>
                      <span className="choix-court">{t('renum.remplacer')}</span><span className="choix-valeur" dir="auto">{valeur(l.cle, l.nouvelle)}</span>
                    </button>
                  </div>
                </td>
              </tr>
            )
          })}
        </tbody>
      </table>
      {identiques.length > 0 && (
        <details className="renum-identiques">
          <summary>{t('renum.identiques', { n: identiques.length })}</summary>
          <ul>{identiques.map((l) => <li key={l.cle}><span dir="auto">{libelle(l.cle)}</span> : <b dir="auto">{valeur(l.cle, l.valeur)}</b></li>)}</ul>
        </details>
      )}
      {!fige && (
        <button type="button" className="bouton renum-appliquer" disabled={occupe} onClick={() => onAppliquer([...nouvelles])}>
          {t('renum.appliquerN', { n: nouvelles.size })}
        </button>
      )}
    </div>
  )
}
