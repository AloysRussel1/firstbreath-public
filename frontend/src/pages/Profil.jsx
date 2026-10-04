import { useState } from 'react'
import { IconeRetour, Logo } from '../components/Icones'
import SelecteurLangue from '../components/SelecteurLangue'
import { useProfil } from '../etat/profil'
import { identifiantValide, ROLES } from '../lib/roles'
import { naviguer } from '../etat/route'
import { useLangue } from '../i18n'

// Identifiant professionnel et rôle, mémorisés sur l'appareil (envoyés dans X-Sage-Femme-Id et X-Role).
export default function Profil() {
  const { t } = useLangue()
  const { profil, enregistrer } = useProfil()
  const [identifiant, setIdentifiant] = useState(profil?.sageFemmeId || '')
  const [role, setRole] = useState(profil?.role || 'SAGE_FEMME')
  const [essai, setEssai] = useState(false)
  const valide = identifiantValide(identifiant.trim())

  function soumettre(evenement) {
    evenement.preventDefault()
    setEssai(true)
    if (!valide) return
    enregistrer({ sageFemmeId: identifiant.trim(), role })
    naviguer('/app/conversation')
  }

  return (
    <div className="vitrine">
      <header className="vitrine-haut">
        <button type="button" className="bouton-icone" onClick={() => window.history.back()} aria-label={t('commun.retour')}><IconeRetour /></button>
        <span className="marque"><Logo taille={34} /><b>{t('app.nom')}</b></span>
        <SelecteurLangue />
      </header>
      <main className="vitrine-corps etroit">
        <h1 className="titre-page">{t('profil.titre')}</h1>
        <p className="intro">{t('profil.intro')}</p>
        <form className="formulaire carte-papier" onSubmit={soumettre} noValidate>
          <div className="champ-formulaire">
            <label htmlFor="identifiant">{t('profil.identifiant')}</label>
            <input id="identifiant" autoComplete="off" autoCapitalize="none" value={identifiant}
              aria-invalid={essai && !valide} aria-describedby="aide-identifiant"
              onChange={(e) => setIdentifiant(e.target.value)} placeholder="sf_01" />
            <p className="aide" id="aide-identifiant">{t('profil.identifiantAide')}</p>
            {essai && !valide && <p className="erreur" role="alert">{t('profil.identifiantInvalide')}</p>}
          </div>
          <fieldset className="choix-role">
            <legend>{t('profil.role')}</legend>
            {ROLES.map((r) => (
              <label key={r} className={`option-role ${role === r ? 'choisie' : ''}`}>
                <input type="radio" name="role" value={r} checked={role === r} onChange={() => setRole(r)} />
                <span><b>{t(`profil.role.${r}`)}</b><small>{t(`profil.role.${r}Aide`)}</small></span>
              </label>
            ))}
          </fieldset>
          <button type="submit" className="bouton bouton-navigation bouton-large">{t('profil.valider')}</button>
        </form>
      </main>
    </div>
  )
}
