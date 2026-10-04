import { useState } from 'react'
import { useLangue } from '../i18n'
import { normaliserCode } from '../lib/code'

// Saisie du code de liaison recopié depuis le registre papier.
export default function SaisieCode({ reponse, occupe, onSoumettre, onAnnuler = null, libelle = null }) {
  const { t } = useLangue()
  const [valeur, setValeur] = useState('')
  const code = normaliserCode(valeur)
  if (reponse) return null
  return (
    <form className="saisie-code" onSubmit={(e) => { e.preventDefault(); if (code) onSoumettre(code) }}>
      <input autoFocus value={valeur} onChange={(e) => setValeur(e.target.value)} maxLength={7} placeholder="ABC-234"
        autoCapitalize="characters" autoComplete="off" spellCheck={false} aria-label={t('liaison.saisirCode')} />
      {onAnnuler && <button type="button" className="bouton" onClick={onAnnuler}>{t('commun.annuler')}</button>}
      <button type="submit" className="bouton envoyer" disabled={!code || occupe}>{libelle || t('liaison.chercher')}</button>
    </form>
  )
}
