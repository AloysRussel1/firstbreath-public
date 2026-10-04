import { useState } from 'react'
import { useLangue } from '../i18n'
import { lisible } from '../lib/format'

// Saisie d'une valeur au type du schéma (shared/schema_champs.json). onValider reçoit la valeur typée.
export default function EditeurValeur({ definition, valeurInitiale, onValider, onAnnuler, libelleValider = null, variante = '' }) {
  const { t } = useLangue()
  const type = definition?.type || 'texte'
  const [texte, setTexte] = useState(valeurInitiale ?? '')
  const [liste, setListe] = useState(Array.isArray(valeurInitiale) ? valeurInitiale : [])
  const [tension, setTension] = useState(() => (typeof valeurInitiale === 'string' ? valeurInitiale.split('/') : ['', '']))

  if (type === 'booleen') {
    return (
      <div className={`editeur choix-rapides ${variante}`}>
        <button type="button" onClick={() => onValider(true)}>{t('valeur.oui')}</button>
        <button type="button" onClick={() => onValider(false)}>{t('valeur.non')}</button>
        <button type="button" onClick={onAnnuler}>{t('commun.annuler')}</button>
      </div>
    )
  }
  if (type === 'choix') {
    return (
      <div className={`editeur choix-rapides ${variante}`}>
        {definition.choix.map((c) => <button type="button" key={c} onClick={() => onValider(c)}>{lisible(c)}</button>)}
        <button type="button" onClick={onAnnuler}>{t('commun.annuler')}</button>
      </div>
    )
  }
  if (type === 'liste_choix') {
    const basculer = (c) => setListe((l) => (l.includes(c) ? l.filter((x) => x !== c) : [...l, c]))
    return (
      <div className={`editeur ${variante}`}>
        <p className="aide">{t('editeur.cochezAide')}</p>
        <div className="puces">
          {definition.choix.map((c) => (
            <button type="button" key={c} className={`puce ${liste.includes(c) ? 'active' : ''}`} aria-pressed={liste.includes(c)} onClick={() => basculer(c)}>
              <span aria-hidden="true">{liste.includes(c) ? '☑' : '☐'}</span> {lisible(c)}
            </button>
          ))}
        </div>
        <div className="choix-rapides">
          <button type="button" onClick={() => onValider(liste)}>{t('editeur.cochees', { n: liste.length })}</button>
          <button type="button" onClick={onAnnuler}>{t('commun.annuler')}</button>
        </div>
      </div>
    )
  }
  if (type === 'liste_objets') {
    return (
      <div className={`editeur ${variante}`}>
        <p className="aide">{t('editeur.tableau')}</p>
        <div className="choix-rapides"><button type="button" onClick={onAnnuler}>{t('commun.fermer')}</button></div>
      </div>
    )
  }

  function soumettre(evenement) {
    evenement.preventDefault()
    if (type === 'tension') {
      const [s, d] = tension.map((x) => String(x).trim())
      if (s && d) onValider(`${s}/${d}`)
      return
    }
    const brut = String(texte).trim()
    if (!brut) return
    if (type === 'entier') onValider(Number.parseInt(brut, 10))
    else if (type === 'decimal') onValider(Number.parseFloat(brut.replace(',', '.')))
    else onValider(brut)
  }

  return (
    <form className={`editeur ${variante}`} onSubmit={soumettre}>
      {type === 'tension' ? (
        <div className="tension">
          <input inputMode="numeric" aria-label={t('editeur.systolique')} placeholder="110" value={tension[0]} onChange={(e) => setTension([e.target.value, tension[1]])} />
          <span>/</span>
          <input inputMode="numeric" aria-label={t('editeur.diastolique')} placeholder="70" value={tension[1]} onChange={(e) => setTension([tension[0], e.target.value])} />
          <span className="unite">mmHg</span>
        </div>
      ) : (
        <input
          autoFocus
          dir="auto"
          aria-label={definition?.label_fr || t('editeur.valeur')}
          type={type === 'date' ? 'date' : 'text'}
          inputMode={type === 'entier' ? 'numeric' : type === 'decimal' ? 'decimal' : undefined}
          value={texte}
          onChange={(e) => setTexte(e.target.value)}
          placeholder={type === 'entier' || type === 'decimal' ? `${t('editeur.nombre')}${definition?.unite ? ` (${definition.unite})` : ''}` : t('editeur.valeur')}
        />
      )}
      <div className="choix-rapides editeur-actions">
        <button type="button" onClick={onAnnuler}>{t('commun.annuler')}</button>
        <button type="submit" className="envoyer">{libelleValider || t('commun.enregistrer')}</button>
      </div>
    </form>
  )
}
