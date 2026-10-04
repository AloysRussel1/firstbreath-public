// Logique de la conversation de vérification, au-dessus des onglets : elle survit au changement d'onglet.
// Reprise de l'écran de chat précédent (envoi, file hors ligne, suivi /etat, questions une à une) ;
// les textes de l'agent sont stockés sous forme de clés de traduction ({ cle, params }).
import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from 'react'
import statuts from '../../../shared/statuts.json'
import { api } from '../api'
import { lireDocument, lirePhoto, sauverDocument, sauverPhoto, supprimerPhotos } from '../lib/coffre'
import { dateLisible, definitionChamp, estDouteux, estFiable, pageVide } from '../lib/format'
import { controleQualiteActif, panneCentraleSimulee } from '../lib/preferences'
import { verifierQualite } from '../lib/qualitePhoto'
import { erreurServeur, normaliserSaisie } from '../lib/saisie'
import { TYPES_PAGE } from '../lib/statuts'
import { useConnexion } from './connexion'
import { naviguer } from './route'

const CLE_SESSION = 'firstbreath-session'
// Seuil de question : shared/statuts.json (le serveur renvoie le même dans /schema ; ceci sert hors ligne).
const SEUIL_PAR_DEFAUT = statuts.seuil_question_suivi
const INTERVALLE_SUIVI_MS = 2500
const ConversationContexte = createContext(null)

const nouvelId = () => crypto.randomUUID()
function lireSession() {
  try {
    const id = localStorage.getItem(CLE_SESSION)
    if (id) return id
  } catch { /* stockage indisponible */ }
  return nouvelleSession()
}
function nouvelleSession(id = nouvelId()) {
  try { localStorage.setItem(CLE_SESSION, id) } catch { /* stockage indisponible */ }
  return id
}
// N° de fiche comparés sans tenir compte des espaces ni de la casse.
const memeNumero = (a, b) => String(a).replace(/\s/g, '').toUpperCase() === String(b).replace(/\s/g, '').toUpperCase()

const texte = (cle, params) => ({ cle, params })
// Actions proposées après une page : l'action suivante évidente d'abord, le détail en dernier.
const OPTION_PHOTO = { id: 'photo', libelle: texte('option.pageSuivante') }
const OPTION_VALIDER = { id: 'valider', libelle: texte('option.valider') }
const OPTION_DETAIL = { id: 'detail', libelle: texte('option.detail') }
const OPTIONS_FIN_PAGE = [{ id: 'tout_confirmer', libelle: texte('option.toutConfirmer') }, OPTION_PHOTO, OPTION_VALIDER, OPTION_DETAIL]
const OPTIONS_SUITE = [OPTION_PHOTO, OPTION_VALIDER, OPTION_DETAIL]
const BILAN_VIDE = { confirme: [], corrige: [], vide: [] }
const BIENVENUE = { id: 'bienvenue', auteur: 'agent', type: 'texte', texte: texte('conv.bienvenue') }
// Captures encore à envoyer ou en cours de lecture : jamais abandonnées par « Nouveau registre ».
const EN_ATTENTE = ['QUALITE', 'EN_FILE', 'ENVOI', 'A_TRAITER', 'CAPTURE', 'EN_ATTENTE_IA']

export function FournisseurConversation({ children }) {
  const { connecte } = useConnexion()
  const [schema, setSchema] = useState(null)
  const [sessionId, setSessionId] = useState(lireSession)
  const [captures, setCaptures] = useState([])
  const [dossier, setDossier] = useState(null)
  const [messages, setMessages] = useState([BIENVENUE])
  const [questionActive, setQuestionActive] = useState(null)
  const [reponses, setReponses] = useState({})
  const [detailOuvert, setDetailOuvert] = useState(false)
  const [pagesEnSaisie, setPagesEnSaisie] = useState([])
  // Bilan des réponses par page (confirmé, corrigé, laissé vide), affiché à la fin de la vérification.
  const [bilans, setBilans] = useState({})
  const bilansRef = useRef({})
  const [occupe, setOccupe] = useState(false)
  const [pret, setPret] = useState(false)
  const capturesRef = useRef(captures)
  const dossierRef = useRef(null)
  const seuilRef = useRef(SEUIL_PAR_DEFAUT)
  const requisRef = useRef(['identification.numero_fiche'])
  const messagesRef = useRef(messages)
  const reponsesRef = useRef(reponses)
  const dernierePage = useRef(0)
  const terminees = useRef(new Set())
  const enCours = useRef(new Set())
  const ouvrirAppareilRef = useRef(() => {})
  const nouveauRegistreRef = useRef(() => false)
  const choisirAutrePatienteRef = useRef(() => {})
  // Journal des photos en file, écrit AVANT l'entrée en file : la conversation n'est sauvegardée qu'après
  // un court délai, le journal garantit qu'un rechargement immédiat ne perd aucune photo.
  const journal = useRef([])
  const seuil = schema?.seuil_question_suivi ?? SEUIL_PAR_DEFAUT

  useEffect(() => { capturesRef.current = captures }, [captures])
  useEffect(() => { messagesRef.current = messages }, [messages])
  useEffect(() => { dossierRef.current = dossier }, [dossier])
  useEffect(() => { seuilRef.current = seuil }, [seuil])
  useEffect(() => { requisRef.current = schema?.required_fields || ['identification.numero_fiche'] }, [schema])
  useEffect(() => { reponsesRef.current = reponses }, [reponses])
  useEffect(() => {
    if (connecte && !schema) api.schema().then(setSchema).catch(() => {})
  }, [connecte, schema])

  const ajouter = useCallback((message) => setMessages((m) => [...m, { id: nouvelId(), ...message }]), [])
  const dire = useCallback((cle, params, extra = {}) => ajouter({ auteur: 'agent', type: 'texte', texte: texte(cle, params), ...extra }), [ajouter])
  const repondreSf = useCallback((cle, params) => ajouter({ auteur: 'sf', type: 'texte', texte: texte(cle, params) }), [ajouter])
  const majCapture = useCallback((localId, changement) =>
    setCaptures((cs) => cs.map((c) => (c.localId === localId ? { ...c, ...changement } : c))), [])
  const ouvrirAppareil = useCallback(() => ouvrirAppareilRef.current(), [])

  // ---------- Envoi d'une photo puis lancement du traitement ----------
  const envoyer = useCallback(async (localId) => {
    const c = capturesRef.current.find((x) => x.localId === localId)
    if (!c || enCours.current.has(localId)) return
    enCours.current.add(localId)
    try {
      let captureId = c.captureId
      if (!captureId) {
        majCapture(localId, { etat: 'ENVOI' })
        const envoi = await api.envoyerCapture(c.fichier, { sessionId, pageNo: c.pageNo })
        if (envoi.duplicate_suspected) {
          // Même image déjà envoyée : on montre le dossier existant, sans le mélanger au registre en cours.
          majCapture(localId, { etat: 'DOUBLON_SUSPECTE', captureId: envoi.capture_id })
          dire('msg.doublon', null, {
            type: 'choix', unique: true,
            options: [
              { id: `ouvrir:${envoi.dossier.dossier_id}`, libelle: texte('option.ouvrirExistant') },
              { id: 'photo', libelle: texte('option.reprendre') },
            ],
          })
          return
        }
        setDossier(envoi.dossier)
        captureId = envoi.capture_id
        majCapture(localId, { etat: 'CAPTURE', captureId })
      }
      const t = await api.traiter(captureId)
      majCapture(localId, { etat: t.etat, duree: t.duree_estimee_s, progression: t.progression, ecoule: t.ecoule_s })
    } catch (erreur) {
      if (erreur.hors_ligne) majCapture(localId, { etat: c.captureId ? 'A_TRAITER' : 'EN_FILE' })
      else {
        majCapture(localId, { etat: 'REFUSEE', detail: erreur.message })
        dire('msg.refusee', { n: c.pageNo, detail: erreur.message },
          { type: 'choix', options: [{ id: 'reprendre', libelle: texte('option.reprendre') }] })
      }
    } finally {
      enCours.current.delete(localId)
    }
  }, [dire, majCapture, sessionId])

  // Au retour de la connexion : les dossiers enregistrés (ou en échec de synchronisation) repartent.
  const connecteAvant = useRef(false)
  useEffect(() => {
    if (!pret) return
    const revient = connecte && !connecteAvant.current
    connecteAvant.current = Boolean(connecte)
    if (!revient) return
    api.synchroniser({ simulerPanne: panneCentraleSimulee() })
      .then((s) => { if (s.synchronises.length) dire('cycle.synchroniseAuto', { n: s.synchronises.length }) })
      .catch(() => {})
  }, [connecte, dire, pret])

  // Reprise automatique de la file dès que la connexion revient (et après un rechargement de la page).
  useEffect(() => {
    if (!connecte || !pret) return
    captures.filter((c) => (c.etat === 'EN_FILE' || c.etat === 'A_TRAITER') && c.fichier).forEach((c) => envoyer(c.localId))
  }, [connecte, pret, captures, envoyer])

  const prendrePhoto = useCallback(async (fichier) => {
    if (!fichier) return
    dernierePage.current = Math.max(dernierePage.current, ...capturesRef.current.map((c) => c.pageNo)) + 1
    const pageNo = dernierePage.current
    const localId = nouvelId()
    // La photo est écrite (chiffrée) dans le coffre AVANT d'entrer dans la file : un rechargement
    // ou une coupure ne peut plus la perdre.
    try {
      await sauverPhoto(localId, fichier)
      journal.current = [...journal.current, { localId, pageNo, sessionId }]
      await sauverDocument('journal', journal.current)
    } catch { /* coffre indisponible : file en mémoire seulement */ }
    const url = URL.createObjectURL(fichier)
    const controle = controleQualiteActif()
    setCaptures((cs) => [...cs, { localId, fichier, url, pageNo, etat: controle ? 'QUALITE' : 'EN_FILE' }])
    ajouter({ auteur: 'sf', type: 'photo', localId, pageNo })
    ajouter({ auteur: 'agent', type: 'suivi', localId })
    if (controle) {
      // Contrôle de netteté et de luminosité sur l'appareil ; la sage-femme décide de reprendre ou d'envoyer.
      const { problemes } = await verifierQualite(fichier).catch(() => ({ problemes: [] }))
      if (problemes.length) {
        majCapture(localId, { qualiteDemandee: true })
        dire('msg.qualite', { n: pageNo, problemes: problemes.map((x) => texte(`msg.qualite.${x}`)), conseil: texte('msg.qualite.conseil') }, {
          type: 'choix', unique: true,
          options: [
            { id: `qualite:reprendre:${localId}`, libelle: texte('option.reprendre') },
            { id: `qualite:envoyer:${localId}`, libelle: texte('option.envoyerQuandMeme') },
          ],
        })
        return
      }
      majCapture(localId, { etat: 'EN_FILE' })
    }
    setTimeout(() => envoyer(localId), 0)
  }, [ajouter, dire, envoyer, majCapture, sessionId])

  const deciderQualite = useCallback((action, localId) => {
    if (action === 'envoyer') {
      majCapture(localId, { etat: 'EN_FILE' })
      setTimeout(() => envoyer(localId), 0)
      return
    }
    majCapture(localId, { etat: 'ABANDONNEE' })
    supprimerPhotos([localId]).catch(() => {})
    journal.current = journal.current.filter((j) => j.localId !== localId)
    sauverDocument('journal', journal.current).catch(() => {})
    ouvrirAppareil()
  }, [envoyer, majCapture, ouvrirAppareil])

  // ---------- Questions : une à la fois ----------
  const fileRef = useRef([])
  const activeRef = useRef(null)
  const avancer = useCallback(() => {
    // Une question dont le champ a déjà été vérifié ailleurs n'est plus posée.
    while (fileRef.current.length) {
      const q = fileRef.current[0]
      const champ = dossierRef.current?.pages?.find((p) => p.page_no === q.pageNo)?.champs.find((c) => c.champ === q.cle)
      if (!champ || estDouteux(champ, seuilRef.current) || requisRef.current.includes(q.cle)) break
      fileRef.current = fileRef.current.slice(1)
    }
    if (activeRef.current || fileRef.current.length === 0) return
    const [suivante, ...reste] = fileRef.current
    const id = nouvelId()
    fileRef.current = reste
    activeRef.current = id
    setQuestionActive(id)
    setMessages((m) => [...m, { id, auteur: 'agent', type: 'question', ...suivante }])
  }, [])
  const ajouterQuestions = useCallback((questions) => {
    fileRef.current = [...fileRef.current, ...questions]
    avancer()
  }, [avancer])
  const terminerQuestion = useCallback(() => {
    activeRef.current = null
    setQuestionActive(null)
    avancer()
  }, [avancer])

  const reposerQuestions = useCallback(() => {
    if (activeRef.current) {
      document.getElementById(`msg-${activeRef.current}`)?.scrollIntoView({ block: 'center' })
      return
    }
    const enFile = new Set(fileRef.current.map((q) => `${q.pageNo}:${q.cle}`))
    const nouvelles = []
    for (const page of dossierRef.current?.pages || []) {
      const douteux = page.champs.filter((c) => estDouteux(c, seuil) && !enFile.has(`${page.page_no}:${c.champ}`))
      douteux.forEach((c, i) => nouvelles.push({ cle: c.champ, pageNo: page.page_no, numero: i + 1, total: douteux.length }))
    }
    ajouterQuestions(nouvelles)
  }, [ajouterQuestions, seuil])

  // ---------- Suivi du traitement : GET /captures/{id}/etat toutes les 2,5 s ----------
  // Résumé d'une page lue : renumérisation, rien lu, aucun doute, ou questions une à une.
  const analyserPage = useCallback((c, d) => {
    const page = d?.pages?.find((p) => p.page_no === c.pageNo)
    if (!page) return
    // Même type de page déjà photographié dans ce registre : renumérisation, la sage-femme choisit champ par champ.
    const ancienne = d.pages.find((p) => p.type_page === page.type_page && p.page_no < c.pageNo)
    if (ancienne) {
      const comparees = page.champs.map((n) => ({ cle: n.champ, ancienne: ancienne.champs.find((a) => a.champ === n.champ)?.valeur ?? null, nouvelle: n.valeur ?? null }))
      const differe = (l) => JSON.stringify(l.ancienne) !== JSON.stringify(l.nouvelle)
      const lignes = comparees.filter(differe)
      const identiques = comparees.filter((l) => !differe(l)).map((l) => ({ cle: l.cle, valeur: l.ancienne }))
      const type = { typePage: page.type_page }
      if (lignes.length === 0) {
        dire('renum.identiqueType', { type })
        api.renumeriser(d.dossier_id, { ancienne_page: ancienne.page_no, nouvelle_page: c.pageNo, champs: [] })
          .then((r) => setDossier(r.dossier)).catch(() => {})
        return
      }
      const comparaison = { auteur: 'agent', type: 'renum', texte: texte('renum.explication'), typePage: page.type_page,
        compte: texte('renum.resume', { n: lignes.length, total: comparees.length }), ancienne: ancienne.page_no, nouvelle: c.pageNo, lignes, identiques }
      // Très différente (plus de la moitié des champs, ou des dates à plus de 90 jours) : sans doute une autre patiente.
      const jours = (a, b) => Math.abs(Date.parse(a) - Date.parse(b)) / 86400000
      const datesEloignees = lignes.some((l) => /^\d{4}-\d{2}-\d{2}$/.test(String(l.ancienne)) && /^\d{4}-\d{2}-\d{2}$/.test(String(l.nouvelle)) && jours(l.ancienne, l.nouvelle) > 90)
      if (lignes.length > comparees.length / 2 || datesEloignees) {
        dire('renum.tresDifferent', { type }, {
          type: 'choix', unique: true, comparaison,
          options: [
            { id: 'diff:meme', libelle: texte('option.memePage') },
            { id: `autre:nouveau:${c.localId}`, libelle: texte('option.autreRegistre') },
            { id: `autre:annuler:${c.localId}`, libelle: texte('option.annuler') },
          ],
        })
        return
      }
      ajouter(comparaison)
      return
    }
    const douteux = page.champs.filter((champ) => estDouteux(champ, seuil))
    const titre = texte('msg.titrePage', { type: { typePage: page.type_page } })
    if (page.champs.every((champ) => champ.valeur === null || champ.valeur === undefined)) {
      dire('msg.rienLu', { titre }, {
        type: 'choix',
        options: [
          { id: 'detail', libelle: texte('option.saisirDetail') },
          { id: `relancer:${c.localId}`, libelle: texte('option.relancer') },
          { id: 'reprendre', libelle: texte('option.reprendre') },
        ],
      })
      return
    }
    if (douteux.length === 0) {
      // « Tout confirmer » seulement s'il reste au moins un champ lu avec certitude à confirmer.
      const aConfirmer = page.champs.some((x) => estFiable(x, seuil) && !x.confirme && x.source !== 'manual')
      dire('msg.resumeSansDoute', { titre, total: page.champs.length }, {
        type: 'choix', options: aConfirmer ? OPTIONS_FIN_PAGE : OPTIONS_FIN_PAGE.filter((o) => o.id !== 'tout_confirmer'),
      })
      return
    }
    dire('msg.resume', { titre, total: page.champs.length, douteux: douteux.length })
    ajouterQuestions(douteux.map((champ, i) => ({ cle: champ.champ, pageNo: c.pageNo, numero: i + 1, total: douteux.length })))
  }, [ajouter, ajouterQuestions, dire, seuil])

  const finTraitement = useCallback((c, etat) => {
    if (terminees.current.has(c.localId)) return
    terminees.current.add(c.localId)
    const d = etat.dossier
    setDossier(d)
    if (['ECHEC_TRAITEMENT', 'REVISION_MANUELLE_REQUISE'].includes(etat.etat)) {
      dire('msg.echec', { n: c.pageNo, detail: etat.detail || '' }, {
        type: 'choix',
        options: [
          { id: `relancer:${c.localId}`, libelle: texte('option.relancer') },
          { id: 'reprendre', libelle: texte('option.reprendre') },
          { id: `saisie:${c.pageNo}`, libelle: texte('option.saisie') },
        ],
      })
      return
    }
    const page = d?.pages?.find((p) => p.page_no === c.pageNo)
    if (!page) return
    // Page portant un autre N° de fiche que le registre : sans doute une autre patiente. La sage-femme décide.
    const numeroLu = page.champs.find((x) => x.champ === 'identification.numero_fiche')?.valeur
    if (numeroLu && d.numero_fiche && !memeNumero(numeroLu, d.numero_fiche)) {
      dire('patiente.autre', { nouveau: numeroLu, actuel: d.numero_fiche }, {
        type: 'choix', unique: true,
        options: [
          { id: `autre:ajouter:${c.localId}`, libelle: texte('option.ajouterQuandMeme') },
          { id: `autre:nouveau:${c.localId}`, libelle: texte('option.commencerNouveau') },
          { id: `autre:annuler:${c.localId}`, libelle: texte('option.annuler') },
        ],
      })
      return
    }
    analyserPage(c, d)
  }, [analyserPage, dire])


  useEffect(() => {
    if (!captures.some((c) => c.etat === 'EN_ATTENTE_IA')) return
    const minuterie = setInterval(() => {
      capturesRef.current.filter((c) => c.etat === 'EN_ATTENTE_IA' && c.captureId).forEach(async (c) => {
        try {
          const e = await api.etat(c.captureId)
          majCapture(c.localId, { etat: e.etat, progression: e.progression, ecoule: e.ecoule_s, duree: e.duree_estimee_s, typePage: e.type_page })
          if (e.termine) finTraitement(c, e)
        } catch {
          // Hors ligne pendant le traitement : le serveur continue, le suivi reprendra au retour de la connexion.
        }
      })
    }, INTERVALLE_SUIVI_MS)
    return () => clearInterval(minuterie)
  }, [captures, finTraitement, majCapture])

  // ---------- Hors ligne : restauration et sauvegarde chiffrées (lib/coffre.js) ----------
  useEffect(() => {
    let actif = true
    ;(async () => {
      try {
        const lu = await lireDocument('conversation')
        journal.current = (await lireDocument('journal').catch(() => null)) || []
        if ((!lu && journal.current.length === 0) || !actif) return
        const etat = lu || { sessionId: journal.current[0]?.sessionId, captures: [], messages: [BIENVENUE] }
        // Photos du journal absentes de la conversation sauvegardée (rechargement immédiat) : remises en file.
        const manquantes = journal.current.filter((j) => j.sessionId === etat.sessionId && !(etat.captures || []).some((c) => c.localId === j.localId))
        etat.captures = [...(etat.captures || []), ...manquantes.map((j) => ({ localId: j.localId, pageNo: j.pageNo, etat: 'EN_FILE' }))]
        etat.messages = [...(etat.messages?.length ? etat.messages : [BIENVENUE]), ...manquantes.flatMap((j) => [
          { id: nouvelId(), auteur: 'sf', type: 'photo', localId: j.localId, pageNo: j.pageNo },
          { id: nouvelId(), auteur: 'agent', type: 'suivi', localId: j.localId },
        ])]
        const restaurees = []
        for (const c of etat.captures) {
          const blob = await lirePhoto(c.localId).catch(() => null)
          // Une capture interrompue en plein envoi repart en file : le serveur reconnaît un renvoi
          // identique (même session, page et image) et ne crée aucun doublon.
          // Une photo dont le contrôle de qualité attend une réponse garde sa question.
          let etatCapture = c.etat
          if (etatCapture === 'ENVOI' || (etatCapture === 'QUALITE' && !c.qualiteDemandee)) etatCapture = c.captureId ? 'A_TRAITER' : 'EN_FILE'
          restaurees.push({
            ...c,
            etat: etatCapture,
            fichier: blob ? new File([blob], `page-${c.pageNo}.jpg`, { type: blob.type }) : null,
            url: blob ? URL.createObjectURL(blob) : null,
          })
        }
        if (!actif) return
        if (etat.sessionId) {
          setSessionId(etat.sessionId)
          try { localStorage.setItem(CLE_SESSION, etat.sessionId) } catch { /* stockage indisponible */ }
        }
        capturesRef.current = restaurees
        dernierePage.current = Math.max(0, ...restaurees.map((c) => c.pageNo))
        setCaptures(restaurees)
        setDossier(etat.dossier || null)
        setMessages(etat.messages?.length ? etat.messages : [BIENVENUE])
        setReponses(etat.reponses || {})
        setPagesEnSaisie(etat.pagesEnSaisie || [])
        bilansRef.current = etat.bilans || {}
        setBilans(bilansRef.current)
        fileRef.current = etat.file || []
        activeRef.current = etat.questionActive || null
        setQuestionActive(etat.questionActive || null)
        terminees.current = new Set(etat.terminees || [])
      } catch {
        // Coffre indisponible (navigation privée…) : la conversation fonctionne en mémoire.
      } finally {
        if (actif) setPret(true)
      }
    })()
    return () => { actif = false }
  }, [])

  useEffect(() => {
    if (!pret) return undefined
    const minuterie = setTimeout(() => {
      sauverDocument('conversation', {
        sessionId,
        // Le fichier (déjà dans le coffre) et l'URL temporaire ne font pas partie du document.
        captures: captures.map((c) => Object.fromEntries(Object.entries(c).filter(([cle]) => cle !== 'fichier' && cle !== 'url'))),
        dossier, messages, reponses, pagesEnSaisie, bilans,
        file: fileRef.current, questionActive: activeRef.current, terminees: [...terminees.current],
      }).catch(() => {})
    }, 300)
    return () => clearTimeout(minuterie)
  }, [pret, sessionId, captures, dossier, messages, reponses, pagesEnSaisie, bilans, questionActive])

  // Ce qui empêche la validation, recalculé à chaque changement : le message de blocage reste à jour.
  const requis = useMemo(() => schema?.required_fields || ['identification.numero_fiche'], [schema])
  const blocages = useMemo(() => {
    const pages = dossier?.pages || []
    const sur = (c) => c && c.valeur !== null && c.valeur !== undefined && c.statut === 'CONNU' && (c.confiance >= seuil || c.confirme || c.source === 'manual')
    const obligatoires = requis.filter((cle) => !sur(pages.flatMap((p) => p.champs).find((c) => c.champ === cle)))
      .map((cle) => {
        const page = pages.find((p) => p.champs.some((c) => c.champ === cle)) || null
        return { cle, page, valeur: page?.champs.find((c) => c.champ === cle)?.valeur ?? null }
      })
    const questions = pages.flatMap((p) => p.champs.filter((c) => estDouteux(c, seuil) && !requis.includes(c.champ))
      .map((c) => ({ cle: c.champ, pageNo: p.page_no, typePage: p.type_page, valeur: c.valeur })))
    const enLecture = captures.filter((c) => EN_ATTENTE.includes(c.etat)).length
    const comparaison = messages.find((m) => m.type === 'renum' && reponses[m.id] === undefined)?.id || null
    return { obligatoires, questions, enLecture, comparaison,
      aucun: !obligatoires.length && !questions.length && !enLecture && !comparaison }
  }, [captures, dossier, messages, reponses, requis, seuil])
  const [filtreAVerifier, setFiltreAVerifier] = useState(false)
  const fiablesAConfirmer = useMemo(() => (dossier?.pages || []).flatMap((p) => p.champs)
    .filter((c) => estFiable(c, seuil) && !c.confirme && c.source !== 'manual').length, [dossier, seuil])

  const champDuDossier = useCallback((cle, pageNo) =>
    dossier?.pages?.find((p) => p.page_no === pageNo)?.champs.find((c) => c.champ === cle), [dossier])

  // Renvoie { ok: true, valeur } ou { ok: false, refus: { cle, params } } : la zone de saisie affiche le refus.
  // Toute valeur passe d'abord au format du schéma (lib/saisie.js) : « 11/7 » -> « 110/70 », JJ/MM/AAAA -> ISO…
  const enregistrerChamp = useCallback(async (champ, page, changement) => {
    const definition = definitionChamp(schema, champ.champ)
    let valeur = null
    if (!changement.vide) {
      const n = normaliserSaisie(definition, changement.valeur)
      if (n.erreur) return { ok: false, refus: n.erreur }
      valeur = n.valeur
    }
    const corps = changement.vide
      ? { champ: champ.champ, valeur: null, statut: 'NON_FOURNI', confiance: 1 }
      : { champ: champ.champ, valeur, statut: 'CONNU', confiance: 1 }
    setOccupe(true)
    try {
      const r = await api.corrigerChamp(dossier.dossier_id, { ...corps, page_no: page.page_no, type_page: page.type_page })
      setDossier(r.dossier)
      return { ok: true, valeur }
    } catch (erreur) {
      if (erreur.hors_ligne) return { ok: false, refus: { cle: 'msg.horsLigneReponse' } }
      console.warn('Valeur refusée par le serveur :', champ.champ, erreur.message)
      if (changement.vide) dire('msg.valeurRefusee')
      return { ok: false, refus: erreurServeur(definition, erreur.message) }
    } finally {
      setOccupe(false)
    }
  }, [dire, dossier, schema])

  const repondre = useCallback(async (message, { action, valeur }) => {
    const champ = champDuDossier(message.cle, message.pageNo)
    const page = dossier.pages.find((p) => p.page_no === message.pageNo)
    if (action === 'reprendre') {
      setReponses((r) => ({ ...r, [message.id]: 'reprendre' }))
      if (message.ponctuelle) { ouvrirAppareil(); return }
      fileRef.current = fileRef.current.filter((q) => q.pageNo !== message.pageNo)
      repondreSf('sf.reprendre')
      dire('msg.reprendre', { n: message.pageNo })
      ouvrirAppareil()
      terminerQuestion()
      return
    }
    const changement = action === 'vide' ? { vide: true } : { valeur: action === 'confirmer' ? champ.valeur : valeur }
    const resultat = await enregistrerChamp(champ, page, changement)
    if (!resultat.ok) {
      // Correction : l'erreur s'affiche dans la zone de saisie. Confirmation (pas de zone) : message dans le fil.
      if (action === 'confirmer') dire(resultat.refus.cle, resultat.refus.params)
      return resultat
    }
    const valeurAffichee = { champ: message.cle, valeur: action === 'vide' ? null : resultat.valeur }
    if (action === 'confirmer') repondreSf('sf.confirme', { valeur: valeurAffichee })
    else if (action === 'vide') repondreSf('sf.vide')
    else repondreSf('sf.corrige', { valeur: valeurAffichee })
    setReponses((r) => ({ ...r, [message.id]: action }))
    if (message.ponctuelle) return
    const precedent = bilansRef.current[message.pageNo] || BILAN_VIDE
    const bilan = {
      confirme: action === 'confirmer' ? [...precedent.confirme, message.cle] : precedent.confirme,
      corrige: action === 'corriger' ? [...precedent.corrige, valeurAffichee] : precedent.corrige,
      vide: action === 'vide' ? [...precedent.vide, message.cle] : precedent.vide,
    }
    bilansRef.current = { ...bilansRef.current, [message.pageNo]: bilan }
    setBilans(bilansRef.current)
    if (message.numero === message.total) {
      // Fin de la page : récapitulatif clair, puis l'action suivante.
      ajouter({ auteur: 'agent', type: 'recap', pageNo: message.pageNo, bilan, texte: texte('recap.titre', { type: { typePage: page.type_page } }), options: OPTIONS_SUITE })
    }
    terminerQuestion()
  }, [ajouter, champDuDossier, dire, dossier, enregistrerChamp, ouvrirAppareil, repondreSf, terminerQuestion])

  const toutConfirmer = useCallback(async () => {
    if (!dossier) return
    setOccupe(true)
    try {
      const r = await api.confirmerFiables(dossier.dossier_id)
      setDossier(r.dossier)
      dire('msg.toutConfirme', { n: r.confirmes })
    } catch (erreur) {
      if (erreur.hors_ligne) dire('msg.horsLigneConfirmer')
      else dire('msg.valeurRefusee', { detail: erreur.message })
    } finally {
      setOccupe(false)
    }
  }, [dire, dossier])

  // ---------- Liaison à une patiente : toujours une décision explicite, jamais de création automatique ----------
  const lancerLiaison = useCallback(() => {
    dire('liaison.demande', null, {
      type: 'choix', unique: true,
      options: [{ id: 'liaison:oui', libelle: texte('liaison.ouiCode') }, { id: 'liaison:non', libelle: texte('liaison.nonCode') }],
    })
  }, [dire])

  const chercherPatientes = useCallback(async (code) => {
    if (!dossier) return
    setOccupe(true)
    try {
      const r = await api.correspondances({ numero: dossier.numero_fiche, code })
      const inconnu = { id: 'liaison:inconnu', libelle: texte('liaison.inconnu') }
      // Code déjà écrit par la sage-femme sur le registre : elle peut créer la patiente avec CE code.
      const avecSonCode = code ? [{ id: `liaison:creerCode:${code}`, libelle: texte('liaison.creerAvecCode', { code }) }] : []
      if (r.candidates.length === 0) {
        dire('liaison.aucuneCandidate', null, { type: 'choix', unique: true, options: [...avecSonCode, { id: 'liaison:creer', libelle: texte('liaison.creerSeule') }, inconnu] })
      } else {
        dire('liaison.candidates', null, {
          type: 'choix', unique: true,
          options: [
            ...r.candidates.map((c, i) => ({
              id: `liaison:patiente:${c.patiente_id}:${c.code || ''}`,
              libelle: texte('liaison.patiente', { n: i + 1, code: c.code || '—', numero: c.numero_fiche || '—', visites: texte('liaison.visites', { n: c.nb_visites }), date: dateLisible(c.derniere_visite) }),
            })),
            { id: 'liaison:creer', libelle: texte('liaison.creer') },
            inconnu,
          ],
        })
      }
    } catch (erreur) {
      if (erreur.hors_ligne) dire('liaison.horsLigne')
      else dire('msg.valeurRefusee', { detail: erreur.message })
    } finally {
      setOccupe(false)
    }
  }, [dire, dossier])

  // Après la décision de liaison : enregistrement (ENREGISTRE), puis synchronisation avec le système de
  // santé (SYNCHRONISE, ou ECHEC_SYNCHRONISATION en cas de panne : nouvelle tentative au retour du réseau).
  const finaliser = useCallback(async (dossierId) => {
    try {
      const e = await api.enregistrer(dossierId)
      setDossier(e.dossier)
      dire('cycle.enregistre')
      const s = await api.synchroniser({ simulerPanne: panneCentraleSimulee() })
      if (s.synchronises.includes(dossierId)) {
        dire('cycle.synchronise')
        setDossier(await api.dossier(dossierId))
      } else if (s.echecs.includes(dossierId)) {
        dire('cycle.echecSync')
        setDossier(await api.dossier(dossierId))
      }
    } catch (erreur) {
      if (erreur.hors_ligne) dire('cycle.horsLigne')
      else dire('msg.valeurRefusee')
    }
  }, [dire])

  // Registre terminé : ouvrir le dossier ou commencer le registre suivant.
  const proposerFin = useCallback(async (dossierId) => {
    await finaliser(dossierId)
    dire('msg.fin', null, {
      type: 'choix', unique: true,
      options: [{ id: `ouvrir:${dossierId}`, libelle: texte('option.ouvrirDossier') }, { id: 'nouveau', libelle: texte('option.nouveauRegistre') }],
    })
  }, [dire, finaliser])

  const lier = useCallback(async (choix) => {
    if (!dossier) return
    setOccupe(true)
    try {
      const r = await api.lier(dossier.dossier_id, choix)
      setDossier(r.dossier)
      if (r.patient_created) ajouter({ auteur: 'agent', type: 'code', code: r.code, texte: texte('liaison.codeCree') })
      else {
        dire('liaison.liee', { code: r.code || '—' })
        proposerFin(r.dossier.dossier_id)
      }
    } catch (erreur) {
      if (erreur.hors_ligne) dire('liaison.horsLigne')
      else dire('msg.valeurRefusee', { detail: erreur.message })
    } finally {
      setOccupe(false)
    }
  }, [ajouter, dire, dossier, proposerFin])

  const soumettreCode = useCallback((message, code) => {
    setReponses((r) => ({ ...r, [message.id]: code }))
    ajouter({ auteur: 'sf', type: 'texte', texte: code })
    chercherPatientes(code)
  }, [ajouter, chercherPatientes])

  const codeRecopie = useCallback((message) => {
    setReponses((r) => ({ ...r, [message.id]: 'recopie' }))
    repondreSf('liaison.codeRecopie')
    dire('liaison.merci')
    if (dossier) proposerFin(dossier.dossier_id)
  }, [dire, dossier, proposerFin, repondreSf])

  const choisirLiaison = useCallback((id) => {
    const [, action, patienteId, code] = id.split(':')
    if (action === 'oui') ajouter({ auteur: 'agent', type: 'saisieCode', texte: texte('liaison.saisirCode') })
    else if (action === 'non') chercherPatientes(null)
    else if (action === 'creer') lier({ choix: 'nouvelle' })
    else if (action === 'creerCode') lier({ choix: 'nouvelle', code: patienteId })
    else if (action === 'patiente') lier({ patiente_id: patienteId, code })
    else if (action === 'inconnu') {
      dire('liaison.plusTard')
      if (dossier) proposerFin(dossier.dossier_id)
    }
  }, [ajouter, chercherPatientes, dire, dossier, lier, proposerFin])

  // ---------- Renumérisation : seuls les champs choisis remplacent l'existant ----------
  const appliquerRenumerisation = useCallback(async (message, cles) => {
    if (!dossier) return
    setOccupe(true)
    try {
      const r = await api.renumeriser(dossier.dossier_id, { ancienne_page: message.ancienne, nouvelle_page: message.nouvelle, champs: cles })
      setDossier(r.dossier)
      setReponses((x) => ({ ...x, [message.id]: cles }))
      if (cles.length) dire('renum.fait', { n: cles.length })
      else dire('renum.identique')
    } catch (erreur) {
      if (erreur.hors_ligne) dire('msg.horsLigneReponse')
      else dire('msg.valeurRefusee', { detail: erreur.message })
    } finally {
      setOccupe(false)
    }
  }, [dire, dossier])

  // Un seul message de blocage dans le fil : s'il existe (non clos), on y ramène au lieu d'en ajouter un.
  const expliquerBlocages = useCallback((serveur = []) => {
    setDetailOuvert(false) // l'explication s'affiche dans le fil : la fenêtre du dossier se ferme
    const invalides = serveur.some((b) => b.code === 'donnees_invalides')
    const existant = messagesRef.current.find((m) => m.type === 'blocage' && m.vivant && reponsesRef.current[m.id] === undefined)
    if (existant) {
      setMessages((ms) => ms.map((m) => (m.id === existant.id ? { ...m, invalides } : m)))
      setTimeout(() => document.getElementById(`msg-${existant.id}`)?.scrollIntoView({ block: 'center' }), 50)
      return
    }
    ajouter({ auteur: 'agent', type: 'blocage', vivant: true, invalides, texte: texte('valid.bloque') })
  }, [ajouter])

  // Ouvre directement la question d'un champ : celle du fil si elle attend, sinon une question ponctuelle.
  const verifierChamp = useCallback((cle, pageNo) => {
    const attente = messagesRef.current.find((m) => m.type === 'question' && m.cle === cle && m.pageNo === pageNo && reponsesRef.current[m.id] === undefined)
    if (attente) {
      document.getElementById(`msg-${attente.id}`)?.scrollIntoView({ block: 'center' })
      return
    }
    fileRef.current = fileRef.current.filter((q) => !(q.cle === cle && q.pageNo === pageNo))
    const id = nouvelId()
    setMessages((m) => [...m, { id, auteur: 'agent', type: 'question', cle, pageNo, numero: 1, total: 1, ponctuelle: true }])
    setTimeout(() => document.getElementById(`msg-${id}`)?.scrollIntoView({ block: 'center' }), 80)
  }, [])

  const validerDossier = useCallback(async () => {
    if (!dossier) return
    // Blocages connus de l'appareil : pages encore en file ou en lecture, comparaison sans réponse.
    const locaux = []
    const enCoursLecture = capturesRef.current.filter((c) => EN_ATTENTE.includes(c.etat)).length
    if (enCoursLecture) locaux.push({ code: 'en_lecture', n: enCoursLecture })
    const comparaison = messagesRef.current.find((m) => m.type === 'renum' && reponsesRef.current[m.id] === undefined)
    if (comparaison) locaux.push({ code: 'comparaison', messageId: comparaison.id })
    if (locaux.length) {
      expliquerBlocages()
      return
    }
    setOccupe(true)
    try {
      const r = await api.valider(dossier.dossier_id)
      setDossier(r.dossier)
      if (r.can_validate) {
        // Le message de blocage se clôt : la validation est faite.
        const ouverts = messagesRef.current.filter((m) => m.type === 'blocage' && m.vivant && reponsesRef.current[m.id] === undefined)
        if (ouverts.length) setReponses((x) => ({ ...x, ...Object.fromEntries(ouverts.map((m) => [m.id, 'valide'])) }))
        dire('msg.valide')
        lancerLiaison()
      } else expliquerBlocages(r.blocages || [])
    } catch (erreur) {
      if (erreur.hors_ligne) dire('msg.horsLigneValider')
      else dire('msg.valeurRefusee', { detail: erreur.message })
    } finally {
      setOccupe(false)
    }
  }, [dire, dossier, expliquerBlocages, lancerLiaison])

  const relancer = useCallback((localId) => {
    const c = capturesRef.current.find((x) => x.localId === localId)
    if (!c?.captureId) return
    terminees.current.delete(localId)
    dire('msg.relance', { n: c.pageNo })
    majCapture(localId, { etat: 'A_TRAITER' })
    setTimeout(() => envoyer(localId), 0)
  }, [dire, envoyer, majCapture])

  const choisir = useCallback((option, message) => {
    if (message?.unique) {
      // Choix à réponse unique : la réponse s'affiche côté sage-femme et les boutons se figent.
      setReponses((r) => ({ ...r, [message.id]: option.id }))
      ajouter({ auteur: 'sf', type: 'texte', texte: option.libelle })
    }
    if (option.id.startsWith('liaison:')) choisirLiaison(option.id)
    else if (option.id === 'diff:meme' && message?.comparaison) ajouter(message.comparaison)
    else if (option.id.startsWith('autre:')) choisirAutrePatienteRef.current(option.id.split(':')[1], option.id.split(':')[2])
    else if (option.id.startsWith('aller:')) document.getElementById(`msg-${option.id.slice(6)}`)?.scrollIntoView({ block: 'center' })
    else if (option.id === 'questions') reposerQuestions()
    else if (option.id.startsWith('verifier:')) {
      const [, pageNo, ...cle] = option.id.split(':')
      verifierChamp(cle.join(':'), Number(pageNo))
    } else if (option.id === 'filtre') { setFiltreAVerifier(true); setDetailOuvert(true) }
    else if (option.id.startsWith('demander:')) {
      const cle = option.id.slice(9)
      const page = dossier?.pages?.find((p) => p.champs.some((c) => c.champ === cle))
      if (page) ajouterQuestions([{ cle, pageNo: page.page_no, numero: 1, total: 1 }])
    }
    else if (option.id.startsWith('qualite:')) deciderQualite(option.id.split(':')[1], option.id.split(':')[2])
    else if (option.id === 'lier') lancerLiaison()
    else if (option.id === 'detail') setDetailOuvert(true)
    else if (option.id === 'photo') ouvrirAppareil()
    else if (option.id.startsWith('ouvrir:')) naviguer(`/app/dossiers/${option.id.slice(7)}`)
    else if (option.id === 'nouveau') { if (!nouveauRegistreRef.current()) dire('conv.nouveauRegistreFile') }
    else if (option.id === 'tout_confirmer') toutConfirmer()
    else if (option.id === 'valider') validerDossier()
    else if (option.id === 'reprendre') ouvrirAppareil()
    else if (option.id.startsWith('relancer:')) relancer(option.id.split(':')[1])
    else if (option.id.startsWith('saisie:')) {
      const pageNo = Number(option.id.split(':')[1])
      dire('msg.quellePage', { n: pageNo }, {
        type: 'choix',
        options: TYPES_PAGE.map((type) => ({ id: `type:${pageNo}:${type}`, libelle: texte(`type.${type}`) })),
      })
    } else if (option.id.startsWith('type:')) {
      const [, pageNo, type] = option.id.split(':')
      setPagesEnSaisie((ps) => [...ps.filter((p) => p.page_no !== Number(pageNo)), pageVide(schema, Number(pageNo), type)])
      dire('msg.saisie', { type: { typePage: type } })
      setDetailOuvert(true)
    }
  }, [ajouter, ajouterQuestions, choisirLiaison, deciderQualite, dire, dossier, lancerLiaison, reposerQuestions, verifierChamp, ouvrirAppareil, relancer, schema, toutConfirmer, validerDossier])

  const choisirAutrePatiente = useCallback(async (action, localId) => {
    const c = capturesRef.current.find((x) => x.localId === localId)
    const d = dossierRef.current
    if (!c || !d) return
    if (action === 'ajouter') {
      analyserPage(c, d)
      return
    }
    setOccupe(true)
    try {
      if (action === 'annuler') {
        const r = await api.retirerPage(d.dossier_id, c.pageNo)
        setDossier(r.dossier)
        majCapture(localId, { etat: 'ABANDONNEE' })
        dire('patiente.annulee', { n: c.pageNo })
        return
      }
      // Nouveau registre avec cette page : la capture déjà lue y est déplacée (pas de nouvel envoi).
      if (capturesRef.current.some((x) => x.localId !== localId && EN_ATTENTE.includes(x.etat))) {
        dire('conv.nouveauRegistreFile')
        return
      }
      const sid = nouvelId()
      const r = await api.deplacerCapture(c.captureId, { session_id: sid, page_no: 1 })
      const autres = capturesRef.current.filter((x) => x.localId !== localId)
      autres.forEach((x) => x.url && URL.revokeObjectURL(x.url))
      supprimerPhotos(autres.map((x) => x.localId)).catch(() => {})
      journal.current = []
      sauverDocument('journal', []).catch(() => {})
      setSessionId(nouvelleSession(sid))
      const deplacee = { ...c, pageNo: 1 }
      capturesRef.current = [deplacee]
      dernierePage.current = 1
      setCaptures([deplacee])
      setDossier(r.dossier)
      fileRef.current = []
      activeRef.current = null
      setQuestionActive(null)
      setReponses({}); setPagesEnSaisie([])
      bilansRef.current = {}
      setBilans({})
      terminees.current = new Set([localId])
      setMessages([BIENVENUE,
        { id: nouvelId(), auteur: 'sf', type: 'photo', localId, pageNo: 1 },
        { id: nouvelId(), auteur: 'agent', type: 'texte', texte: texte('patiente.deplacee', { numero: r.dossier.numero_fiche || '—' }) }])
      analyserPage(deplacee, r.dossier)
    } catch (erreur) {
      if (erreur.hors_ligne) dire('msg.horsLigneReponse')
      else dire('msg.valeurRefusee')
    } finally {
      setOccupe(false)
    }
  }, [analyserPage, dire, majCapture])

  // Retire du registre une page (doublon suspecté) : elle n'a jamais été ajoutée au dossier côté serveur.
  const retirerCapture = useCallback((localId) => {
    const c = capturesRef.current.find((x) => x.localId === localId)
    if (!c) return
    if (c.url) URL.revokeObjectURL(c.url)
    supprimerPhotos([localId]).catch(() => {})
    journal.current = journal.current.filter((j) => j.localId !== localId)
    sauverDocument('journal', journal.current).catch(() => {})
    setCaptures((cs) => cs.filter((x) => x.localId !== localId))
    dire('pages.retiree', { n: c.pageNo })
  }, [dire])

  // Rouvre un dossier existant dans la conversation (vue du dossier, « Reprendre la vérification ») :
  // la conversation en cours est remplacée (son dossier reste sur le serveur), puis la première question
  // restante est posée. Refusé tant qu'une photo du registre en cours attend d'être envoyée ou lue.
  const reprendreDossier = useCallback((d) => {
    if (capturesRef.current.some((c) => EN_ATTENTE.includes(c.etat))) return false
    capturesRef.current.forEach((c) => c.url && URL.revokeObjectURL(c.url))
    supprimerPhotos(capturesRef.current.map((c) => c.localId)).catch(() => {})
    journal.current = []
    sauverDocument('journal', []).catch(() => {})
    setSessionId(nouvelleSession(d.session_id))
    setDetailOuvert(false)
    setFiltreAVerifier(false)
    const reprises = (d.captures || []).map((c) => ({ localId: nouvelId(), captureId: c.capture_id, pageNo: c.page_no, etat: c.etat, typePage: c.type_page, fichier: null, url: null }))
    capturesRef.current = reprises
    dernierePage.current = Math.max(0, ...reprises.map((c) => c.pageNo))
    terminees.current = new Set(reprises.map((c) => c.localId))
    setCaptures(reprises)
    dossierRef.current = d
    setDossier(d)
    fileRef.current = []
    activeRef.current = null
    setQuestionActive(null)
    setReponses({}); setPagesEnSaisie([])
    bilansRef.current = {}
    setBilans({})
    setMessages([BIENVENUE, { id: nouvelId(), auteur: 'agent', type: 'texte', texte: texte('reprise.message', { titre: d.patiente_code || d.numero_fiche
      || texte('dossiers.titreDate', { date: dateLisible(d.captures?.[0]?.date_capture || d.historique_etats?.[0]?.date),
        type: { typePage: [...(d.pages || [])].sort((a, b) => a.page_no - b.page_no)[0]?.type_page || 'IDENTIFICATION' } }) }) }])
    setTimeout(() => reposerQuestions(), 0)
    // Photos d'origine (vignettes des questions), selon le rôle ; sans connexion, les questions restent lisibles.
    reprises.forEach((c) => {
      api.image(c.captureId).then((blob) => majCapture(c.localId, { url: URL.createObjectURL(blob) })).catch(() => {})
    })
    return true
  }, [majCapture, reposerQuestions])

  // Nouveau registre : refusé tant qu'une photo attend d'être envoyée ou lue (aucun enregistrement perdu).
  const nouveauRegistre = useCallback(() => {
    if (capturesRef.current.some((c) => EN_ATTENTE.includes(c.etat))) return false
    capturesRef.current.forEach((c) => c.url && URL.revokeObjectURL(c.url))
    supprimerPhotos(capturesRef.current.map((c) => c.localId)).catch(() => {})
    journal.current = []
    sauverDocument('journal', []).catch(() => {})
    dernierePage.current = 0
    setSessionId(nouvelleSession())
    setCaptures([]); setDossier(null); setMessages([BIENVENUE]); setQuestionActive(null)
    fileRef.current = []
    activeRef.current = null
    setReponses({}); setPagesEnSaisie([])
    bilansRef.current = {}
    setBilans({})
    terminees.current = new Set()
    return true
  }, [])
  useEffect(() => { nouveauRegistreRef.current = nouveauRegistre }, [nouveauRegistre])
  useEffect(() => { choisirAutrePatienteRef.current = choisirAutrePatiente }, [choisirAutrePatiente])

  const valeur = useMemo(() => ({
    pret, schema, seuil, sessionId, captures, dossier, messages, questionActive, reponses, detailOuvert, pagesEnSaisie, occupe,
    setDetailOuvert, prendrePhoto, repondre, choisir, enregistrerChamp, toutConfirmer, validerDossier, nouveauRegistre,
    champDuDossier, soumettreCode, codeRecopie, appliquerRenumerisation, retirerCapture, reprendreDossier, blocages, requis, filtreAVerifier, setFiltreAVerifier, fiablesAConfirmer,
    ouvrirAppareil, enregistrerAppareil: (fonction) => { ouvrirAppareilRef.current = fonction },
  }), [pret, schema, seuil, sessionId, captures, dossier, messages, questionActive, reponses, detailOuvert, pagesEnSaisie, occupe,
    prendrePhoto, repondre, choisir, enregistrerChamp, toutConfirmer, validerDossier, nouveauRegistre, champDuDossier,
    soumettreCode, codeRecopie, appliquerRenumerisation, retirerCapture, reprendreDossier, blocages, requis, filtreAVerifier, fiablesAConfirmer, ouvrirAppareil])

  return <ConversationContexte.Provider value={valeur}>{children}</ConversationContexte.Provider>
}

// eslint-disable-next-line react-refresh/only-export-components
export function useConversation() {
  return useContext(ConversationContexte)
}
