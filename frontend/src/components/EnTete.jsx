import { useConnexion } from '../etat/connexion'
import { useProfil } from '../etat/profil'
import { useLangue } from '../i18n'
import { IconeConnexion, Logo } from './Icones'

// En-tête de l'application : logo (retour à l'accueil), titre de l'écran, pastille de connexion,
// identité connectée ; le bouton « Simuler hors ligne » est affiché sur l'écran Conversation.
export default function EnTete({ titre, avecSimulation = false }) {
  const { t } = useLangue()
  const { profil } = useProfil()
  const { connecte, verifie, simule, basculerSimulation } = useConnexion()
  const etat = simule ? 'simule' : !verifie ? 'verification' : connecte ? 'en-ligne' : 'hors-ligne'
  const libelle = { simule: t('connexion.simule'), verification: t('connexion.verification'), 'en-ligne': t('connexion.enLigne'), 'hors-ligne': t('connexion.horsLigne') }[etat]

  return (
    <header className="entete">
      <a href="#/accueil" className="entete-logo" aria-label={t('nav.accueil')}><Logo taille={38} /></a>
      <div className="entete-texte">
        <b className="entete-titre">{titre}</b>
        <span className="entete-ligne">
          <span className={`pastille ${etat}`} role="status"><i aria-hidden="true" />{libelle}</span>
          {profil && <span className="identite" title={t(`profil.role.${profil.role}`)}>{profil.sageFemmeId} · {t(`profil.role.${profil.role}`)}</span>}
        </span>
      </div>
      {avecSimulation && (
        <button type="button" className={`bouton-simulation ${simule ? 'actif' : ''}`} aria-pressed={simule} onClick={basculerSimulation}>
          <IconeConnexion coupee={!simule} />
          <span>{simule ? t('connexion.retablir') : t('connexion.simuler')}</span>
        </button>
      )}
    </header>
  )
}
