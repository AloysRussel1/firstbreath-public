"""Compare les six dégradations du développement à leurs références d'origine."""
import argparse
from concurrent.futures import ProcessPoolExecutor, as_completed
import importlib
import json
import os
from pathlib import Path
import sys
sys.dont_write_bytecode = True

from evaluer import BASE, ROOT, digest, load_inputs, run_evaluation, save_results, percent, selected_pages
from verite_terrain import expected_keys

VARIANTS = ['flou', 'rotation', 'ombre', 'sombre', 'jpeg', 'combinaison']


def generate():
    supplied = ROOT / 'extraction/degradees/index_degradees.json'
    if supplied.exists():
        entries = json.loads(supplied.read_text(encoding='utf-8'))['images']
        if all((ROOT / i['fichier']).is_file() for i in entries):
            return supplied
    output = BASE / 'degradees'
    output.mkdir(exist_ok=True)
    local = output / 'index_degradees.json'
    if local.exists():
        entries = json.loads(local.read_text(encoding='utf-8'))['images']
        if len(entries) == 288 and all((ROOT / i['fichier']).is_file() for i in entries):
            return local
    # Appeler le script livré, sans modifier sa source ni écrire dans extraction/.
    sys.path.insert(0, str(ROOT))
    generator = importlib.import_module('extraction.degrader')
    generator.SORTIE = output
    generator.main()
    return local


def validate_index(index_path, inputs):
    references = {p['page_no']: p for p, _ in inputs}
    annotations = json.loads((BASE / 'annotations_manuelles.json').read_text(encoding='utf-8'))
    sources = {p['page_no']: p for p in annotations['pages'] if p['page_no'] <= 48}
    data = json.loads(index_path.read_text(encoding='utf-8'))
    seen, entries = set(), []
    for entry in data['images']:
        number, variant = entry['page_pdf'], entry['degradation']
        if type(number) is not int or not 1 <= number <= 48 or entry['split'] != 'dev':
            raise ValueError('Image hors développement : refus.')
        if variant not in VARIANTS or (number, variant) in seen:
            raise ValueError('Dégradation inconnue ou dupliquée.')
        seen.add((number, variant))
        if number not in references:
            continue
        if entry['type_page'] != references[number]['type_page'] or entry['patiente'] != (number - 1) // 8 + 1:
            raise ValueError('Type ou patiente incompatibles avec la référence.')
        source = (ROOT / entry['fichier_origine']).resolve()
        image = (ROOT / entry['fichier']).resolve()
        if not source.is_relative_to(ROOT / 'data/Paper Registry'):
            raise ValueError('Source hors du spécimen autorisé.')
        if not (image.is_relative_to(BASE / 'degradees') or image.is_relative_to(ROOT / 'extraction/degradees')):
            raise ValueError('Image dégradée hors des dossiers prévus.')
        if digest(source) != entry['sha256_origine'] or entry['sha256_origine'] != sources[number]['image_sha256']:
            raise ValueError('Empreinte de la page originale incompatible.')
        if digest(image) != entry['sha256']:
            raise ValueError('Image dégradée modifiée depuis sa génération.')
        entries.append(entry)
    expected = {(n, v) for n in references for v in VARIANTS}
    if not expected <= seen:
        raise ValueError('Index incomplet pour les pages sélectionnées.')
    return entries


def evaluate_variant(variant, entries, selected, directory):
    from dotenv import load_dotenv
    load_dotenv(BASE / '.env')
    inputs, duplicates = load_inputs(BASE / 'verite_terrain.json', BASE / 'annotations_manuelles.json', set(selected))
    pipeline = importlib.import_module('extraction.pipeline')
    client = importlib.import_module('extraction.client')
    if client.FOURNISSEUR == 'anthropic' and not os.getenv('ANTHROPIC_API_KEY'):
        raise ValueError('Clé Anthropic absente.')
    client.CACHE = BASE / 'cache'
    client.CACHE.mkdir(exist_ok=True)
    # Même index de types que la livraison, pour les images générées dans evaluation/.
    original_index = json.loads((ROOT / 'extraction/index.json').read_text(encoding='utf-8'))
    pipeline._index = {p['sha256']: p['type_page'] for p in original_index['pages']}
    pipeline._index.update({e['sha256']: e['type_page'] for e in entries})
    if variant != 'propre':
        images = {e['page_pdf']: ROOT / e['fichier'] for e in entries if e['degradation'] == variant}
        inputs = [(reference, images[reference['page_no']]) for reference, _ in inputs]
    def progress(done, total, number, failed):
        print(f'{variant} {done}/{total} : page {number}, ' + ('échec' if failed else 'comparée'), flush=True)
    scores, rows = run_evaluation(inputs, pipeline.extract_page, progress=progress)
    possible = sum(len(expected_keys(reference['type_page'])) for reference, _ in inputs)
    scores['provenance'] = dict(etiquette=f'ia-dev-{variant}', variante=variant, pages=list(selected),
                                fournisseur=client.FOURNISSEUR, modele=client.MODELE_DEFAUT,
                                pipeline='extraction.pipeline.extract_page',
                                pipeline_sha256=digest(ROOT / 'extraction/pipeline.py'),
                                client_sha256=digest(ROOT / 'extraction/client.py'),
                                normalisation_sha256=digest(ROOT / 'extraction/normalisation.py'),
                                reference_sha256=digest(BASE / 'verite_terrain.json'),
                                annotations_sha256=digest(BASE / 'annotations_manuelles.json'),
                                generateur_sha256=digest(ROOT / 'extraction/degrader.py'),
                                doublons_ignores=duplicates if variant == 'propre' else 0,
                                champs_possibles_schema=possible, champs_annotations_en_attente=possible - len(rows),
                                couverture_annotations=len(rows) / possible if possible else 0,
                                comparaison=dict(texte_seuil=85, decimal_tolerance=0.1,
                                                 poids_g_tolerance=10, tension_tolerance=1,
                                                 autres_entiers_tolerance=0))
    save_results(Path(directory) / variant, scores, rows)
    return scores


def summarize(directory, selected):
    scores = {v: json.loads((directory / v / 'scores.json').read_text(encoding='utf-8'))
              for v in ['propre'] + VARIANTS}
    baseline = scores['propre']['global']
    rows = []
    for variant, result in scores.items():
        g = result['global']
        rows.append(dict(variante=variant, pages=result['n_pages'], sorties_valides=result['n_sorties_valides'],
                         couverture=g['couverture'], valeurs=g['exactitude_valeurs'],
                         statuts=g['exactitude_statuts'], champs_exacts=g['exactitude_champs'],
                         ecart_champs_points=100 * (g['exactitude_champs'] - baseline['exactitude_champs']),
                         anomalies=result['anomalies']))
    report = dict(pages=list(selected), reference_sha256=digest(BASE / 'verite_terrain.json'), resultats=rows)
    (directory / 'comparaison_degradations.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    lines = ['# Robustesse aux dégradations — développement', '',
             'Même vérité terrain de la page originale pour chaque variante ; comparaison au modèle de référence, pas seulement accord entre deux prédictions.', '',
             '| Variante | Pages | Sorties valides | Valeurs | Statuts | Champs exacts | Écart / propre (points) |',
             '|---|---:|---:|---:|---:|---:|---:|']
    for r in rows:
        lines.append(f'| {r["variante"]} | {r["pages"]} | {r["sorties_valides"]} | {percent(r["valeurs"])} | {percent(r["statuts"])} | {percent(r["champs_exacts"])} | {r["ecart_champs_points"]:+.2f} |')
    lines += ['', 'Scores avec les tolérances fixées à l’étape 3. Les appels échoués et champs absents restent dans le dénominateur. Jeu synthétique, types de page connus par index ; aucune page 49–80.']
    (directory / 'comparaison_degradations.md').write_text('\n'.join(lines) + '\n', encoding='utf-8')
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--generer-seulement', action='store_true')
    parser.add_argument('--pages', default='1-48')
    parser.add_argument('--jobs', type=int, default=3, choices=range(1, 7))
    parser.add_argument('--sortie', type=Path, default=BASE / 'resultats_degradations_dev')
    args = parser.parse_args()
    try:
        selected = sorted(selected_pages(args.pages))
    except ValueError as error:
        parser.error(str(error))
    directory = args.sortie.resolve()
    if not directory.is_relative_to(BASE) or directory == BASE:
        parser.error('--sortie doit rester dans un sous-dossier de evaluation/.')
    inputs, _ = load_inputs(BASE / 'verite_terrain.json', BASE / 'annotations_manuelles.json', set(selected))
    index = generate()
    entries = validate_index(index, inputs)
    print(f'Index validé : {len(entries)} images dégradées pour {len(selected)} pages dev.', flush=True)
    if args.generer_seulement:
        return
    directory.mkdir(parents=True, exist_ok=True)
    evaluate_variant('propre', entries, selected, str(directory))
    with ProcessPoolExecutor(max_workers=args.jobs) as pool:
        futures = {pool.submit(evaluate_variant, v, entries, selected, str(directory)): v for v in VARIANTS}
        for future in as_completed(futures):
            scores = future.result()
            print(f'TERMINÉ {futures[future]} : champs exacts {percent(scores["global"]["exactitude_champs"])}', flush=True)
    report = summarize(directory, selected)
    print(f'Bilan : {directory / "comparaison_degradations.md"}')
    return 2 if any(r['sorties_valides'] != r['pages'] for r in report['resultats']) else 0


if __name__ == '__main__':
    raise SystemExit(main())
