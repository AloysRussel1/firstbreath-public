// Libellés, mise en forme des valeurs et règles « douteux / fiable » pour l'affichage.
// Les libellés de champ viennent de shared/schema_champs.json (label_fr / label_en).

const VISITE = /^grossesse\.visites\[(\d)\]\.(\w+)$/

export function infosVisite(cle) {
  const m = VISITE.exec(cle)
  return m ? { index: Number(m[1]), cle: m[2] } : null
}

export function definitionChamp(schema, cle) {
  const visite = infosVisite(cle)
  if (visite) return schema?.visites?.champs?.[visite.cle] || null
  return schema?.fields?.[cle] || null
}

// Libellé dans la langue choisie ; pour une visite, ajoute la colonne (« 7e mois »).
export function libelleChamp(schema, cle, langue = 'fr', t = null, avecVisite = true) {
  const definition = definitionChamp(schema, cle)
  const base = (langue === 'en' ? definition?.label_en : definition?.label_fr) || definition?.label_fr || cle
  const visite = infosVisite(cle)
  if (!visite || !avecVisite) return base
  const colonne = schema?.visites?.index?.[visite.index]
  return `${base} · ${t && colonne ? t(`visite.${colonne}`) : colonne || visite.index + 1}`
}

// Code de choix lisible : « VOIE_BASSE_INSTRUMENTALE » -> « Voie basse instrumentale ».
export function lisible(code) {
  if (typeof code !== 'string') return String(code)
  if (code.length <= 4) return code
  const texte = code.replaceAll('_', ' ').toLowerCase()
  return texte.charAt(0).toUpperCase() + texte.slice(1)
}

export function dateLisible(iso) {
  const m = /^(\d{4})-(\d{2})-(\d{2})/.exec(iso || '')
  return m ? `${m[3]}/${m[2]}/${m[1]}` : iso
}

// Horodatage du serveur (UTC) -> « 04/10/2026 · 14:32 » à l'heure locale du téléphone.
export function dateHeureLisible(iso) {
  const d = new Date(iso || '')
  if (Number.isNaN(d.getTime())) return dateLisible(iso)
  const deux = (n) => String(n).padStart(2, '0')
  return `${deux(d.getDate())}/${deux(d.getMonth() + 1)}/${d.getFullYear()} · ${deux(d.getHours())}:${deux(d.getMinutes())}`
}

export function formaterValeur(definition, valeur, t = (cle) => ({ 'valeur.oui': 'Oui', 'valeur.non': 'Non', 'valeur.aucuneCase': 'Aucune case cochée', 'valeur.aucun': 'Aucun' }[cle])) {
  if (valeur === null || valeur === undefined) return '—'
  const type = definition?.type
  if (typeof valeur === 'boolean') return valeur ? t('valeur.oui') : t('valeur.non')
  if (type === 'date') return dateLisible(valeur)
  if (type === 'liste_choix') return valeur.length ? valeur.map(lisible).join(', ') : t('valeur.aucuneCase')
  if (type === 'liste_objets') {
    if (!valeur.length) return t('valeur.aucun')
    return valeur.map((o) => (typeof o === 'object'
      ? [dateLisible(o.date), o.modalite, o.poids_g ? `${o.poids_g} g` : null].filter(Boolean).join(' · ')
      : String(o))).join(' ; ')
  }
  if (type === 'choix') return lisible(valeur)
  const unite = definition?.unite && !['mmHg (sys/dia)'].includes(definition.unite) ? ` ${definition.unite}` : ''
  return `${valeur}${unite}`
}

// Un champ demande une question s'il est À vérifier, illisible, ou lu sous le seuil de confiance,
// et que la sage-femme ne l'a ni confirmé ni corrigé.
export function estDouteux(champ, seuil) {
  if (champ.source === 'manual' || champ.confirme) return false
  return ['A_REVISER', 'ILLISIBLE'].includes(champ.statut) || (champ.statut === 'CONNU' && champ.confiance < seuil)
}

export function estFiable(champ, seuil) {
  return champ.statut === 'CONNU' && champ.confiance >= seuil
}

// Raison du doute, sous forme de clé de traduction.
export function raisonDoute(champ, seuil) {
  const pourcent = `${Math.round((champ.confiance || 0) * 100)} %`
  if (champ.statut === 'ILLISIBLE') return { cle: 'doute.illisible' }
  if (champ.statut === 'A_REVISER' && champ.valeur === null) return { cle: 'doute.pasSur', params: { pourcent } }
  if (champ.statut === 'A_REVISER') return { cle: 'doute.incertain', params: { pourcent } }
  if (champ.confiance < seuil) return { cle: 'doute.faible', params: { pourcent } }
  return null
}

// Champs vides d'une page à saisir entièrement à la main (extraction impossible).
export function pageVide(schema, pageNo, typePage) {
  const cles = (schema?.pages?.[typePage] || []).flatMap((cle) => (cle === 'grossesse.visites[*]'
    ? (schema.visites.index || []).flatMap((_, i) => Object.keys(schema.visites.champs).map((c) => `grossesse.visites[${i}].${c}`))
    : [cle]))
  return { page_no: pageNo, type_page: typePage, champs: cles.map((cle) => ({ champ: cle, valeur: null, statut: 'NON_FOURNI', confiance: 0, saisie: true })) }
}

// Regroupement par section : préfixe de la clé ; le nom sert de clé de traduction (« section.<nom> »).
const SECTIONS = [
  ['identification.', 'Identification'], ['profil.', 'Profil'], ['antecedents.familiaux.', 'Antécédents familiaux'],
  ['antecedents.femme.', 'Antécédents de la femme'], ['obstetrique.', 'Histoire obstétricale'],
  ['vaccination.', 'Vaccination'], ['depistage.', 'Dépistage'], ['grossesse.tests.', 'Examens biologiques'],
  ['grossesse.traitement.', 'Traitement'], ['grossesse.visites[', 'Visites'], ['grossesse.', 'Grossesse'],
  ['accouchement.', 'Accouchement'], ['nouveau_ne.', 'Nouveau-né'], ['pp_precoce.mere.', 'Mère'],
  ['pp_precoce.nouveau_ne.', 'Nouveau-né'], ['pp_tardif.mere.', 'Mère'], ['pp_tardif.nouveau_ne.', 'Nouveau-né'],
]

export function sectionDe(cle) {
  return (SECTIONS.find(([prefixe]) => cle.startsWith(prefixe)) || [null, 'Autres'])[1]
}

// Dates qui devraient être passées au moment de la photo (consultation, venue à une visite, DDR, accouchement) ;
// les rendez-vous et la date prévue d'accouchement sont normalement dans le futur.
const DATES_PASSEES = /(\.date_consultation|\.date_venue|^grossesse\.ddr|^accouchement\.date)$/

// Vrai si une telle date lue est postérieure à la date de capture de la photo (avertissement seulement).
export function datePosterieure(champ, dateCapture) {
  if (!dateCapture || typeof champ.valeur !== 'string' || !DATES_PASSEES.test(champ.champ)) return false
  return /^\d{4}-\d{2}-\d{2}$/.test(champ.valeur) && champ.valeur > String(dateCapture).slice(0, 10)
}
