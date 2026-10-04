"""Interface locale de relecture des cases du développement et import validé."""
import argparse
import json
from pathlib import Path
from PIL import Image
from verite_terrain import ROOT, SCHEMA, expected_keys, load_annotations, valider_page
from evaluer import digest

BASE = Path(__file__).resolve().parent
# Zones de cases, hors identifiants directs et personnel, adaptées au spécimen.
REGIONS = {
    1: [(110, 560, 1430, 390), (110, 1190, 1430, 430)],
    2: [(110, 465, 1430, 70), (90, 1990, 1430, 220)],
    3: [(850, 175, 690, 100)],
    4: [(540, 310, 970, 450), (540, 900, 970, 410), (530, 1340, 980, 470), (540, 1840, 970, 120)],
    5: [(100, 405, 1430, 90), (100, 1090, 1430, 210), (100, 1390, 1430, 210), (100, 1640, 1430, 410)],
    6: [(100, 440, 1430, 330), (100, 1150, 1430, 190), (100, 1840, 1430, 90)],
    7: [(100, 405, 1430, 90), (100, 1090, 1430, 210), (100, 1390, 1430, 210), (100, 1640, 1430, 410)],
    8: [(100, 440, 1430, 330), (100, 1150, 1430, 190), (100, 1840, 1430, 90)],
}


def merge_corrections(data, corrections):
    changes = corrections.get('corrections')
    if not isinstance(changes, list):
        raise ValueError('Une liste corrections est requise.')
    seen = set()
    for item in changes:
        number, key = item['page_no'], item['champ']
        if type(number) is not int or not 1 <= number <= 48 or (number, key) in seen:
            raise ValueError('Page hors développement ou correction dupliquée.')
        seen.add((number, key))
        page = next(p for p in data['pages'] if p['page_no'] == number)
        if key not in expected_keys(page['type_page']):
            raise ValueError('Clé hors du type de page.')
        field = dict(champ=key, valeur=item['valeur'], statut=item['statut'], confiance=1.0, page_source=number)
        errors, alerts = valider_page(dict(type_page=page['type_page'], champs=[field]))
        if errors or alerts:
            raise ValueError('Correction invalide : vérifier format, statut et plausibilité.')
        page['champs'] = [f for f in page['champs'] if f['champ'] != key] + [field]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--importer', type=Path)
    args = parser.parse_args()
    path = BASE / 'annotations_manuelles.json'
    data = json.loads(path.read_text(encoding='utf-8'))
    load_annotations(path, digest(ROOT / 'data/Paper Registry/dossiers_specimen_10_patientes.pdf'))
    if args.importer:
        merge_corrections(data, json.loads(args.importer.read_text(encoding='utf-8-sig')))
        # Le chargeur applique aussi les vérifications strictes et les empreintes.
        candidate = BASE / 'apercus' / 'annotations_candidate.json'
        candidate.parent.mkdir(exist_ok=True)
        candidate.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
        load_annotations(candidate, data['source_sha256'])
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        print('Corrections importées ; régénérer ensuite verite_terrain.py.')
        return
    output = BASE / 'apercus' / 'revision_dev'
    output.mkdir(parents=True, exist_ok=True)
    corpus = json.loads((BASE / 'verite_terrain.json').read_text(encoding='utf-8'))
    pages = []
    for p in corpus['pages']:
        number = p['page_no']
        if number > 48:
            continue
        source = next(a for a in data['pages'] if a['page_no'] == number)
        regions = REGIONS[(number - 1) % 8 + 1]
        sheet = Image.new('RGB', (1000, sum(int(h * 1000 / w) for _, _, w, h in regions)), 'white')
        offset = 0
        with Image.open(ROOT / 'data/Paper Registry' / source['image_source']) as image:
            for x, y, w, h in regions:
                crop = image.crop((x, y, x + w, y + h)).resize((1000, int(h * 1000 / w)))
                sheet.paste(crop, (0, offset)); offset += crop.height
        sheet.save(output / f'page_{number:02d}.png')
        definitions = SCHEMA['pages'][p['type_page']]['champs']
        values = {f['champ']: f for f in p['champs']}
        fields = [dict(champ=d['cle'], type=d['type'], choix=d.get('choix', []),
                       reference=values.get(d['cle'])) for d in definitions
                  if d['type'] in {'booleen', 'choix', 'liste_choix'}]
        pages.append(dict(page_no=number, champs=fields))
    payload = json.dumps(pages, ensure_ascii=False).replace('<', '\\u003c')
    template = (BASE / 'revision_cases.html').read_text(encoding='utf-8')
    (output / 'index.html').write_text(template.replace('__DONNEES__', payload), encoding='utf-8')
    print(f'Interface locale : {output / "index.html"}')


if __name__ == '__main__':
    main()
