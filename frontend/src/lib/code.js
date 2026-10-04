// Code de liaison recopié depuis le registre papier : 6 caractères, sans 0/O ni 1/I (même règle que le serveur).
export const ALPHABET_CODE = 'ABCDEFGHJKLMNPQRSTUVWXYZ23456789'

export function normaliserCode(saisie) {
  const brut = (saisie || '').toUpperCase().replace(/[^A-Z0-9]/g, '')
  if (brut.length !== 6 || [...brut].some((c) => !ALPHABET_CODE.includes(c))) return null
  return `${brut.slice(0, 3)}-${brut.slice(3)}`
}
