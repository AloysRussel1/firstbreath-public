import { IconeRetour, Logo } from '../components/Icones'
import IllustrationRegistre from '../components/IllustrationRegistre'
import SelecteurLangue from '../components/SelecteurLangue'
import { useLangue } from '../i18n'

// Présentation du projet pour la démo : problème, solution, confidentialité, modèles, hors périmètre.
export default function APropos() {
  const { t } = useLangue()
  const sections = ['probleme', 'solution', 'confidentialite']
  return (
    <div className="vitrine">
      <header className="vitrine-haut">
        <button type="button" className="bouton-icone" onClick={() => window.history.back()} aria-label={t('commun.retour')}><IconeRetour /></button>
        <span className="marque"><Logo taille={34} /><b>{t('app.nom')}</b></span>
        <SelecteurLangue />
      </header>
      <main className="vitrine-corps etroit">
        <h1 className="titre-page">{t('apropos.titre')}</h1>
        <IllustrationRegistre petite />
        {sections.map((s, i) => (
          <section key={s} className="bloc-apropos">
            <span className="etape-numero">0{i + 1}</span>
            <div>
              <h2>{t(`apropos.${s}.titre`)}</h2>
              <p>{t(`apropos.${s}.texte`)}</p>
            </div>
          </section>
        ))}
        <section className="bloc-apropos">
          <span className="etape-numero">04</span>
          <div>
            <h2>{t('apropos.modeles.titre')}</h2>
            <ul>
              <li>{t('apropos.modeles.sonnet')}</li>
              <li>{t('apropos.modeles.opus')}</li>
              <li>{t('apropos.modeles.haiku')}</li>
            </ul>
          </div>
        </section>
        <section className="bloc-apropos">
          <span className="etape-numero">05</span>
          <div>
            <h2>{t('apropos.limites.titre')}</h2>
            <p>{t('apropos.limites.texte')}</p>
          </div>
        </section>
      </main>
    </div>
  )
}
