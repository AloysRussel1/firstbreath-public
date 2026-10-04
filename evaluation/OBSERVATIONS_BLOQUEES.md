# Observations auparavant bloquées

Le validateur commun accepte maintenant les champs `vaccins_du_jour` et `nouveau_ne.anomalie` : les faux positifs ont été corrigés. Les lectures des pages 1–48 sont intégrées à la vérité terrain. Les observations historiques des pages 49–80 sont conservées sans nouvelle lecture ni évaluation du jeu réservé.

Lorsqu'une consultation a eu lieu, aucune case de vaccin cochée signifie `CONNU []`, conformément à la section 7 des conventions. Les anciennes lectures ci-dessous sont réécrites avec les accents corrects en UTF-8 ; les lignes du jeu réservé sont indiquées comme historiques. La complication de la page 69 reste à clarifier, sans intervenir sur le développement.

| Page | Champ | Lecture | Image source | SHA-256 |
|---|---|---|---|---|
| 6 | `pp_precoce.nouveau_ne.vaccins_du_jour` | BCG et HB cochés | dossiers_specimen_10_patientes-06.png | e43cbfec65aacbbfa7d2bf5f5f3f2264042d8b5327c5f090aa771dd1141bba54 |
| 8 | `pp_tardif.nouveau_ne.vaccins_du_jour` | Aucune case cochée : CONNU, valeur [] | dossiers_specimen_10_patientes-08.png | 4b2cb2278bed946f3568b4c0412db11b3553d2fdd874169199ba4a3f5b3a7c7a |
| 14 | `pp_precoce.nouveau_ne.vaccins_du_jour` | BCG et HB cochés | dossiers_specimen_10_patientes-14__1NRsJ9Ddo8.png | dbb7fd0f83862cf8c790241b8cb17cb0502cb841d8ff74d26fa6f10f8484be4d |
| 16 | `pp_tardif.nouveau_ne.vaccins_du_jour` | Aucune case cochée : CONNU, valeur [] | dossiers_specimen_10_patientes-16__1CB60L7TiS.png | 853c1f7f087692f6ed0bbcabab1dd34cb92183b4396afd4a12b11741e36f2a11 |
| 22 | `pp_precoce.nouveau_ne.vaccins_du_jour` | BCG et HB cochés | dossiers_specimen_10_patientes-22.png | 138939d7684b547ed8c4d23c8c1297602ae6c9bdd880ffd6e50ffc96037d4394 |
| 24 | `pp_tardif.nouveau_ne.vaccins_du_jour` | Aucune case cochée : CONNU, valeur [] | dossiers_specimen_10_patientes-24__11w0IP6pSn.png | b4aba6bea2cd4986395a1b2a41f3f3fe4f46b49f1e196b2e4100f585fd81d44b |
| 30 | `pp_precoce.nouveau_ne.vaccins_du_jour` | BCG et HB cochés | dossiers_specimen_10_patientes-30__1kKkGMBMD5.png | 065e2111d89a6998c064cb8e5180034efe5eac6203b0a0c7cb29bfdd7789b77f |
| 32 | `pp_tardif.nouveau_ne.vaccins_du_jour` | Aucune case cochée : CONNU, valeur [] | dossiers_specimen_10_patientes-32__1Bx-67ocGy.png | 940ad93e464178311da23d18804023c012d2eb3b301ab77f9ddbd41eda6407c3 |
| 38 | `pp_precoce.nouveau_ne.vaccins_du_jour` | BCG et HB cochés | dossiers_specimen_10_patientes-38__1CXcCUFyrj.png | 2fb813c119e90504357ba7bf6338cd891f2eb53b6e9b1f78917b12caab5c0a6f |
| 40 | `pp_tardif.nouveau_ne.vaccins_du_jour` | Aucune case cochée : CONNU, valeur [] | dossiers_specimen_10_patientes-40__1s1Z5scO-G.png | dcc4ebf1c1c166b497859f55bc77918bde5a8a6367df901a82f89176c77a60e2 |
| 46 | `pp_precoce.nouveau_ne.vaccins_du_jour` | BCG et HB cochés | dossiers_specimen_10_patientes-46__13tFG11aaA.png | 50ff16998e1c6ef7392f3b1b3a993f57a64a499d40e657ee2d7016178dff5d2a |
| 48 | `pp_tardif.nouveau_ne.vaccins_du_jour` | Aucune case cochée : CONNU, valeur [] | dossiers_specimen_10_patientes-48__1JY9DkRr_Z.png | 1486749fc689d774b86d67b5408cc2d79871b6e515ebe9b864bb46acb3573421 |
| 54 | `pp_precoce.nouveau_ne.vaccins_du_jour` | BCG et HB cochés (observation historique, jeu réservé) | dossiers_specimen_10_patientes-54__155-coOlhB.png | 1857c36da7dad67cdedcdb7fd4c36991abbf9bc5634cbbbb106ab20595829e04 |
| 56 | `pp_tardif.nouveau_ne.vaccins_du_jour` | Aucune case cochée : NON_FOURNI, valeur null (observation historique, jeu réservé) | dossiers_specimen_10_patientes-56__14R5jqMZgt.png | 8035acac8f8a46ebba2031884dfe6bb2cb5fe0631b4a58027c3c7a2f9e07d3ae |
| 62 | `pp_precoce.nouveau_ne.vaccins_du_jour` | BCG et HB cochés (observation historique, jeu réservé) | dossiers_specimen_10_patientes-62.png | 99562ed7a6228e3f953869e7d16fa9df6532ee6c192cc5e4835696e9ca064505 |
| 64 | `pp_tardif.nouveau_ne.vaccins_du_jour` | Aucune case cochée : NON_FOURNI, valeur null (observation historique, jeu réservé) | dossiers_specimen_10_patientes-64.png | 3b1ac2c9e972c7284c18dc55cd8782f80e65ce5590ea3363125f059aa33904fc |
| 70 | `pp_precoce.nouveau_ne.vaccins_du_jour` | BCG et HB cochés (observation historique, jeu réservé) | dossiers_specimen_10_patientes-70.png | 42bfe62e7eda705e768d6bc94918669e232e2bd410b5014df2a0ace1eb32fc62 |
| 72 | `pp_tardif.nouveau_ne.vaccins_du_jour` | Aucune case cochée : NON_FOURNI, valeur null (observation historique, jeu réservé) | dossiers_specimen_10_patientes-72.png | 6441e5d61a90f5db3180585a43c2bbcda94bad318c48aa4aa6ac094811efa94d |
| 78 | `pp_precoce.nouveau_ne.vaccins_du_jour` | BCG et HB cochés (observation historique, jeu réservé) | dossiers_specimen_10_patientes-78.png | 0cbdde6d8878748493e3001a42cb416f1f1d298077759411ed6d4dd640777968 |
| 80 | `pp_tardif.nouveau_ne.vaccins_du_jour` | Aucune case cochée : NON_FOURNI, valeur null (observation historique, jeu réservé) | dossiers_specimen_10_patientes-80.png | 62d034d1793a3169e4a859a31ad97b08c8fa45fdebd196895505e30ec4c143d8 |
