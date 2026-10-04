// Code visuel des statuts de champ (shared/statuts.json). Les libellés sont dans i18n (statut.<CODE>).
// Pas de vert / jaune / rouge : le triage clinique est hors périmètre. Chaque statut se distingue par
// une icône et un motif de bordure, dans une palette neutre.
export const STATUTS_CHAMP = {
  CONNU: { icone: '✓', classe: 'st-connu' },
  A_REVISER: { icone: '?', classe: 'st-a-reviser' },
  ILLISIBLE: { icone: '≈', classe: 'st-illisible' },
  NON_FOURNI: { icone: '–', classe: 'st-non-fourni' },
  NON_APPLICABLE: { icone: '∅', classe: 'st-non-applicable' },
  INCONNU: { icone: '¿', classe: 'st-inconnu' },
}

export const TYPES_PAGE = [
  'IDENTIFICATION', 'ANTECEDENTS', 'GROSSESSE_ACTUELLE', 'ACCOUCHEMENT',
  'PP_PRECOCE_MERE', 'PP_PRECOCE_NOUVEAU_NE', 'PP_TARDIF_MERE', 'PP_TARDIF_NOUVEAU_NE',
]

// États d'une capture dans la file locale (en plus des états du cycle de vie de shared/statuts.json).
export const ETATS_FILE = ['QUALITE', 'EN_FILE', 'ENVOI', 'A_TRAITER']
