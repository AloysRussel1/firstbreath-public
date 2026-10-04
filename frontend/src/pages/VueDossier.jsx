import { useCallback, useEffect, useState } from 'react'
import { api } from '../api'
import { IconeRetour } from '../components/Icones'
import SaisieCode from '../components/SaisieCode'
import SectionsPage from '../components/SectionsDossier'
import { useConnexion } from '../etat/connexion'
import { useConversation } from '../etat/conversation'
import { useDonnees } from '../etat/donnees'
import { useLangue } from '../i18n'
import { dateLisible } from '../lib/format'
import { panneCentraleSimulee } from '../lib/preferences'

const ETATS_VALIDES = ['VALIDE', 'PATIENTE_LIEE', 'ENREGISTRE', 'SYNCHRONISE', 'ECHEC_SYNCHRONISATION']

// Photo d'origine d'une page : chargée à la demande, accès selon le rôle (GET /captures/{id}/image).
function PhotoOrigine({ capture }) {
  const { t } = useLangue()
  if (!capture) return null
  return (
    <div className="photo-origine-bloc">
      <p className="aide">{t('dossiers.capture', { date: dateLisible(capture.date_capture), sf: capture.sage_femme_id || '—', etat: t(`etat.${capture.etat}`) })}</p>
      <ChargeurPhoto captureId={capture.capture_id} />
    </div>
  )
}

function ChargeurPhoto({ captureId }) {
  const { t } = useLangue()
  const [etat, setEtat] = useState({ url: null, message: null, chargement: false })
  useEffect(() => () => { if (etat.url) URL.revokeObjectURL(etat.url) }, [etat.url])
  if (!captureId) return null
  async function charger() {
    setEtat({ url: null, message: null, chargement: true })
    try {
      const blob = await api.image(captureId)
      setEtat({ url: URL.createObjectURL(blob), message: null, chargement: false })
    } catch (erreur) {
      const message = erreur.statut === 403 ? 'dossiers.photoRefusee' : 'dossiers.photoAbsente'
      setEtat({ url: null, message, chargement: false })
    }
  }
  if (etat.url) return <img className="photo-origine" src={etat.url} alt={t('dossiers.photo')} />
  return (
    <div className="photo-origine-zone">
      <button type="button" className="lien-texte" disabled={etat.chargement} onClick={charger}>{t('dossiers.voirPhoto')}</button>
      {etat.message && <p className="aide" role="status">{t(etat.message)}</p>}
    </div>
  )
}

// Liaison décidée plus tard, depuis le dossier : mêmes choix que dans la conversation, jamais automatique.
function Liaison({ dossier, onLie }) {
  const { t } = useLangue()
  const [candidats, setCandidats] = useState(null)
  const [codeCree, setCodeCree] = useState(null)
  const [message, setMessage] = useState(null)
  const [occupe, setOccupe] = useState(false)
  const [codeCherche, setCodeCherche] = useState(null)

  async function agir(action) {
    setOccupe(true)
    setMessage(null)
    try { await action() } catch (erreur) {
      setMessage(erreur.hors_ligne ? t('liaison.horsLigne') : erreur.message)
    } finally { setOccupe(false) }
  }
  const chercher = (code) => agir(async () => {
    setCodeCherche(code)
    setCandidats((await api.correspondances({ numero: dossier.numero_fiche, code })).candidates)
  })
  const lier = (choix) => agir(async () => {
    const r = await api.lier(dossier.dossier_id, choix)
    if (r.patient_created) setCodeCree(r.code)
    else onLie(r.dossier)
    if (!r.patient_created) setMessage(t('liaison.liee', { code: r.code || '—' }))
  })

  if (codeCree) {
    return (
      <div className="carte-papier liaison">
        <p>{t('liaison.codeCree')}</p>
        <p className="code-liaison">{codeCree}</p>
        <button type="button" className="bouton" onClick={() => agir(async () => onLie(await api.dossier(dossier.dossier_id)))}>{t('liaison.codeRecopie')}</button>
      </div>
    )
  }
  return (
    <div className="carte-papier liaison">
      <p><b>{t('dossiers.relier')}</b></p>
      {candidats === null ? (
        <>
          <p>{t('liaison.saisirCode')}</p>
          <SaisieCode occupe={occupe} onSoumettre={chercher} />
          <button type="button" className="lien-texte" disabled={occupe} onClick={() => chercher(null)}>{t('liaison.nonCode')}</button>
        </>
      ) : (
        <>
          <p>{t(candidats.length ? 'liaison.candidates' : 'liaison.aucuneCandidate')}</p>
          <div className="choix-rapides liste">
            {candidats.map((c, i) => (
              <button type="button" key={c.patiente_id} disabled={occupe} onClick={() => lier({ patiente_id: c.patiente_id, code: c.code })}>
                {t('liaison.patiente', { n: i + 1, code: c.code || '—', numero: c.numero_fiche || '—', visites: t('liaison.visites', { n: c.nb_visites }), date: dateLisible(c.derniere_visite) })}
              </button>
            ))}
            {codeCherche && candidats.length === 0 && (
              <button type="button" disabled={occupe} onClick={() => lier({ choix: 'nouvelle', code: codeCherche })}>{t('liaison.creerAvecCode', { code: codeCherche })}</button>
            )}
            <button type="button" disabled={occupe} onClick={() => lier({ choix: 'nouvelle' })}>{t(candidats.length ? 'liaison.creer' : 'liaison.creerSeule')}</button>
            <button type="button" disabled={occupe} onClick={() => { setCandidats(null); setMessage(t('liaison.plusTard')) }}>{t('liaison.inconnu')}</button>
          </div>
        </>
      )}
      {message && <p className="aide" role="status">{message}</p>}
    </div>
  )
}

// Vue détaillée d'un dossier : sections par page, cartes de visites, statuts neutres, photo d'origine, historique.
export default function VueDossier({ dossierId }) {
  const { t } = useLangue()
  const { connecte } = useConnexion()
  const { schema, seuil } = useConversation()
  const charger = useCallback(async () => {
    const [dossier, historique] = await Promise.all([api.dossier(dossierId), api.historique(dossierId)])
    return { dossier, historique }
  }, [dossierId])
  const { donnees, chargement, horsLigne, erreur, recharger } = useDonnees(`dossier:${dossierId}`, charger, connecte)

  const retour = <a className="lien-retour" href="#/app/dossiers"><IconeRetour /> {t('commun.retour')}</a>
  if (chargement && !donnees) return <section className="ecran-contenu">{retour}<p className="aide">{t('commun.chargement')}</p></section>
  if (!donnees?.dossier) {
    return <section className="ecran-contenu">{retour}<p className="aide">{horsLigne ? t('dossiers.horsLigne') : erreur?.message || t('dossiers.introuvable')}</p></section>
  }
  const { dossier, historique } = donnees
  const pages = [...dossier.pages].sort((a, b) => a.page_no - b.page_no)
  const captureDe = (page) => [...(dossier.captures || [])].reverse().find((c) => c.page_no === page.page_no)

  return (
    <section className="ecran-contenu vue-dossier">
      {retour}
      {horsLigne && <p className="bandeau-hors-ligne" role="status">{t('dossiers.horsLigne')}</p>}
      <header className="carte-papier vue-dossier-tete">
        {dossier.patiente_code && <span className="code-patiente">{dossier.patiente_code}</span>}
        <h2 dir="auto">{dossier.numero_fiche ? t('dossiers.fiche', { numero: dossier.numero_fiche }) : t('dossiers.sansFiche')}</h2>
        <p><span className="tampon">{t(`etat.${dossier.etat}`)}</span> <small>{t('dossiers.pages', { n: pages.length })}</small></p>
      </header>

      {!dossier.patiente_id && ETATS_VALIDES.includes(dossier.etat) && connecte && (
        <Liaison dossier={dossier} onLie={() => recharger()} />
      )}

      {connecte && ['VALIDE', 'PATIENTE_LIEE', 'ENREGISTRE', 'ECHEC_SYNCHRONISATION'].includes(dossier.etat) && (
        <button type="button" className="bouton" onClick={async () => {
          try {
            if (['VALIDE', 'PATIENTE_LIEE'].includes(dossier.etat)) await api.enregistrer(dossier.dossier_id)
            await api.synchroniser({ simulerPanne: panneCentraleSimulee() })
          } finally { recharger() }
        }}>
          {dossier.etat === 'ECHEC_SYNCHRONISATION' || dossier.etat === 'ENREGISTRE' ? t('dossiers.resynchroniser') : t('dossiers.enregistrer')}
        </button>
      )}

      {pages.map((page) => (
        <div key={page.page_no} className="carte-papier vue-page">
          <SectionsPage page={page} schema={schema} seuil={seuil} occupe entete={<PhotoOrigine capture={captureDe(page)} />} />
        </div>
      ))}

      {historique?.transitions?.length > 0 && (
        <details className="carte-papier historique">
          <summary><b>{t('dossiers.historique')}</b></summary>
          <ol>
            {historique.transitions.map((h, i) => (
              <li key={i}>
                <span>{dateLisible(h.changed_at)}</span>
                <span>{t(`etat.${h.from_state}`)} → <b>{t(`etat.${h.to_state}`)}</b></span>
                <small>{h.actor_id}</small>
              </li>
            ))}
          </ol>
        </details>
      )}
    </section>
  )
}
