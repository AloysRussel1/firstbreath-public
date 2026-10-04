import { useLangue } from '../i18n'
import { definitionChamp, formaterValeur, libelleChamp } from '../lib/format'

const VISIBLES = 6

// Message de blocage « vivant » : recalculé à chaque changement (blocages du fournisseur de conversation).
// Chaque question restante est nommée (page, champ, valeur lue) avec [Vérifier] qui l'ouvre directement.
// Quand plus rien ne bloque : « Tout est vérifié » et [Valider le dossier].
export default function MessageBlocage({ message, blocages, schema, clos, occupe, onChoisir }) {
  const { t, langue } = useLangue()
  const libelle = (cle) => libelleChamp(schema, cle, langue, t)
  const valeur = (cle, v) => formaterValeur(definitionChamp(schema, cle), v, t)
  const bouton = (id, cle, params) => (
    <button type="button" className="lien-bouton" disabled={occupe} onClick={() => onChoisir({ id, libelle: { cle, params } }, message)}>
      {t(cle, params)}
    </button>
  )

  if (clos) return <div className="bulle bulle-agent"><p>{t('valid.clos')}</p></div>
  if (blocages.aucun && !message.invalides) {
    return (
      <div className="bulle bulle-agent blocage" role="status">
        <p><b>{t('valid.toutVerifie')}</b></p>
        <div className="choix-rapides">
          <button type="button" className="navigation" disabled={occupe} onClick={() => onChoisir({ id: 'valider', libelle: { cle: 'option.valider' } }, message)}>
            {t('option.valider')}
          </button>
        </div>
      </div>
    )
  }

  const { obligatoires, questions, enLecture, comparaison } = blocages
  const ligneQuestion = (q) => (
    <li key={`${q.pageNo}:${q.cle}`}>
      <span>
        <b>{t(`type.${q.typePage}`)}</b>
        {' — '}<span dir="auto">{libelle(q.cle)}</span>
        {' : '}{q.valeur === null || q.valeur === undefined ? t('valid.pasLu') : <>{t('valid.lu')} « <span dir="auto">{valeur(q.cle, q.valeur)}</span> »</>}
      </span>
      {bouton(`verifier:${q.pageNo}:${q.cle}`, 'option.verifier')}
    </li>
  )
  return (
    <div className="bulle bulle-agent large blocage" role="status">
      <p><b>{t('valid.bloque')}</b></p>
      <ul className="blocages">
        {enLecture > 0 && <li><span>{t('valid.enLecture', { n: enLecture })}</span></li>}
        {comparaison && <li><span>{t('valid.comparaison')}</span>{bouton(`aller:${comparaison}`, 'option.voirComparaison')}</li>}
        {obligatoires.map((o) => (
          <li key={o.cle}>
            <span>
              {o.page && <b>{t(`type.${o.page.type_page}`)} — </b>}
              <span dir="auto">{libelle(o.cle)}</span> : {o.valeur === null
                ? t('valid.aSaisir')
                : <>{t('valid.lu')} « <span dir="auto">{valeur(o.cle, o.valeur)}</span> »</>}
            </span>
            {o.page ? bouton(`verifier:${o.page.page_no}:${o.cle}`, o.valeur === null ? 'option.saisir' : 'option.verifier') : bouton('photo', 'option.photoIdentification')}
          </li>
        ))}
        {message.invalides && <li><span>{t('valid.invalide')}</span>{bouton('detail', 'option.detail')}</li>}
      </ul>
      {questions.length > 0 && (
        <>
          <p className="blocages-titre">{t('valid.questions', { n: questions.length })}</p>
          <ul className="blocages">{questions.slice(0, VISIBLES).map(ligneQuestion)}</ul>
          {questions.length > VISIBLES && (
            <details className="blocages-suite">
              <summary>{t('valid.autres', { n: questions.length - VISIBLES })}</summary>
              <ul className="blocages">{questions.slice(VISIBLES).map(ligneQuestion)}</ul>
            </details>
          )}
          <div className="choix-rapides">
            <button type="button" disabled={occupe} onClick={() => onChoisir({ id: 'filtre', libelle: { cle: 'option.voirAVerifier' } }, message)}>
              {t('option.voirAVerifier', { n: questions.length + obligatoires.length })}
            </button>
          </div>
        </>
      )}
    </div>
  )
}
