"""Évalue extract_page sur les champs annotés, sans enregistrer les valeurs prédites."""
import argparse
from collections import Counter, defaultdict
from contextlib import redirect_stdout, redirect_stderr
import csv
import hashlib
import importlib
import io
import json
import math
import os
from pathlib import Path
import sys
import unicodedata
from rapidfuzz.fuzz import ratio as text_ratio

sys.dont_write_bytecode = True
BASE = Path(__file__).resolve().parent
ROOT = BASE.parent
sys.path.insert(0, str(ROOT))
from shared.valider import definition, valider_champ, valider_dossier, verifier_type
from evaluation.verite_terrain import TYPES, expected_keys, load_annotations


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def same_value(key, expected, actual):
    """Types stricts, tolérances numériques et similarité des textes libres."""
    if expected is None or actual is None:
        return expected is actual
    d = definition(key)
    if not verifier_type(d, actual):
        return False
    if d['type'] == 'liste_choix':
        return set(expected) == set(actual) and len(actual) == len(set(actual))
    if d['type'] in {'entier', 'decimal'}:
        tolerance = 10 if key.endswith('_g') else 0.1 if d['type'] == 'decimal' else 0
        return math.isclose(expected, actual, rel_tol=0, abs_tol=tolerance + 1e-12)
    if d['type'] == 'tension':
        return all(abs(int(a) - int(b)) <= 1 for a, b in zip(expected.split('/'), actual.split('/')))
    if d['type'] == 'texte' and key != 'identification.numero_fiche':
        a, b = normalize_text(expected), normalize_text(actual)
        if a == b:
            return True
        negatives = {'non', 'sans', 'pas', 'aucun', 'aucune'}
        if min(len(a), len(b)) < 4 or (set(a.split()) & negatives) != (set(b.split()) & negatives):
            return False
        return text_ratio(a, b) >= 85
    if d['type'] == 'liste_objets' and key == 'obstetrique.accouchements_anterieurs':
        if len(expected) != len(actual):
            return False
        for left, right in zip(expected, actual):
            if not isinstance(right, dict) or set(left) != set(right):
                return False
            for child, value in left.items():
                predicted = right[child]
                if value is None or predicted is None:
                    if value is not predicted:
                        return False
                elif child == 'poids_g':
                    if type(predicted) is not int or abs(value - predicted) > 10:
                        return False
                elif child == 'date':
                    if value != predicted:
                        return False
                elif not isinstance(predicted, str) or normalize_text(value) != normalize_text(predicted):
                    return False
        return True
    return expected == actual


def normalize_text(value):
    value = value.casefold().replace('œ', 'oe').replace('æ', 'ae')
    return ' '.join(''.join(c for c in unicodedata.normalize('NFKD', value)
                           if not unicodedata.combining(c)).split())


def selected_pages(selection, authorize_test=False):
    pages = parse_pages(selection)
    if not authorize_test and any(n > 48 for n in pages):
        raise ValueError('Pages 49–80 réservées : utiliser --autoriser-test après autorisation explicite.')
    return pages


def clean_prediction(prediction):
    """Ne renvoie que des champs valides ; ne journalise jamais le contenu brut."""
    issues = Counter()
    if not isinstance(prediction, dict):
        return None, {}, Counter(sortie_non_objet=1)
    kind = prediction.get('type_page')
    if not isinstance(kind, str) or kind not in TYPES:
        issues['type_page_invalide'] += 1
        kind = None
    fields = prediction.get('champs')
    if not isinstance(fields, list):
        issues['champs_non_liste'] += 1
        return kind, {}, issues
    counts = Counter(f.get('champ') for f in fields if isinstance(f, dict) and isinstance(f.get('champ'), str))
    valid = {}
    for field in fields:
        if not isinstance(field, dict):
            issues['champ_non_objet'] += 1
            continue
        key = field.get('champ')
        if not isinstance(key, str) or definition(key) is None:
            issues['cle_absente_du_schema'] += 1
            continue
        if counts[key] > 1:
            issues['cle_dupliquee'] += 1
            continue
        if not {'champ', 'valeur', 'statut', 'confiance', 'page_source'} <= field.keys():
            issues['champ_incomplet'] += 1
            continue
        confidence = field['confiance']
        if type(confidence) not in (int, float) or not math.isfinite(confidence) or not 0 <= confidence <= 1:
            issues['confiance_invalide'] += 1
            continue
        if type(field['page_source']) is not int or field['page_source'] < 1:
            issues['page_source_invalide'] += 1
            continue
        d = definition(key)
        if d['type'] in {'entier', 'decimal'} and isinstance(field['valeur'], (int, float)) and not math.isfinite(field['valeur']):
            issues['valeur_non_finie'] += 1
            continue
        if field['valeur'] is not None and not verifier_type(d, field['valeur']):
            issues['type_valeur_invalide'] += 1
            continue
        try:
            errors, alerts = valider_champ(field)
        except (TypeError, ValueError, AttributeError):
            issues['champ_invalide'] += 1
            continue
        # Les messages du validateur peuvent contenir des identifiants personnels.
        if errors:
            issues['rejet_validateur'] += 1
            continue
        if kind is None or key not in expected_keys(kind):
            issues['champ_hors_type_predit'] += 1
            continue
        if alerts:
            issues['alerte_plausibilite'] += len(alerts)
        # Exclure les propriétés supplémentaires : elles ne font pas partie du contrat.
        valid[key] = {k: field[k] for k in ('champ', 'valeur', 'statut', 'confiance', 'page_source')}
    return kind, valid, issues


def compare_page(reference, prediction):
    kind, fields, issues = clean_prediction(prediction)
    type_correct = kind == reference['type_page']
    rows = []
    for expected in reference['champs']:
        key = expected['champ']
        actual = fields.get(key)
        present = actual is not None
        equal = present and same_value(key, expected['valeur'], actual['valeur'])
        status_correct = present and actual['statut'] == expected['statut']
        nonempty = expected['valeur'] is not None
        rows.append(dict(page_source=reference['page_no'], specimen_no=reference['specimen_no'],
                         type_page=reference['type_page'], champ=key,
                         present=present, type_page_correct=type_correct,
                         valeur_attendue_renseignee=nonempty,
                         valeur_correcte=bool(equal and type_correct) if nonempty else None,
                         statut_reference=expected['statut'],
                         statut_predit=actual['statut'] if present else None,
                         statut_correct=bool(status_correct and type_correct),
                         exact=bool(equal and status_correct and type_correct),
                         confiance=actual['confiance'] if present else None))
    reference_keys = {f['champ'] for f in reference['champs']}
    expected_type_keys = set(expected_keys(reference['type_page']))
    unannotated = sum(k not in reference_keys and k in expected_type_keys for k in fields)
    other_type = sum(k not in expected_type_keys for k in fields)
    return rows, dict(page_source=reference['page_no'], type_page_reference=reference['type_page'],
                      type_page_predit=kind, type_page_correct=type_correct,
                      sortie_valide=not issues, anomalies=dict(issues),
                      predictions_non_annotees=unannotated, predictions_hors_type_reference=other_type)


def ratio(numerator, denominator):
    return numerator / denominator if denominator else None


def aggregate(rows):
    n = len(rows)
    nonempty = sum(r['valeur_attendue_renseignee'] for r in rows)
    present = sum(r['present'] for r in rows)
    correct_values = sum(r['valeur_correcte'] is True for r in rows)
    correct_statuses = sum(r['statut_correct'] for r in rows)
    exact = sum(r['exact'] for r in rows)
    return dict(n_reference=n, n_valeurs_renseignees=nonempty, n_predits=present,
                n_valeurs_correctes=correct_values, n_statuts_corrects=correct_statuses,
                n_champs_exacts=exact, n_champs_manquants=n - present,
                n_erreurs=n - exact, couverture=ratio(present, n),
                exactitude_valeurs=ratio(correct_values, nonempty),
                exactitude_statuts=ratio(correct_statuses, n),
                exactitude_champs=ratio(exact, n))


def group_scores(rows, key):
    groups = defaultdict(list)
    for row in rows:
        groups[row[key]].append(row)
    return [{key: value, **aggregate(items)} for value, items in sorted(groups.items())]


def parse_pages(value):
    pages = set()
    for part in value.split(','):
        bounds = part.split('-')
        if len(bounds) == 1:
            pages.add(int(bounds[0]))
        elif len(bounds) == 2:
            start, end = map(int, bounds)
            if start > end:
                raise ValueError('Intervalle de pages inversé.')
            pages.update(range(start, end + 1))
        else:
            raise ValueError('Format pages : 1,3-8')
    if not pages or min(pages) < 1 or max(pages) > 80:
        raise ValueError('Pages entre 1 et 80 uniquement.')
    return pages


def load_inputs(truth_path, annotations_path, selected):
    truth = json.loads(truth_path.read_text(encoding='utf-8-sig'))
    pdf = ROOT / 'data/Paper Registry/dossiers_specimen_10_patientes.pdf'
    # Vérifier les empreintes des annotations avant d’appeler le pipeline.
    load_annotations(annotations_path, digest(pdf), max_page=max(selected))
    sources = json.loads(annotations_path.read_text(encoding='utf-8-sig'))
    source_pages = {p['page_no']: p for p in sources['pages']}
    errors, alerts = valider_dossier(truth)
    if errors or alerts:
        raise ValueError('Vérité terrain rejetée par le validateur commun.')
    references = {}
    for page in truth['pages']:
        number = page.get('page_no')
        if type(number) is not int or number in references or not 1 <= number <= 80:
            raise ValueError('Numéro de page invalide ou dupliqué dans la référence.')
        if page['type_page'] != TYPES[(number - 1) % 8] or page.get('specimen_no') != (number - 1) // 8 + 1:
            raise ValueError('Type de page ou spécimen incorrect dans la référence.')
        keys = [f['champ'] for f in page['champs']]
        if len(keys) != len(set(keys)) or any(k not in expected_keys(page['type_page']) for k in keys):
            raise ValueError('Champ de référence dupliqué ou hors du type de page.')
        if any(f['page_source'] != number for f in page['champs']):
            raise ValueError('page_source incohérente dans la référence.')
        references[number] = page
    inputs, dedup = [], 0
    for number in sorted(selected):
        if number not in references or number not in source_pages:
            raise ValueError('Page sélectionnée absente de la référence ou des sources.')
        files = sorted(pdf.parent.glob(f'dossiers_specimen_10_patientes-{number:02d}*.png'))
        hashes = {digest(path) for path in files}
        if hashes != {source_pages[number]['image_sha256']}:
            raise ValueError('Image absente ou doublons différents de la source annotée.')
        dedup += len(files) - 1
        inputs.append((references[number], pdf.parent / source_pages[number]['image_source']))
    return inputs, dedup


def run_evaluation(inputs, extractor, progress=None):
    rows, pages = [], []
    for reference, image in inputs:
        failed = False
        # Le pipeline peut afficher des identifiants ; ses logs ne sont pas conservés.
        with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            try:
                prediction = extractor(str(image))
                page_rows, page_score = compare_page(reference, prediction)
            except Exception:
                failed = True
                page_rows, page_score = compare_page(reference, None)
        if failed:
            page_score['anomalies'] = {'echec_extract_page': 1}
        rows.extend(page_rows)
        pages.append(page_score)
        if progress is not None:
            progress(len(pages), len(inputs), reference['page_no'], failed)
    confusion = Counter((r['statut_reference'], r['statut_predit'] or 'ABSENT') for r in rows)
    by_type = group_scores(rows, 'type_page')
    for item in by_type:
        type_pages = [p for p in pages if p['type_page_reference'] == item['type_page']]
        item.update(n_pages=len(type_pages), n_types_corrects=sum(p['type_page_correct'] for p in type_pages))
        item['exactitude_type_page'] = ratio(item['n_types_corrects'], item['n_pages'])
    anomalies = Counter()
    for page in pages:
        anomalies.update(page['anomalies'])
    scores = dict(global_=aggregate(rows), par_champ=group_scores(rows, 'champ'), par_type_page=by_type,
                  pages=pages, n_pages=len(pages), n_types_corrects=sum(p['type_page_correct'] for p in pages),
                  exactitude_type_page=ratio(sum(p['type_page_correct'] for p in pages), len(pages)),
                  n_sorties_valides=sum(p['sortie_valide'] for p in pages), anomalies=dict(anomalies),
                  confusion_statuts=[dict(reference=a, predit=b, nombre=n) for (a, b), n in sorted(confusion.items())])
    scores['global'] = scores.pop('global_')
    return scores, rows


def write_csv(path, rows):
    if not rows:
        return
    with path.open('w', encoding='utf-8-sig', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def percent(value):
    return '—' if value is None else f'{value:.2%}'


def save_results(output, scores, rows):
    output.mkdir(parents=True, exist_ok=True)
    (output / 'scores.json').write_text(json.dumps(scores, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    write_csv(output / 'scores_champs.csv', scores['par_champ'])
    write_csv(output / 'scores_types_page.csv', scores['par_type_page'])
    write_csv(output / 'confusion_statuts.csv', scores['confusion_statuts'])
    (output / 'comparaisons.jsonl').write_text(''.join(json.dumps(row, ensure_ascii=False) + '\n' for row in rows), encoding='utf-8')
    g = scores['global']
    lines = ['# Évaluation de l’extraction', '',
             f'Étiquette : **{scores["provenance"]["etiquette"]}**. Ces scores décrivent ce pipeline et ce corpus partiel.', '',
             f'{scores["n_pages"]} pages, {g["n_reference"]} champs annotés ; {scores["provenance"]["doublons_ignores"]} images en double ignorées.', '',
             f'Couverture des annotations : {g["n_reference"]}/{scores["provenance"]["champs_possibles_schema"]} ({percent(scores["provenance"]["couverture_annotations"])}). {scores["provenance"]["champs_annotations_en_attente"]} champs restent exclus des scores.', '',
             f'Sorties sans anomalie : {scores["n_sorties_valides"]}/{scores["n_pages"]}.', '',
             f'Types de page : {scores["n_types_corrects"]}/{scores["n_pages"]} ({percent(scores["exactitude_type_page"])}).',
             f'Champs présents : {g["n_predits"]}/{g["n_reference"]} ({percent(g["couverture"])}).',
             f'Valeurs correctes selon les tolérances : {g["n_valeurs_correctes"]}/{g["n_valeurs_renseignees"]} ({percent(g["exactitude_valeurs"])}).',
             f'Statuts exacts : {g["n_statuts_corrects"]}/{g["n_reference"]} ({percent(g["exactitude_statuts"])}).',
             f'Champs entièrement exacts : {g["n_champs_exacts"]}/{g["n_reference"]} ({percent(g["exactitude_champs"])}).', '',
             'Les scores exigent le bon type de page. Les valeurs ne sont évaluées que quand la référence est renseignée. Les champs absents/invalides comptent comme erreurs ; les annotations en attente sont exclues. Les champs entièrement exacts exigent le statut exact et une valeur conforme aux tolérances fixées avant le lancement : décimaux 0,1 ; poids 10 g ; tension 1 mmHg ; autres entiers exacts ; RapidFuzz 85/100 pour les textes libres. Accents, ligatures et casse sont normalisés.', '',
             '| Type de page | Champs | Couverture | Valeurs | Statuts | Champs exacts |',
             '|---|---:|---:|---:|---:|---:|']
    for item in scores['par_type_page']:
        lines.append(f'| {item["type_page"]} | {item["n_reference"]} | {percent(item["couverture"])} | {percent(item["exactitude_valeurs"])} | {percent(item["exactitude_statuts"])} | {percent(item["exactitude_champs"])} |')
    lines += ['', '## Champs avec le plus d’erreurs', '', '| Champ | Erreurs | Références | Manquants |', '|---|---:|---:|---:|']
    worst = sorted(scores['par_champ'], key=lambda s: (-s['n_erreurs'], s['champ']))[:20]
    for item in worst:
        lines.append(f'| `{item["champ"]}` | {item["n_erreurs"]} | {item["n_reference"]} | {item["n_champs_manquants"]} |')
    lines += ['', 'Les rapports de scores n’enregistrent pas les valeurs prédites ni les logs bruts. Les diagnostics sont des catégories et compteurs. Le cache du client contient la lecture intermédiaire et reste local dans evaluation/cache/, ignoré par Git.']
    (output / 'rapport.md').write_text('\n'.join(lines) + '\n', encoding='utf-8')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--pages', default='1-48', help='Développement : 1–48. Exemple : 1,3-8')
    parser.add_argument('--autoriser-test', action='store_true', help='Réservé au gel du modèle, sur autorisation explicite.')
    parser.add_argument('--sortie', type=Path, default=BASE / 'resultats')
    parser.add_argument('--etiquette', default='pipeline courant')
    args = parser.parse_args()
    try:
        selected = selected_pages(args.pages, args.autoriser_test)
    except ValueError as exc:
        parser.error(str(exc))
    output = args.sortie.resolve()
    if not output.is_relative_to(BASE) or output == BASE:
        parser.error('--sortie doit être un sous-dossier de evaluation/.')
    try:
        truth_path, annotations_path = BASE / 'verite_terrain.json', BASE / 'annotations_manuelles.json'
        inputs, duplicates = load_inputs(truth_path, annotations_path, selected)
        from dotenv import load_dotenv
        load_dotenv(BASE / '.env')
        # Import direct de l’interface commune ; aucun fichier extraction/ modifié.
        with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            pipeline = importlib.import_module('extraction.pipeline')
        client = importlib.import_module('extraction.client')
        if client.FOURNISSEUR == 'anthropic' and not os.getenv('ANTHROPIC_API_KEY'):
            parser.exit(1, 'Clé Anthropic absente : renseigner evaluation/.env ou le .env racine.\n')
        client.CACHE = BASE / 'cache'
        client.CACHE.mkdir(parents=True, exist_ok=True)
        def progress(done, total, number, failed):
            print(f'{done}/{total} : page {number}, ' + ('appel en échec' if failed else 'comparée'), flush=True)
        scores, rows = run_evaluation(inputs, pipeline.extract_page, progress=progress)
        scores['provenance'] = dict(etiquette=args.etiquette, pages=sorted(selected),
                                    pipeline='extraction.pipeline.extract_page',
                                    autoriser_test=args.autoriser_test, fournisseur=client.FOURNISSEUR,
                                    modele=client.MODELE_DEFAUT,
                                    comparaison=dict(texte_seuil=85, decimal_tolerance=0.1,
                                                     poids_g_tolerance=10, tension_tolerance=1,
                                                     autres_entiers_tolerance=0),
                                    client_sha256=digest(ROOT / 'extraction/client.py'),
                                    normalisation_sha256=digest(ROOT / 'extraction/normalisation.py'),
                                    pipeline_sha256=digest(ROOT / 'extraction/pipeline.py'),
                                    reference_sha256=digest(truth_path), annotations_sha256=digest(annotations_path),
                                    doublons_ignores=duplicates)
        possible = sum(len(expected_keys(page['type_page'])) for page, _ in inputs)
        scores['provenance']['champs_possibles_schema'] = possible
        scores['provenance']['champs_annotations_en_attente'] = possible - len(rows)
        scores['provenance']['couverture_annotations'] = ratio(len(rows), possible)
        save_results(output, scores, rows)
    except Exception:
        # Éviter d’afficher des messages tiers susceptibles de contenir des valeurs.
        parser.exit(1, 'Évaluation interrompue : vérifier référence, annotations, images et import du pipeline. Aucun log brut affiché.\n')
    g = scores['global']
    print(f'{scores["n_pages"]} pages ; {g["n_reference"]} champs ; exactitude champs {percent(g["exactitude_champs"])} ; statuts {percent(g["exactitude_statuts"])}.')
    print(f'Rapport : {output / "rapport.md"}')
    if any(not page['sortie_valide'] for page in scores['pages']):
        print('Sorties invalides ou appels en échec : consulter les compteurs du rapport JSON.')
        return 2
    return 0


if __name__ == '__main__':
    sys.exit(main())
