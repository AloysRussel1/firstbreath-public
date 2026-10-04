"""Alignement reproductible du développement ; aucune lecture des pages de test."""
import json
from pathlib import Path
import pymupdf

from verite_terrain import ROOT, SCHEMA, valider_dossier, expected_keys, write_pending

BASE = Path(__file__).resolve().parent
BOOLEAN_KEYS = {'identification.grossesse_a_risque', 'profil.consanguinite',
                'vaccination.hepatite_b', 'accouchement.episiotomie',
                'pp_precoce.nouveau_ne.transfert', 'pp_tardif.nouveau_ne.transfert'}
NOT_APPLICABLE = {'identification.types_risque', 'accouchement.complications',
                  'pp_precoce.mere.complications', 'pp_tardif.mere.complications'}
VISUAL = {
    (10, 'profil.niveau_instruction'): 'Aucun',
    (18, 'profil.niveau_instruction'): 'Collège',
    (26, 'profil.niveau_instruction'): 'Aucun',
    (12, 'accouchement.indication_cesarienne'): 'Souffrance foetale',
    (28, 'accouchement.indication_cesarienne'): 'Utérus cicatriciel',
    (10, 'antecedents.familiaux.maladies_hereditaires'): 'femme : oncle ; mari : RAS',
}


def empty_columns(page):
    edges = []
    for drawing in page.get_drawings():
        for item in drawing['items']:
            if item[0] == 'l':
                a, b = item[1:3]
                if abs(a.x - b.x) < 15 and min(a.y, b.y) < 150 and max(a.y, b.y) > 700:
                    edges.append(round((a.x + b.x) / 2, 1))
    edges = sorted(set(edges))
    if len(edges) != 11:
        raise ValueError('Limites du tableau des visites ambiguës.')
    spans = [s for b in page.get_text('dict')['blocks'] for l in b.get('lines', [])
             for s in l['spans'] if 140 < s['bbox'][1] < 740 and s['text'].strip()]
    # Une lettre italique peut déborder légèrement à gauche de sa propre cellule.
    # Utiliser un point intérieur du glyphe évite de remplir la colonne voisine vide.
    return [i for i in range(9) if not any(
        edges[i + 1] <= s['bbox'][0] + min(3, (s['bbox'][2] - s['bbox'][0]) / 2) < edges[i + 2]
        for s in spans)]


def align_fields(page):
    if page['page_no'] > 48:
        return
    for f in page['champs']:
        key, value = f['champ'], f['valeur']
        if key in BOOLEAN_KEYS and value is None and f['statut'] == 'NON_FOURNI':
            f.update(valeur=False, statut='CONNU')
        elif key in NOT_APPLICABLE and (value is None or value == []) and f['statut'] in {'NON_FOURNI', 'CONNU'}:
            f.update(valeur=None, statut='NON_APPLICABLE')
        elif key.startswith('antecedents.familiaux.') and isinstance(value, str) and value.startswith('Famille de la femme : '):
            f['valeur'] = 'femme : ' + value.removeprefix('Famille de la femme : ').replace('; mari/famille : ', ' ; mari : ')
        if (page['page_no'], key) in VISUAL:
            f.update(valeur=VISUAL[page['page_no'], key], statut='CONNU')


def align_corpus(corpus, annotations):
    for p in annotations['pages']:
        align_fields(p)
    columns = {}
    with pymupdf.open(ROOT / 'data/Paper Registry/dossiers_specimen_10_patientes.pdf') as pdf:
        for p in corpus['pages']:
            if p['page_no'] > 48:
                continue
            align_fields(p)
            fields = {f['champ']: f for f in p['champs']}
            for (number, key), value in VISUAL.items():
                if number == p['page_no']:
                    fields[key] = dict(champ=key, valeur=value, statut='CONNU', confiance=1.0, page_source=number)
                    ap = next(a for a in annotations['pages'] if a['page_no'] == number)
                    if not any(f['champ'] == key for f in ap['champs']):
                        ap['champs'].append(dict(fields[key]))
            if p['type_page'] == 'GROSSESSE_ACTUELLE':
                slots = empty_columns(pdf[p['page_no'] - 1]); columns[str(p['page_no'])] = slots
                for slot in slots:
                    prefix = f'grossesse.visites[{slot}].'
                    if any(f['valeur'] is not None for k, f in fields.items() if k.startswith(prefix)):
                        raise ValueError('Une colonne vide contredit une annotation renseignée.')
                    for d in SCHEMA['pages'][p['type_page']]['visites']['champs']:
                        key = prefix + d['cle']
                        fields[key] = dict(champ=key, valeur=None, statut='NON_APPLICABLE', confiance=1.0, page_source=p['page_no'])
            if p['page_no'] % 8 in (6, 0):
                prefix = ('pp_precoce' if p['page_no'] % 8 == 6 else 'pp_tardif') + '.nouveau_ne.'
                if fields.get(prefix + 'date_consultation', {}).get('valeur'):
                    key = prefix + 'signes_danger'
                    if key not in fields:
                        fields[key] = dict(champ=key, valeur=[], statut='CONNU', confiance=1.0, page_source=p['page_no'])
            p['champs'] = list(fields.values())
    return columns


def main():
    paths = [BASE / name for name in ('verite_terrain.json', 'annotations_manuelles.json', 'rapport_verite_terrain.json')]
    corpus, annotations, report = [json.loads(p.read_text(encoding='utf-8')) for p in paths]
    held_out = json.dumps(corpus['pages'][48:], sort_keys=True)
    report['visites_vides_non_applicables_dev'] = align_corpus(corpus, annotations)
    assert json.dumps(corpus['pages'][48:], sort_keys=True) == held_out
    errors, alerts = valider_dossier(corpus)
    if errors or alerts:
        raise ValueError('Référence invalide après alignement.')
    available = {(p['page_no'], f['champ']) for p in corpus['pages'] for f in p['champs']}
    report['a_verifier'] = [x for x in report['a_verifier'] if (x['page_source'], x['champ']) not in available]
    report.update(champs_extraits=len(available), champs_a_verifier=len(report['a_verifier']),
                  champs_annotes=sum(len(p['champs']) for p in annotations['pages']))
    for path, value in zip(paths, [corpus, annotations, report]):
        path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    write_pending(BASE / 'A_ANNOTER.md', report['a_verifier'])
    count = sum(len(p['champs']) for p in corpus['pages'] if p['page_no'] <= 48)
    print(f'VALIDE : développement {count}/1470 champs ; pages 49–80 inchangées.')


if __name__ == '__main__':
    main()
