// Données lues sur le serveur et gardées (chiffrées) sur l'appareil : hors ligne, la dernière copie s'affiche.
import { useCallback, useEffect, useState } from 'react'
import { lireDocument, sauverDocument } from '../lib/coffre'

export function useDonnees(cle, charger, connecte) {
  const [etat, setEtat] = useState({ donnees: null, chargement: true, horsLigne: false, erreur: null })

  const recharger = useCallback(async () => {
    setEtat((e) => ({ ...e, chargement: true }))
    try {
      if (!connecte) throw Object.assign(new Error('hors ligne'), { hors_ligne: true })
      const donnees = await charger()
      setEtat({ donnees, chargement: false, horsLigne: false, erreur: null })
      sauverDocument(cle, donnees).catch(() => {})
    } catch (erreur) {
      const copie = await lireDocument(cle).catch(() => null)
      setEtat({ donnees: copie, chargement: false, horsLigne: Boolean(erreur.hors_ligne), erreur: erreur.hors_ligne ? null : erreur })
    }
  }, [charger, cle, connecte])

  useEffect(() => {
    // Chargement initial, puis à chaque changement de connexion.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    recharger()
  }, [recharger])

  return { ...etat, recharger }
}
