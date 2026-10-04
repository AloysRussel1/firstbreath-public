import { useState } from 'react'
import { useLangue } from '../i18n'
import { lisible } from '../lib/format'
import { normaliserSaisie, texteInitial } from '../lib/saisie'

// Saisie d'une valeur au type du schéma (shared/schema_champs.json). onValider reçoit la valeur au format du
// schéma (lib/saisie.js) ; s'il renvoie { refus: { cle, params } }, l'erreur s'affiche ici, sous la saisie.
export default function EditeurValeur({ definition, valeurInitiale, onValider, onAnnuler, libelleValider = null, variante = '' }) {
  const { t } = useLangue()
  const type = definition?.type || 'texte'
  const [texte, setTexte] = useState(() => texteInitial(definition, valeurInitiale))
  const [liste, setListe] = useState(Array.isArray(valeurInitiale) ? valeurInitiale : [])
  const [tension, setTension] = useState(() => (typeof valeurInitiale === 'string' ? valeurInitiale.split('/') : ['', '']))
  const [erreur, setErreur] = useState(null)

  async function valider(brut) {
    const r = normaliserSaisie(definition, brut)
    if (r.erreur) { setErreur(r.erreur); return }
    setErreur(null)
    const resultat = await onValider(r.valeur)
    if (resultat?.refus) setErreur(resultat.refus)
  }
  const messageErreur = erreur && <p className="erreur erreur-saisie" role="alert">{t(erreur.cle, erreur.params)}</p>

  if (type === 'booleen') {
    return (
      <div className={`editeur choix-rapides ${variante}`}>
        <button type="button" onClick={() => valider(true)}>{t('valeur.oui')}</button>
        <button type="button" onClick={() => valider(false)}>{t('valeur.non')}</button>
        <button type="button" onClick={onAnnuler}>{t('commun.annuler')}</button>
        {messageErreur}
      </div>
    )
  }
  if (type === 'choix') {
    return (
      <div className={`editeur choix-rapides ${variante}`}>
        {definition.choix.map((c) => <button type="button" key={c} onClick={() => valider(c)}>{lisible(c)}</button>)}
        <button type="button" onClick={onAnnuler}>{t('commun.annuler')}</button>
        {messageErreur}
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
          <button type="button" onClick={() => valider(liste)}>{t('editeur.cochees', { n: liste.length })}</button>
          <button type="button" onClick={onAnnuler}>{t('commun.annuler')}</button>
        </div>
        {messageErreur}
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
      const [s, d] = tension.map((x) => String(x ?? '').trim())
      // « 11/7 » tapé d'un bloc dans la première case est accepté aussi.
      valider(s.includes('/') && !d ? s : `${s}/${d}`)
      return
    }
    valider(texte)
  }
  const modifier = (maj) => (e) => { setErreur(null); maj(e.target.value) }

  return (
    <form className={`editeur ${variante}`} onSubmit={soumettre}>
      {type === 'tension' ? (
        <div className="tension">
          <input inputMode="decimal" aria-label={t('editeur.systolique')} aria-invalid={Boolean(erreur)} placeholder="110" value={tension[0]} onChange={modifier((v) => setTension([v, tension[1]]))} />
          <span>/</span>
          <input inputMode="decimal" aria-label={t('editeur.diastolique')} aria-invalid={Boolean(erreur)} placeholder="70" value={tension[1]} onChange={modifier((v) => setTension([tension[0], v]))} />
          <span className="unite">mmHg</span>
        </div>
      ) : (
        <input
          autoFocus
          dir="auto"
          aria-label={definition?.label_fr || t('editeur.valeur')}
          type="text"
          inputMode={type === 'entier' ? 'numeric' : type === 'decimal' ? 'decimal' : undefined}
          aria-invalid={Boolean(erreur)}
          value={texte}
          onChange={modifier(setTexte)}
          placeholder={type === 'entier' || type === 'decimal' ? `${t('editeur.nombre')}${definition?.unite ? ` (${definition.unite})` : ''}`
            : type === 'date' ? t('editeur.formatDate') : t('editeur.valeur')}
        />
      )}
      {messageErreur}
      <div className="choix-rapides editeur-actions">
        <button type="button" onClick={onAnnuler}>{t('commun.annuler')}</button>
        <button type="submit" className="envoyer">{libelleValider || t('commun.enregistrer')}</button>
      </div>
    </form>
  )
}
