import { Logo } from '../components/Icones'
import IllustrationRegistre from '../components/IllustrationRegistre'
import SelecteurLangue from '../components/SelecteurLangue'
import { naviguer } from '../etat/route'
import { useProfil } from '../etat/profil'
import { useLangue } from '../i18n'

// Page vitrine, comme la page d'origine : logo, illustration, accroche, étapes 01 / 02 / 03.
export default function Accueil() {
  const { t } = useLangue()
  const { profil } = useProfil()
  const etapes = [1, 2, 3]

  return (
    <div className="vitrine">
      <header className="vitrine-haut">
        <span className="marque">
          <Logo taille={40} />
          <span><b>{t('app.nom')}</b><small>{t('app.sousTitre')}</small></span>
        </span>
        <SelecteurLangue />
      </header>

      <main className="vitrine-corps">
        <section className="hero">
          <p className="surtitre">{t('accueil.surtitre')}</p>
          <h1 className="accroche">{t('accueil.accroche1')}<br /><em>{t('accueil.accroche2')}</em></h1>
          <IllustrationRegistre />
          <p className="intro">{t('accueil.intro')}</p>
          <div className="actions">
            <button type="button" className="bouton bouton-navigation bouton-large" onClick={() => naviguer(profil ? '/app/conversation' : '/profil')}>
              {profil ? t('accueil.continuer', { id: profil.sageFemmeId }) : t('accueil.commencer')}
            </button>
            <a className="lien-texte" href="#/a-propos">{t('accueil.aPropos')}</a>
          </div>
        </section>

        <ol className="etapes-vitrine">
          {etapes.map((n) => (
            <li key={n}>
              <span className="etape-numero">0{n}</span>
              <span><b>{t(`accueil.etape${n}`)}</b><span>{t(`accueil.etape${n}Texte`)}</span></span>
            </li>
          ))}
        </ol>
      </main>

      <footer className="vitrine-pied">{t('accueil.hautDePage')}</footer>
    </div>
  )
}
