# FirstBreath — page Devpost

## Français

### Inspiration
Dans de nombreux centres de santé, les sages-femmes consignent la grossesse, l'accouchement et le post-partum dans
un registre papier de plusieurs pages. Une fois écrite, l'information ne suit pas la femme d'une visite à l'autre
et ne remonte pas au système de santé. Nous voulions que ce registre devienne un dossier numérique fiable, sans
changer la pratique de la sage-femme : le papier reste la référence, le numérique s'y greffe.

### Ce que fait FirstBreath
- **Lecture** : la sage-femme photographie chaque page avec son téléphone, même sans réseau. L'agent la lit selon
  un schéma de 245 champs, avec un statut explicite (connu, inconnu, non fourni, illisible, sans objet, à
  vérifier) et une confiance pour chaque champ.
- **Vérification** : l'agent ne pose une question que lorsqu'il doute, une à la fois, comme dans WhatsApp. Il
  dit pourquoi il doute et propose quatre réponses de même poids : Confirmer, Corriger, Vide sur le papier,
  Reprendre la photo.
- **Hors ligne** : les photos sont chiffrées sur l'appareil, mises en file « En attente de traitement IA »,
  envoyées et lues au retour du réseau, puis synchronisées avec le système de santé. Aucun enregistrement n'est
  perdu.
- **Liaison** : les visites d'une même femme sont reliées par un code court recopié sur le registre.
  L'application propose les correspondances possibles, et la sage-femme tranche : [Patiente 1] [Patiente 2]
  [Aucune, créer] [Je ne sais pas].
- **Image d'origine** : elle reste liée au dossier, avec un accès selon le rôle.
- **Tableau de bord** : un tableau anonymisé (tension, température, VIH, syphilis, hépatite C) illustre l'usage
  épidémiologique ; toute case de moins de 5 dossiers est masquée.

### Comment nous l'avons construit
- **Extraction** : `claude-sonnet-5` lit chaque page avec une sortie structurée par appel d'outil, générée depuis
  le schéma. `claude-haiku-4-5` détecte le type de page quand il est inconnu. La normalisation applique les
  conventions communes et une confiance finale, qui combine plausibilité, cohérence entre champs et effort de
  réflexion.
- **Évaluation** : une vérité terrain sur les patientes 1 à 6, six types de dégradations (flou, rotation, ombre,
  sous-exposition, JPEG, combinaison) et une calibration isotone. Le seuil de question choisi est de 0,92.
- **Backend** : FastAPI et SQLite, avec un cycle de vie complet des dossiers (8 états et 4 états d'échec), des
  captures idempotentes, une liaison patiente et une synchronisation simulée.
- **Interface** : React et Vite, un coffre chiffré dans le navigateur (IndexedDB et AES-GCM), un contrôle de la
  qualité de la photo sur l'appareil, une interface bilingue français/anglais.
- **Outils** : Claude Code (`claude-opus-5-5`) a servi d'assistant de développement ; Playwright avec Edge pour
  les parcours de bout en bout.

### Défis rencontrés
- Faire dire au modèle quand il doute, sans noyer la sage-femme sous les questions : la calibration a montré
  qu'une confiance brute de 0,92 ne laisse passer aucune erreur sur le développement, au prix de beaucoup de
  questions sur les pages difficiles.
- Le hors ligne réel : une file qui survit à un rechargement immédiat, à une coupure en pleine lecture et à un
  redémarrage du serveur.
- La confidentialité : ne jamais lire ni stocker un nom, une CIN, un téléphone ou une adresse, et ne jamais
  envoyer de données réelles à un tiers.
- Une interface lisible sur téléphone pour une page de 160 champs.

### Réalisations
- **Score officiel sur le jeu de test** (patientes 7 à 10, jamais vues pendant le développement, évaluation
  lancée une seule fois) : **98,92 % de valeurs exactes** et seulement **0,65 % de valeurs fausses sans alerte**
  au seuil de 0,92. Le seuil prudent envoie beaucoup de valeurs justes en question : les champs entièrement exacts
  (valeur et statut) sont à 53,63 %, avec 11,4 questions par page en moyenne (médiane 3,5).
- **Développement** : 100 % de valeurs exactes et 98,84 % de champs entièrement exacts.
- **Application** : les 12 états du cycle de vie sont atteints dans l'application, et les quatre moments de la
  démonstration sont jouables de bout en bout.

### Ce que nous avons appris
Un agent utile n'est pas celui qui ne se trompe jamais, mais celui qui dit quand il doute. La calibration d'une
confiance vaut autant que l'exactitude brute. Et la meilleure interface de saisie est celle qui pose la bonne
question au bon moment.

### La suite
- Héberger un modèle open source dans le système de santé, pour qu'aucune donnée ne sorte du pays.
- Vérifier par section pour réduire le nombre de questions.
- Redresser automatiquement les photos inclinées.
- Mesurer l'extraction sur de vraies photos et sur l'écriture arabe.
- Se connecter à WhatsApp Business.
- Mettre en place une vraie authentification des rôles.

---

## English

### Inspiration
In many health centres, midwives record pregnancy, delivery and postpartum care in a multi-page paper register.
Once written, the information does not follow the woman from one visit to the next and never reaches the health
system. We wanted that register to become a reliable digital record without changing the midwife's practice: paper
stays the reference, the digital layer sits on top of it.

### What it does
- **Reading** : the midwife photographs each page with her phone, even offline. The agent reads it into a
  245-field schema, with an explicit status (known, unknown, not provided, illegible, not applicable, to review)
  and a confidence for every field.
- **Verification** : the agent only asks when it is unsure, one question at a time, WhatsApp-style. It says why
  it doubts and offers four equal answers: Confirm, Correct, Blank on paper, Retake the photo.
- **Offline** : photos are encrypted on the device, queued as "Waiting for AI processing", sent and read when the
  network returns, then synchronised with the health system. No record is lost.
- **Linking** : visits of the same woman are linked through a short code copied onto the register. The app
  proposes possible matches and the midwife decides: [Patient 1] [Patient 2] [None, create] [I don't know].
- **Original image** : it stays linked to the record, with role-based access.
- **Dashboard** : an anonymised dashboard (blood pressure, temperature, HIV, syphilis, hepatitis C) shows the
  epidemiological use; any cell under 5 records is hidden.

### How we built it
- **Extraction** : `claude-sonnet-5` reads each page through tool use, with a schema generated from our field
  definitions. `claude-haiku-4-5` detects unknown page types. Normalisation applies shared conventions and a final
  confidence, which combines plausibility, cross-field consistency and reasoning effort.
- **Evaluation** : ground truth for patients 1–6, six degradations (blur, rotation, shadow, underexposure, JPEG,
  combination) and isotonic calibration. The chosen question threshold is 0.92.
- **Backend** : FastAPI and SQLite, with a full record lifecycle (8 states and 4 failure states), idempotent
  captures, patient linking and simulated synchronisation.
- **Frontend** : React and Vite, an encrypted in-browser vault (IndexedDB and AES-GCM), an on-device photo quality
  check, a bilingual French/English interface.
- **Tools** : Claude Code (`claude-opus-5-5`) was our development assistant; Playwright with Edge ran the
  end-to-end journeys.

### Challenges
- Making the model say when it doubts without drowning the midwife in questions: calibration showed that a raw
  confidence of 0.92 lets no error through on development data, at the cost of many questions on hard pages.
- Real offline behaviour: a queue that survives an immediate reload, a cut during reading and a server restart.
- Privacy: never reading or storing a name, ID number, phone or address, and never sending real data to a third
  party.
- A readable phone interface for a 160-field page.

### Accomplishments
- **Official test score** (patients 7–10, never seen during development, run once): **98.92% exact values** and
  only **0.65% wrong values without an alert** at the 0.92 threshold. The cautious threshold sends many correct
  values to review: fully exact fields (value and status) are 53.63%, with 11.4 questions per page on average
  (median 3.5).
- **Development** : 100 % exact values and 98.84 % fully exact fields.
- **App** : all 12 lifecycle states are reached in the app, and the four demo moments play end to end.

### What we learned
A useful agent is not one that is never wrong but one that says when it is unsure. Calibrating confidence matters
as much as raw accuracy. And the best data-entry interface asks the right question at the right time.

### What's next
- Host an open-source model inside the health system, so no data leaves the country.
- Section-level verification to reduce the number of questions.
- Automatic deskewing of tilted photos.
- Measure extraction on real photos and Arabic handwriting.
- Connect to WhatsApp Business.
- Real role authentication.
