// Icônes au trait, intégrées (aucun chargement réseau), dans le style du logo.
const trait = { fill: 'none', stroke: 'currentColor', strokeWidth: 1.8, strokeLinecap: 'round', strokeLinejoin: 'round' }

// Logo d'origine : cœur et croix fine dans un carré au coin de départ presque droit.
export function Logo({ taille = 40 }) {
  return (
    <span className="logo" style={{ width: taille, height: taille }} aria-hidden="true">
      <svg viewBox="0 0 48 48" width={taille * 0.75} height={taille * 0.75}>
        <path d="M24 5v38M5 24h17M26 24h17" {...trait} strokeWidth="2.1" />
        <path d="M27 12a8 8 0 0 1 14 5c0 8-14 16-14 16s-14-8-14-16a8 8 0 0 1 14-5Z" {...trait} strokeWidth="2.1" />
      </svg>
    </span>
  )
}

export function IconeAppareil({ taille = 28 }) {
  return (
    <svg viewBox="0 0 24 24" width={taille} height={taille} aria-hidden="true">
      <path d="M4 8h3l1.6-2.4A1.5 1.5 0 0 1 9.9 5h4.2a1.5 1.5 0 0 1 1.3.6L17 8h3a1 1 0 0 1 1 1v9a1 1 0 0 1-1 1H4a1 1 0 0 1-1-1V9a1 1 0 0 1 1-1Z" {...trait} />
      <circle cx="12" cy="13" r="3.6" {...trait} />
    </svg>
  )
}

export function IconeDossier({ taille = 22 }) {
  return (
    <svg viewBox="0 0 24 24" width={taille} height={taille} aria-hidden="true">
      <path d="M6 3h9l4 4v13a1 1 0 0 1-1 1H6a1 1 0 0 1-1-1V4a1 1 0 0 1 1-1Z" {...trait} />
      <path d="M15 3v4h4M8.5 11h7M8.5 14.5h7M8.5 18h4" {...trait} />
    </svg>
  )
}

export function IconeReglages({ taille = 22 }) {
  return (
    <svg viewBox="0 0 24 24" width={taille} height={taille} aria-hidden="true">
      <path d="M4 7h10M18 7h2M4 17h4M12 17h8" {...trait} />
      <circle cx="16" cy="7" r="2" {...trait} />
      <circle cx="10" cy="17" r="2" {...trait} />
    </svg>
  )
}

export function IconeConversation({ taille = 24 }) {
  return (
    <svg viewBox="0 0 24 24" width={taille} height={taille} aria-hidden="true">
      <path d="M4 5h16a1 1 0 0 1 1 1v10a1 1 0 0 1-1 1H10l-4.5 3.5V17H4a1 1 0 0 1-1-1V6a1 1 0 0 1 1-1Z" {...trait} />
      <path d="M7.5 10h9M7.5 13h6" {...trait} />
    </svg>
  )
}

export function IconeTableau({ taille = 24 }) {
  return (
    <svg viewBox="0 0 24 24" width={taille} height={taille} aria-hidden="true">
      <path d="M4 20h16M6.5 17v-5M11 17V7M15.5 17v-8M20 17v-3" {...trait} />
    </svg>
  )
}

export function IconeConnexion({ taille = 20, coupee = false }) {
  return (
    <svg viewBox="0 0 24 24" width={taille} height={taille} aria-hidden="true">
      <path d="M2.5 9a14 14 0 0 1 19 0M5.5 12.5a9.5 9.5 0 0 1 13 0M8.5 16a5 5 0 0 1 7 0" {...trait} />
      <circle cx="12" cy="19.3" r="1" fill="currentColor" />
      {coupee && <path d="M4 3l16 18" {...trait} strokeWidth="2.2" />}
    </svg>
  )
}

export function IconeRetour({ taille = 24 }) {
  return (
    <svg viewBox="0 0 24 24" width={taille} height={taille} aria-hidden="true">
      <path d="M15 5l-7 7 7 7" {...trait} strokeWidth="2.2" />
    </svg>
  )
}
