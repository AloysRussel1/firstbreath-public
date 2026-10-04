import { useEffect, useState } from 'react'
import SelecteurLangue from '../components/SelecteurLangue'
import { useConnexion } from '../etat/connexion'
import { useConversation } from '../etat/conversation'
import { useProfil } from '../etat/profil'
import { useLangue } from '../i18n'
import { effacerTout } from '../lib/coffre'
import { api } from '../api'
import { CLES_LOCALES, controleQualiteActif, definirControleQualite, definirPanneCentrale, panneCentraleSimulee } from '../lib/preferences'

const EN_ATTENTE = ['QUALITE', 'EN_FILE', 'ENVOI', 'A_TRAITER', 'CAPTURE', 'EN_ATTENTE_IA']

function Interrupteur({ id, actif, onChange, libelle, aide }) {
  return (
    <div className="interrupteur">
      <span>
        <label htmlFor={id}><b>{libelle}</b></label>
        {aide && <small id={`${id}-aide`}>{aide}</small>}
      </span>
      <input id={id} type="checkbox" role="switch" checked={actif} aria-describedby={aide ? `${id}-aide` : undefined}
        onChange={(e) => onChange(e.target.checked)} />
    </div>
  )
}

// Réglages : langue, profil et rôle, connexion simulée, file d'attente, contrôle de qualité, stockage.
export default function Reglages() {
  const { t } = useLangue()
  const { profil } = useProfil()
  const { connecte, simule, basculerSimulation } = useConnexion()
  const { captures } = useConversation()
  const [qualite, setQualite] = useState(controleQualiteActif)
  const [panne, setPanne] = useState(panneCentraleSimulee)
  const [aSynchroniser, setASynchroniser] = useState(null)
  const [resultatSync, setResultatSync] = useState(null)
  const enFile = captures.filter((c) => EN_ATTENTE.includes(c.etat)).length

  // Dossiers enregistrés en attente de synchronisation (ou en échec), lus sur le serveur.
  useEffect(() => {
    if (!connecte) return undefined
    let actif = true
    api.listeDossiers()
      .then((r) => { if (actif) setASynchroniser(r.dossiers.filter((d) => ['ENREGISTRE', 'ECHEC_SYNCHRONISATION'].includes(d.etat)).length) })
      .catch(() => {})
    return () => { actif = false }
  }, [connecte, resultatSync])

  async function synchroniser() {
    try {
      const r = await api.synchroniser({ simulerPanne: panne })
      setResultatSync(t('reglages.syncResultat', { n: r.synchronises.length, e: r.echecs.length }))
    } catch (erreur) {
      setResultatSync(erreur.hors_ligne ? t('connexion.horsLigne') : t('msg.valeurRefusee'))
    }
  }

  async function effacer() {
    if (!window.confirm(t('reglages.effacerConfirmer'))) return
    await effacerTout().catch(() => {})
    for (const cle of CLES_LOCALES) {
      try { localStorage.removeItem(cle) } catch { /* stockage indisponible */ }
    }
    window.location.reload()
  }

  return (
    <section className="ecran-contenu reglages">
      <div className="carte-papier groupe-reglage">
        <h2>{t('langue.choix')}</h2>
        <SelecteurLangue />
      </div>

      <div className="carte-papier groupe-reglage">
        <h2>{t('reglages.profil')}</h2>
        {profil && <p><b>{profil.sageFemmeId}</b> · {t(`profil.role.${profil.role}`)}</p>}
        <p className="aide">{profil && t(`profil.role.${profil.role}Aide`)}</p>
        <a className="lien-texte" href="#/profil">{t('reglages.modifierProfil')}</a>
      </div>

      <div className="carte-papier groupe-reglage">
        <h2>{t('reglages.connexion')}</h2>
        <p role="status">{simule ? t('connexion.simule') : connecte ? t('connexion.enLigne') : t('connexion.horsLigne')}</p>
        <Interrupteur id="simuler" actif={simule} onChange={basculerSimulation} libelle={t('connexion.simuler')} aide={t('reglages.simulerAide')} />
      </div>

      <div className="carte-papier groupe-reglage">
        <h2>{t('reglages.file')}</h2>
        <p role="status">{enFile ? t('reglages.fileEtat', { n: enFile }) : t('reglages.fileVide')}</p>
      </div>

      <div className="carte-papier groupe-reglage">
        <h2>{t('reglages.sync')}</h2>
        <p className="aide">{t('reglages.syncAide')}</p>
        {aSynchroniser !== null && <p role="status">{t('reglages.syncEnAttente', { n: aSynchroniser })}</p>}
        <button type="button" className="bouton" disabled={!connecte} onClick={synchroniser}>{t('reglages.syncMaintenant')}</button>
        {resultatSync && <p role="status">{resultatSync}</p>}
        <Interrupteur id="panne" actif={panne} libelle={t('reglages.panne')} aide={t('reglages.panneAide')}
          onChange={(actif) => { definirPanneCentrale(actif); setPanne(actif) }} />
      </div>

      <div className="carte-papier groupe-reglage">
        <Interrupteur id="qualite" actif={qualite} libelle={t('reglages.qualite')} aide={t('reglages.qualiteAide')}
          onChange={(actif) => { definirControleQualite(actif); setQualite(actif) }} />
      </div>

      <div className="carte-papier groupe-reglage">
        <h2>{t('reglages.stockage')}</h2>
        <p className="aide">{t('reglages.stockageAide')}</p>
        <button type="button" className="bouton" onClick={effacer}>{t('reglages.effacer')}</button>
      </div>

      <a className="lien-texte" href="#/a-propos">{t('reglages.aPropos')}</a>
    </section>
  )
}
