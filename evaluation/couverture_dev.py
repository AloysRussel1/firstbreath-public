"""Publie uniquement les compteurs et les clés encore à annoter du développement."""
import json
from pathlib import Path
from verite_terrain import expected_keys

BASE = Path(__file__).resolve().parent


def write_coverage():
    corpus = json.loads((BASE / 'verite_terrain.json').read_text(encoding='utf-8'))
    annotations = json.loads((BASE / 'annotations_manuelles.json').read_text(encoding='utf-8'))
    manual = {p['page_no']: {f['champ'] for f in p['champs']} for p in annotations['pages'] if p['page_no'] <= 48}
    rows = []
    for p in corpus['pages']:
        if p['page_no'] > 48:
            continue
        expected = set(expected_keys(p['type_page']))
        present = {f['champ'] for f in p['champs']}
        rows.append(dict(page_no=p['page_no'], specimen_no=p['specimen_no'], type_page=p['type_page'],
                         possibles=len(expected), annotes=len(expected & present),
                         annotations_visuelles=len(expected & manual[p['page_no']]),
                         non_annotes=sorted(expected - present)))
    possible, annotated = sum(r['possibles'] for r in rows), sum(r['annotes'] for r in rows)
    report = dict(pages='1-48', champs_possibles=possible, champs_annotes=annotated,
                  champs_non_annotes=possible - annotated, couverture=annotated / possible,
                  annotations_visuelles=sum(r['annotations_visuelles'] for r in rows),
                  validation_humaine_independante=False, pages_detail=rows)
    (BASE / 'couverture_dev.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    lines = ['# Couverture des annotations du développement', '',
             f'Pages 1–48 : **{annotated}/{possible} champs annotés ({annotated / possible:.2%})** ; **{possible - annotated} non annotés**.', '',
             f'{report["annotations_visuelles"]} champs ont une annotation visuelle persistante. Les autres proviennent de la couche texte ou des règles de visite sans objet.', '',
             'La couverture inclut les statuts d’absence explicites : elle ne signifie pas que toutes les valeurs sont renseignées. Une relecture humaine indépendante reste nécessaire ; le corpus demeure A_REVISER.', '',
             '| Type | Possibles | Annotés | Non annotés |', '|---|---:|---:|---:|']
    for kind in sorted({r['type_page'] for r in rows}):
        group = [r for r in rows if r['type_page'] == kind]
        total, done = sum(r['possibles'] for r in group), sum(r['annotes'] for r in group)
        lines.append(f'| {kind} | {total} | {done} | {total - done} |')
    lines += ['', '## Champs restant à annoter', '']
    missing = [(r['page_no'], key) for r in rows for key in r['non_annotes']]
    lines += [f'- Page {n} : `{key}`' for n, key in missing] if missing else ['Aucun champ non annoté sur le développement.']
    (BASE / 'A_ANNOTER_DEV.md').write_text('\n'.join(lines) + '\n', encoding='utf-8')
    return report


if __name__ == '__main__':
    report = write_coverage()
    print(f'Développement : {report["champs_annotes"]}/{report["champs_possibles"]} ; {report["champs_non_annotes"]} non annotés.')
