// Rôles reconnus par le backend (en-tête X-Role) et règle de l'identifiant professionnel.
export const ROLES = ['SAGE_FEMME', 'SUPERVISEUR']

// Identifiant professionnel : jamais un nom ; lettres, chiffres, tirets, 2 à 40 caractères.
export const identifiantValide = (id) => /^[A-Za-z0-9_-]{2,40}$/.test(id || '')
