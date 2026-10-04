import { useCallback, useEffect, useLayoutEffect, useRef, useState } from 'react'
import CarteQuestion from '../components/CarteQuestion'
import CarteRenumerisation from '../components/CarteRenumerisation'
import Compositeur from '../components/Compositeur'
import DetailDossier, { ContenuDossier } from '../components/DetailDossier'
import { IconeAppareil } from '../components/Icones'
import FilePages from '../components/FilePages'
import IllustrationRegistre from '../components/IllustrationRegistre'
import MessageBlocage from '../components/MessageBlocage'
import { useConversation } from '../etat/conversation'
import { GRAND_ECRAN, useRequeteMedia } from '../etat/largeur'
import { useLangue } from '../i18n'
import { definitionChamp, libelleChamp } from '../lib/format'
import { rendreTexte } from '../lib/textes'

const SEUIL_BAS_PX = 80
const mouvementReduit = () => window.matchMedia?.('(prefers-reduced-motion: reduce)').matches

// Récapitulatif d'une page vérifiée : confirmé, corrigé, laissé vide.
function Recapitulatif({ bilan, rendre, libelle }) {
  const { t } = useLangue()
  const groupes = [
    ['recap.confirme', bilan.confirme.map(libelle)],
    ['recap.corrige', bilan.corrige.map((c) => `${libelle(c.champ)} : ${rendre(c)}`)],
    ['recap.vide', bilan.vide.map(libelle)],
  ].filter(([, liste]) => liste.length)
  return (
    <dl className="recap">
      {groupes.map(([cle, liste]) => (
        <div key={cle}>
          <dt>{t(cle, { n: liste.length })}</dt>
          {liste.map((x, i) => <dd key={i} dir="auto">{x}</dd>)}
        </div>
      ))}
    </dl>
  )
}

// Écran de vérification : la conversation (logique dans etat/conversation.jsx).
// Grand écran : le dossier en cours s'affiche à côté du fil, pour vérifier sans changer d'écran.
export default function Conversation() {
  const { t, langue } = useLangue()
  const conv = useConversation()
  const { schema, seuil, captures, dossier, messages, questionActive, reponses, occupe } = conv
  const grandEcran = useRequeteMedia(GRAND_ECRAN)
  const inputPhoto = useRef(null)
  const fil = useRef(null)
  const enBas = useRef(true)
  const [nouveaux, setNouveaux] = useState(false)
  // Zone de saisie en bas du fil (Corriger, valeur à saisir, code de liaison).
  const [saisie, setSaisie] = useState(null)
  const ouvertes = useRef(new Set())
  const contexte = { t, langue, schema }
  const rendre = (x) => rendreTexte(x, contexte)
  const libelle = useCallback((cle) => libelleChamp(schema, cle, langue, t), [langue, schema, t])

  useEffect(() => {
    conv.enregistrerAppareil(() => inputPhoto.current?.click())
  }, [conv])

  const allerEnBas = useCallback((doux = true) => {
    const el = fil.current
    if (!el) return
    el.scrollTo({ top: el.scrollHeight, behavior: doux && !mouvementReduit() ? 'smooth' : 'auto' })
    enBas.current = true
    setNouveaux(false)
  }, [])

  // Défilement automatique vers le dernier message, sauf si la sage-femme relit plus haut :
  // on affiche alors « Nouveaux messages ↓ ». Ses propres messages ramènent toujours en bas.
  const dernier = messages[messages.length - 1]
  useLayoutEffect(() => {
    if (enBas.current || dernier?.auteur === 'sf') allerEnBas(false)
    else setNouveaux(true)
  }, [messages.length, questionActive, dernier?.auteur, allerEnBas])

  const corriger = useCallback((m, champ, titreCle = 'saisie.corriger') => {
    setSaisie({
      titre: t(titreCle, { champ: libelle(m.cle) }),
      definition: definitionChamp(schema, m.cle),
      valeurInitiale: champ.valeur,
      onEnvoyer: (valeur) => conv.repondre(m, { action: 'corriger', valeur }),
    })
  }, [conv, libelle, schema, t])
  const saisirCode = useCallback((m) => {
    setSaisie({ titre: t('saisie.code'), type: 'code', onEnvoyer: (code) => conv.soumettreCode(m, code) })
  }, [conv, t])

  // Une saisie nécessaire s'ouvre d'elle-même (une fois) : question sans valeur lue, code de liaison demandé.
  useEffect(() => {
    if (!dernier || reponses[dernier.id] !== undefined || ouvertes.current.has(dernier.id)) return
    if (dernier.type === 'saisieCode') {
      ouvertes.current.add(dernier.id)
      // Ouverture unique par message (suivie dans « ouvertes ») : pas de rendu en cascade.
      // eslint-disable-next-line react-hooks/set-state-in-effect
      saisirCode(dernier)
    } else if (dernier.type === 'question') {
      const champ = conv.champDuDossier(dernier.cle, dernier.pageNo)
      if (champ && (champ.valeur === null || champ.valeur === undefined)) {
        ouvertes.current.add(dernier.id)
        corriger(dernier, champ, 'saisie.saisir')
      }
    }
  }, [conv, corriger, dernier, reponses, saisirCode])

  // La zone de saisie réduit le fil : on garde le dernier message (la question en cours) visible.
  useEffect(() => {
    if (saisie && enBas.current) requestAnimationFrame(() => allerEnBas(false))
  }, [saisie, allerEnBas])

  function surDefilement() {
    const el = fil.current
    enBas.current = el.scrollHeight - el.scrollTop - el.clientHeight < SEUIL_BAS_PX
    if (enBas.current && nouveaux) setNouveaux(false)
  }

  function texteSuivi(c) {
    if (!c) return ''
    if (c.etat === 'EN_ATTENTE_IA') return t('suivi.EN_ATTENTE_IA', { n: c.pageNo, duree: c.duree || 20 })
    if (['EN_FILE', 'QUALITE', 'ENVOI', 'CAPTURE', 'A_TRAITER', 'DOUBLON_SUSPECTE', 'REFUSEE', 'ABANDONNEE'].includes(c.etat)) {
      return t(`suivi.${c.etat}`, { n: c.pageNo })
    }
    const type = dossier?.pages?.find((p) => p.page_no === c.pageNo)?.type_page || c.typePage
    return t('suivi.final', { page: type ? t(`type.${type}`) : t('commun.page', { n: c.pageNo }), etat: t(`etat.${c.etat}`) })
  }

  function boutonsChoix(m, options) {
    const choisi = m.unique ? reponses[m.id] : undefined
    return (
      <div className={`choix-rapides ${m.unique ? 'liste' : ''}`}>
        {options.filter((o) => o.id !== 'tout_confirmer' || conv.fiablesAConfirmer > 0).map((o) => (
          <button type="button" key={o.id} className={o.id === 'detail' ? 'navigation' : ''} aria-pressed={m.unique ? choisi === o.id : undefined}
            disabled={occupe || choisi !== undefined} onClick={() => conv.choisir(o, m)}>
            {rendre(o.libelle)}
          </button>
        ))}
        {options.some((o) => o.id === 'tout_confirmer') && conv.fiablesAConfirmer > 0 && choisi === undefined && (
          <p className="aide aide-bouton">{t('aide.toutConfirmer')}</p>
        )}
      </div>
    )
  }

  function rendreMessage(m) {
    if (m.type === 'photo') {
      const c = captures.find((x) => x.localId === m.localId)
      return (
        <figure className="bulle bulle-sf photo">
          {c?.url && <img src={c.url} alt={t('commun.page', { n: m.pageNo })} onLoad={() => { if (enBas.current) allerEnBas(false) }} />}
          <figcaption><span className="tampon">{t('commun.page', { n: m.pageNo })}</span></figcaption>
        </figure>
      )
    }
    if (m.type === 'suivi') {
      const c = captures.find((x) => x.localId === m.localId)
      const lecture = c?.etat === 'EN_ATTENTE_IA' || c?.etat === 'ENVOI'
      return (
        <div className={`bulle bulle-agent suivi ${lecture ? 'en-lecture' : ''}`}>
          {lecture && <span className="scan-lecture" aria-hidden="true" />}
          {lecture && <span className="lecture-indicateur" aria-hidden="true"><i /><i /><i /></span>}
          <p>{texteSuivi(c)}</p>
          {c?.etat === 'EN_ATTENTE_IA' && (
            <div className="progression" role="progressbar" aria-label={texteSuivi(c)} aria-valuenow={Math.round((c.progression || 0) * 100)} aria-valuemin={0} aria-valuemax={100}>
              <span style={{ width: `${Math.max(5, (c.progression || 0) * 100)}%` }} />
            </div>
          )}
        </div>
      )
    }
    if (m.type === 'question') {
      const champ = conv.champDuDossier(m.cle, m.pageNo)
      if (!champ) return null
      return (
        <div className="bulle bulle-agent large sans-fond">
          <CarteQuestion champ={champ} schema={schema} seuil={seuil} numero={m.numero} total={m.total} pageNo={m.pageNo}
            photoUrl={captures.find((c) => c.pageNo === m.pageNo)?.url} reponse={reponses[m.id]}
            occupe={occupe} onRepondre={(r) => conv.repondre(m, r)} onCorriger={() => corriger(m, champ)} />
        </div>
      )
    }
    if (m.type === 'recap') {
      return (
        <div className="bulle bulle-agent large">
          <p><b>{rendre(m.texte)}</b></p>
          <Recapitulatif bilan={m.bilan} rendre={rendre} libelle={libelle} />
          <p className="recap-suite">{t('recap.suite')}</p>
          {boutonsChoix(m, m.options)}
        </div>
      )
    }
    if (m.type === 'blocage' && m.vivant) {
      return <MessageBlocage message={m} blocages={conv.blocages} schema={schema} clos={reponses[m.id] !== undefined} occupe={occupe} onChoisir={conv.choisir} />
    }
    if (m.type === 'blocage') {
      return (
        <div className="bulle bulle-agent blocage" role="status">
          <p><b>{rendre(m.texte)}</b></p>
          <ul>{m.lignes.map((l, i) => <li key={i}>{rendre(l)}</li>)}</ul>
          {m.options.length > 0 && boutonsChoix(m, m.options)}
        </div>
      )
    }
    if (m.type === 'choix') {
      return (
        <div className="bulle bulle-agent">
          <p>{rendre(m.texte)}</p>
          {boutonsChoix(m, m.options)}
        </div>
      )
    }
    if (m.type === 'saisieCode') {
      return (
        <div className="bulle bulle-agent">
          <p>{rendre(m.texte)}</p>
          {reponses[m.id] === undefined && (
            <div className="choix-rapides"><button type="button" onClick={() => saisirCode(m)}>{t('liaison.saisirCodeBouton')}</button></div>
          )}
        </div>
      )
    }
    if (m.type === 'code') {
      return (
        <div className="bulle bulle-agent">
          <p>{rendre(m.texte)}</p>
          <p className="code-liaison" aria-label={m.code.split('').join(' ')}>{m.code}</p>
          {!reponses[m.id] && (
            <div className="choix-rapides">
              <button type="button" onClick={() => conv.codeRecopie(m)}>{t('liaison.codeRecopie')}</button>
            </div>
          )}
        </div>
      )
    }
    if (m.type === 'renum') {
      return (
        <div className="bulle bulle-agent large">
          <p>{rendre(m.texte)}</p>
          {m.compte && <p className="renum-compte"><b>{t(`type.${m.typePage}`)}</b> · {rendre(m.compte)}</p>}
          <CarteRenumerisation message={m} schema={schema} reponse={reponses[m.id]} occupe={occupe}
            onAppliquer={(cles) => conv.appliquerRenumerisation(m, cles)} />
        </div>
      )
    }
    return <div className={`bulle ${m.auteur === 'sf' ? 'bulle-sf' : 'bulle-agent'}`}><p dir="auto">{rendre(m.texte)}</p></div>
  }

  const propsDossier = {
    dossier, pagesEnSaisie: conv.pagesEnSaisie, schema, seuil, occupe,
    onCorriger: conv.enregistrerChamp, onToutConfirmer: conv.toutConfirmer, onValider: conv.validerDossier,
    requis: conv.requis, filtre: conv.filtreAVerifier, onFiltre: conv.setFiltreAVerifier,
  }

  return (
    <div className="conversation">
      <div className="conversation-chat">
        {captures.length > 0 && (
          <FilePages captures={captures} dossier={dossier} seuil={seuil} occupe={occupe} onRetirer={conv.retirerCapture}
            onOuvrirDossier={grandEcran ? null : () => conv.setDetailOuvert(true)}
            onNouveauRegistre={() => {
              if (!window.confirm(t('conv.nouveauRegistreConfirmer'))) return
              if (!conv.nouveauRegistre()) window.alert(t('conv.nouveauRegistreFile'))
            }} />
        )}

        <div className="fil-cadre">
          <div className="fil" ref={fil} onScroll={surDefilement} aria-live="polite" aria-relevant="additions">
            {schema?.fournisseur_extraction && schema.fournisseur_extraction !== 'anthropic' && (
              <p className="avis-mode" role="note">{t('conv.modeSansLecture')}</p>
            )}
            {captures.length === 0 && messages.length === 1 ? (
              <section className="accueil-conversation">
                <IllustrationRegistre petite />
                <p className="consigne">{t('conv.consigne')}</p>
                <p className="aide">{t('conv.bienvenue')}</p>
              </section>
            ) : messages.map((m) => (
              <div key={m.id} id={`msg-${m.id}`} className={`ligne-message ${m.auteur === 'sf' ? 'cote-sf' : 'cote-agent'}`}>{rendreMessage(m)}</div>
            ))}
          </div>
          {nouveaux && (
            <button type="button" className="nouveaux-messages" onClick={() => allerEnBas()}>
              {t('conv.nouveauxMessages')} <span aria-hidden="true">↓</span>
            </button>
          )}
        </div>

        {saisie ? (
          <Compositeur saisie={saisie} onFermer={() => setSaisie(null)} />
        ) : (
          <button type="button" className="bouton-photo flottant" onClick={() => inputPhoto.current?.click()} aria-label={t('conv.photo')}>
            <IconeAppareil taille={26} />
          </button>
        )}
        <input ref={inputPhoto} type="file" accept="image/png,image/jpeg" capture="environment" hidden
          onChange={(e) => { conv.prendrePhoto(e.target.files?.[0]); e.target.value = '' }} />
      </div>

      {grandEcran && (
        <aside className="panneau-lateral" aria-label={t('lateral.titre')}>
          <ContenuDossier {...propsDossier} entete={<h2 className="lateral-titre">{t('lateral.titre')}</h2>} />
        </aside>
      )}

      {conv.detailOuvert && !grandEcran && <DetailDossier {...propsDossier} onFermer={() => conv.setDetailOuvert(false)} />}
    </div>
  )
}
