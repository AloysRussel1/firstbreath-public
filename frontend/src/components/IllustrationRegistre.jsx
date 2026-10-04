// Illustration CSS de la page d'origine : feuille du registre inclinée, tampon, trait de scan.
export default function IllustrationRegistre({ petite = false }) {
  return (
    <div className={`illustration ${petite ? 'petite' : ''}`} aria-hidden="true">
      <span className="orbite" />
      <span className="orbite orbite-2" />
      <div className="feuille">
        <div className="feuille-haut"><b>REGISTRE</b><span>MATERNITÉ</span></div>
        <i className="feuille-ligne longue" />
        <i className="feuille-ligne" />
        <div className="feuille-cases"><i /><i /><i /></div>
        <i className="feuille-ligne longue" />
        <i className="feuille-ligne" />
        <span className="feuille-scan" />
        <span className="feuille-tampon">FB / 01</span>
      </div>
    </div>
  )
}
