import { useLangue } from '../i18n'
import { STATUTS_CHAMP } from '../lib/statuts'

// Badge neutre : icône + libellé ; la forme de la bordure distingue les statuts, pas la couleur.
export default function StatutBadge({ statut, compact = false }) {
  const { t } = useLangue()
  const s = STATUTS_CHAMP[statut] || { icone: '·', classe: '' }
  const libelle = t(`statut.${statut}`)
  return (
    <span className={`statut ${s.classe}`} title={libelle}>
      <span className="statut-icone" aria-hidden="true">{s.icone}</span>
      {compact ? <span className="sr-only">{libelle}</span> : <span className="statut-libelle">{libelle}</span>}
    </span>
  )
}
