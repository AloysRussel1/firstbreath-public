import { useCallback } from 'react'
import { api } from '../api'
import { useConnexion } from '../etat/connexion'
import { useConversation } from '../etat/conversation'
import { useDonnees } from '../etat/donnees'
import { useLangue } from '../i18n'
import { dateLisible } from '../lib/format'

function LigneVisite({ visite }) {
  const { t } = useLangue()
  return (
    <a className="ligne-visite" href={`#/app/dossiers/${visite.dossier_id}`}>
      <span>
        <b>{t('dossiers.visite', { date: dateLisible(visite.date) })}</b>
        <small>
          {visite.numero_fiche ? t('dossiers.fiche', { numero: visite.numero_fiche }) : t('dossiers.sansFiche')}
          {' · '}{t('dossiers.pages', { n: visite.nb_pages })}
        </small>
      </span>
      <span className="tampon">{t(`etat.${visite.etat}`)}</span>
    </a>
  )
}

// Onglet Dossiers : patientes par code de liaison (historique des visites), puis dossiers non reliés.
export default function Dossiers() {
  const { t } = useLangue()
  const { connecte } = useConnexion()
  const { dossier } = useConversation()
  // Recharge quand le dossier de la conversation change d'état (validé, relié…).
  const charger = useCallback(async () => {
    const [d, p] = await Promise.all([api.listeDossiers(), api.patientes()])
    return { dossiers: d.dossiers, patientes: p.patientes, etatConversation: dossier?.etat }
  }, [dossier?.etat])
  const { donnees, chargement, horsLigne, erreur } = useDonnees('liste-dossiers', charger, connecte)

  if (chargement && !donnees) return <section className="ecran-contenu"><p className="aide">{t('commun.chargement')}</p></section>
  const patientes = donnees?.patientes || []
  const nonRelies = (donnees?.dossiers || []).filter((d) => !d.patiente_id)

  return (
    <section className="ecran-contenu dossiers">
      {horsLigne && <p className="bandeau-hors-ligne" role="status">{t('dossiers.horsLigne')}</p>}
      {erreur && <p className="erreur" role="alert">{erreur.message}</p>}
      {patientes.length === 0 && nonRelies.length === 0 && <p className="aide">{t('dossiers.aucun')}</p>}

      {patientes.length > 0 && (
        <div className="groupe-dossiers">
          <h2>{t('dossiers.patientes')}</h2>
          {patientes.map((p) => (
            <article key={p.patiente_id} className="carte-papier carte-patiente">
              <header>
                <span className="code-patiente">{p.code || '—'}</span>
                <small>{p.numero_fiche ? t('dossiers.fiche', { numero: p.numero_fiche }) : t('dossiers.sansFiche')}</small>
              </header>
              <div className="liste-visites">{p.visites.map((v) => <LigneVisite key={v.dossier_id} visite={v} />)}</div>
            </article>
          ))}
        </div>
      )}

      {nonRelies.length > 0 && (
        <div className="groupe-dossiers">
          <h2>{t('dossiers.sansLiaison')}</h2>
          <div className="carte-papier liste-visites">{nonRelies.map((v) => <LigneVisite key={v.dossier_id} visite={v} />)}</div>
        </div>
      )}
    </section>
  )
}
