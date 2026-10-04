"""Calibration du développement, sans appel API et sans accès aux pages de test."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import sys
sys.dont_write_bytecode = True
os.environ['MPLCONFIGDIR'] = str(Path(__file__).resolve().parent / 'apercus/matplotlib')

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
import sklearn
from sklearn.isotonic import IsotonicRegression
from sklearn.linear_model import LogisticRegression

from evaluer import BASE, compare_page

VARIANTS = ['propre', 'flou', 'rotation', 'ombre', 'sombre', 'jpeg', 'combinaison']
MANDATORY = {'A_REVISER', 'ILLISIBLE', 'INCONNU'}


def fingerprint(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_rows(results, details, allow_comparisons=False):
    truth_path = BASE / 'verite_terrain.json'
    truth = json.loads(truth_path.read_text(encoding='utf-8'))
    references = {p['page_no']: p for p in truth['pages'] if p['page_no'] <= 48}
    rows, sources, detail_count, signal_count = [], [], 0, 0
    signature = None
    for variant in VARIANTS:
        scores_path = results / variant / 'scores.json'
        scores = json.loads(scores_path.read_text(encoding='utf-8'))
        current_signature = {k: scores['provenance'][k] for k in ['modele', 'fournisseur', 'pipeline_sha256', 'client_sha256', 'normalisation_sha256']}
        if signature is not None and current_signature != signature:
            raise ValueError('Modèles ou pipelines différents entre les variantes.')
        signature = current_signature
        if scores['provenance']['pages'] != list(range(1, 49)) or scores['provenance']['reference_sha256'] != fingerprint(truth_path):
            raise ValueError('Résultats incomplets ou référence modifiée : relancer le dev.')
        comparisons = results / variant / 'comparaisons.jsonl'
        recorded = [json.loads(line) for line in comparisons.read_text(encoding='utf-8').splitlines()]
        groups = {n: [r for r in recorded if r['page_source'] == n] for n in range(1, 49)}
        if any(type(r['page_source']) is not int or not 1 <= r['page_source'] <= 48 for r in recorded):
            raise ValueError('Pages réservées dans les résultats : refus.')
        sources.append(dict(fichier=str(comparisons.relative_to(BASE)), sha256=fingerprint(comparisons)))
        sources.append(dict(fichier=str(scores_path.relative_to(BASE)), sha256=fingerprint(scores_path)))
        for number, reference in references.items():
            path = details / variant / f'page_{number:02d}.json'
            page_rows = groups[number]
            if path.is_file():
                detailed = json.loads(path.read_text(encoding='utf-8'))
                candidate, page_score = compare_page(reference, detailed)
                # Les détails doivent représenter exactement la même prédiction que l'étape 5.
                expected = {r['champ']: r for r in page_rows}
                if any(r != expected.get(r['champ']) for r in candidate) or not page_score['sortie_valide']:
                    raise ValueError('Sortie détaillée incompatible avec les comparaisons : relancer le dev.')
                page_rows = candidate
                detail_count += 1
                signal_count += sum('signaux' in c for c in detailed['champs'])
                sources.append(dict(fichier=str(path), sha256=fingerprint(path)))
            elif not allow_comparisons and any(r['present'] for r in page_rows):
                raise ValueError('Sorties détaillées absentes. Option --utiliser-comparaisons requise pour le repli documenté.')
            keys = [r['champ'] for r in page_rows]
            if len(keys) != len(set(keys)) or set(keys) != {c['champ'] for c in reference['champs']}:
                raise ValueError('Comparaisons manquantes ou dupliquées.')
            for r in page_rows:
                if r['specimen_no'] != (number - 1) // 8 + 1:
                    raise ValueError('Patiente incohérente.')
                confidence = r['confiance']
                if confidence is not None and (isinstance(confidence, bool) or not isinstance(confidence, (float, int)) or not np.isfinite(confidence) or not 0 <= confidence <= 1):
                    raise ValueError('Confiance invalide.')
                if r['present'] and confidence is None:
                    raise ValueError('Confiance manquante pour un champ présent.')
                rows.append({**r, 'variante': variant})
    return rows, dict(reference_sha256=fingerprint(truth_path), sources=sources,
                      extraction=signature,
                      pages_detaillees=detail_count, champs_avec_signaux=signal_count,
                      repli_comparaisons=allow_comparisons)


def calibration(confidence, exact, bins=10):
    confidence, exact = np.asarray(confidence), np.asarray(exact)
    if not len(exact):
        return dict(n=0, ece=None, brier=None, groupes=[])
    groups, ece = [], 0.0
    positions = np.minimum((confidence * bins).astype(int), bins - 1)
    for b in range(bins):
        mask = positions == b
        if not mask.any():
            continue
        announced, observed = float(confidence[mask].mean()), float(exact[mask].mean())
        n = int(mask.sum())
        ece += n * abs(announced - observed) / len(exact)
        groups.append(dict(bin=b, n=n, confiance=announced, exactitude=observed))
    return dict(n=len(exact), ece=ece, brier=float(np.mean((confidence - exact) ** 2)), groupes=groups)


def fit(method, x, y):
    if method == 'brute':
        return None
    if len(set(y)) < 2:
        return float(np.mean(y))
    if method == 'isotone':
        return IsotonicRegression(out_of_bounds='clip').fit(x, y)
    return LogisticRegression(C=1000, max_iter=1000).fit(np.asarray(x).reshape(-1, 1), y)


def predict(method, model, x):
    x = np.asarray(x)
    if method == 'brute':
        return x.copy()
    if isinstance(model, float):
        return np.full(len(x), model)
    if method == 'isotone':
        return model.predict(x)
    return model.predict_proba(x.reshape(-1, 1))[:, 1]


def choose_method(x, y, patients):
    metrics = {}
    for method in ['brute', 'logistique', 'isotone']:
        oof = np.empty(len(y))
        for patient in [1, 2, 3, 4]:
            held = patients == patient
            model = fit(method, x[~held], y[~held])
            oof[held] = predict(method, model, x[held])
        metrics[method] = calibration(oof, y)
    best = min(metrics, key=lambda method: metrics[method]['brier'])
    # Garder la confiance brute si la réduction du Brier est négligeable.
    if metrics['brute']['brier'] - metrics[best]['brier'] < 0.001:
        best = 'brute'
    return best, metrics


def mandatory(row):
    return not row['present'] or row['confiance'] is None or not row['type_page_correct'] or row['statut_predit'] in MANDATORY or row['confiance'] < 0.75


def threshold_stats(rows, probabilities, threshold):
    reviewed = [bool(mandatory(r) or p < threshold) for r, p in zip(rows, probabilities)]
    n_auto = sum(not r for r in reviewed)
    errors = sum(not row['exact'] and not review for row, review in zip(rows, reviewed))
    return dict(seuil=float(threshold), n=len(rows), n_revision=sum(reviewed),
                taux_revision=sum(reviewed) / len(rows), n_non_revises=n_auto,
                erreurs_non_revisees=errors, taux_erreur_non_revises=errors / n_auto if n_auto else None)


def choose_threshold(rows, probabilities, target=0.01):
    """Exiger la cible sur chaque variante d'apprentissage, pas seulement leur moyenne."""
    candidates = []
    for threshold in sorted(set([0.0, 1.0] + probabilities.tolist())):
        stats = threshold_stats(rows, probabilities, threshold)
        groups = {}
        for variant in sorted({r['variante'] for r in rows}):
            mask = [r['variante'] == variant for r in rows]
            groups[variant] = threshold_stats([r for r in rows if r['variante'] == variant], probabilities[mask], threshold)
        if all(g['n_non_revises'] and g['taux_erreur_non_revises'] <= target for g in groups.values()):
            candidates.append({**stats, 'par_variante': groups})
    return min(candidates, key=lambda s: (s['taux_revision'], s['seuil'])) if candidates else None


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--utiliser-comparaisons', action='store_true')
    parser.add_argument('--resultats', type=Path, default=BASE / 'resultats_degradations_dev')
    parser.add_argument('--details', type=Path, default=BASE.parent / 'extraction/sorties')
    args = parser.parse_args()
    rows, provenance = load_rows(args.resultats.resolve(), args.details.resolve(), args.utiliser_comparaisons)
    known = [r for r in rows if r['confiance'] is not None and r['present']]
    x = np.asarray([r['confiance'] for r in known], dtype=float)
    y = np.asarray([r['exact'] for r in known], dtype=int)
    patients = np.asarray([r['specimen_no'] for r in known])
    train, verification = patients <= 4, patients >= 5
    method, cv = choose_method(x[train], y[train], patients[train])
    model = fit(method, x[train], y[train])
    calibrated = predict(method, model, x)
    fitted = {'brute': calibration(x[verification], y[verification]),
              'retenue': calibration(calibrated[verification], y[verification])}
    training = {'brute': calibration(x[train], y[train]),
                'retenue': calibration(calibrated[train], y[train])}
    if method == 'isotone':
        parameters = dict(x=model.X_thresholds_.tolist(), y=model.y_thresholds_.tolist())
    elif method == 'logistique':
        parameters = dict(coefficient=float(model.coef_[0, 0]), intercept=float(model.intercept_[0]))
    else:
        parameters = {}
    all_probabilities = predict(method, model, np.asarray([r['confiance'] if r['confiance'] is not None else 0 for r in rows]))
    training_rows = [r for r in rows if r['specimen_no'] <= 4]
    held_rows = [r for r in rows if r['specimen_no'] >= 5]
    train_p = all_probabilities[[r['specimen_no'] <= 4 for r in rows]]
    held_p = all_probabilities[[r['specimen_no'] >= 5 for r in rows]]
    recommended = choose_threshold(training_rows, train_p)
    held_result = threshold_stats(held_rows, held_p, recommended['seuil']) if recommended else None
    verified = held_result is not None and held_result['taux_erreur_non_revises'] is not None and held_result['taux_erreur_non_revises'] <= 0.01
    curves = [threshold_stats(held_rows, held_p, t) for t in np.linspace(0, 1, 201)]
    variants = {}
    for variant in VARIANTS:
        mask = np.asarray([r['variante'] == variant for r in known]) & verification
        subset = [r for r in held_rows if r['variante'] == variant]
        p = held_p[[r['variante'] == variant for r in held_rows]]
        variants[variant] = dict(brute=calibration(x[mask], y[mask]), retenue=calibration(calibrated[mask], y[mask]),
                                 seuil=threshold_stats(subset, p, recommended['seuil']) if recommended else None)
    verified_per_variant = recommended is not None and all(v['seuil']['taux_erreur_non_revises'] is not None and v['seuil']['taux_erreur_non_revises'] <= 0.01 for v in variants.values())
    output = BASE / 'figures'
    output.mkdir(exist_ok=True)
    report = dict(provenance=provenance, methode=method, parametres=parameters, selection_cv_patientes_1_4=cv,
                  versions=dict(sklearn=sklearn.__version__, numpy=np.__version__, matplotlib=matplotlib.__version__),
                  apprentissage=training, verification= fitted, n_reference=len(rows),
                  n_confiances=len(known), n_sans_confiance=len(rows)-len(known),
                  objectif_erreur_empirique=0.01, seuil_apprentissage=recommended,
                  seuil_verification=held_result, seuil_verifie=verified,
                  seuil_verifie_par_variante=verified_per_variant,
                  recommandation=dict(seuil_recalibre=recommended['seuil'] if recommended else None,
                                      regle='revision_obligatoire_ou_confiance_recalibree_inferieure_au_seuil',
                                      objectif='erreur_empirique_au_plus_1pct_dans_chaque_variante_apprentissage',
                                      usage='exploratoire_developpement_sans_modification_pipeline'),
                  par_variante_verification=variants, courbe_seuil_verification=curves)
    (output / 'calibration_dev.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    fig, ax = plt.subplots(figsize=(7, 6))
    ax.plot([0, 1], [0, 1], '--', color='gray', label='Calibration parfaite')
    for name, result in fitted.items():
        bins = result['groupes']
        ax.plot([b['confiance'] for b in bins], [b['exactitude'] for b in bins], 'o-', label=f'{name} — ECE {100 * result["ece"]:.2f} %')
    ax.set(xlabel='Confiance annoncée', ylabel='Proportion de champs entièrement exacts',
           title=f'Vérification patientes 5–6 — {method}', xlim=(0, 1), ylim=(0, 1))
    ax.legend(); ax.grid(alpha=0.2)
    fig.tight_layout(); fig.savefig(output / 'calibration_dev.png', dpi=180); plt.close(fig)
    fig, axes = plt.subplots(2, 1, figsize=(8, 7), sharex=True)
    axes[0].plot([c['seuil'] for c in curves], [100*c['taux_revision'] for c in curves], drawstyle='steps-post')
    axes[0].set(ylabel='Champs en révision (%)', title='Compromis de révision — patientes 5–6', ylim=(0, 100))
    axes[1].plot([c['seuil'] for c in curves], [100*c['taux_erreur_non_revises'] if c['taux_erreur_non_revises'] is not None else np.nan for c in curves], color='tab:orange', drawstyle='steps-post')
    axes[1].axhline(1, linestyle=':', color='tab:red', label='Cible expérimentale : 1 %')
    axes[1].set(xlabel='Seuil de confiance recalibrée' if method != 'brute' else 'Seuil de confiance finale',
                ylabel='Erreur parmi les non révisés (%)', xlim=(0, 1), ylim=(0, None))
    for ax in axes:
        if recommended:
            ax.axvline(recommended['seuil'], color='gray', linestyle='--', label=f'Seuil appris : {recommended["seuil"]:.3f}')
        ax.legend(); ax.grid(alpha=0.2)
    if held_result:
        axes[0].scatter([recommended['seuil']], [100 * held_result['taux_revision']], color='tab:blue', zorder=5, clip_on=False)
        axes[0].annotate(f'{100 * held_result["taux_revision"]:.2f} %',
                         (recommended['seuil'], 100 * held_result['taux_revision']),
                         xytext=(-10, 10), textcoords='offset points', ha='right')
        axes[1].scatter([recommended['seuil']], [100 * held_result['taux_erreur_non_revises']], color='tab:orange', zorder=5, clip_on=False)
        axes[1].set_xlim(-0.01, 1.03)
    fig.tight_layout(); fig.savefig(output / 'compromis_seuil_dev.png', dpi=180); plt.close(fig)
    print(json.dumps(dict(methode=method, ece_brute=fitted['brute']['ece'], ece_recalibree=fitted['retenue']['ece'],
                          seuil= recommended['seuil'] if recommended else None,
                          verification=held_result, seuil_verifie_par_variante=verified_per_variant), ensure_ascii=False))


if __name__ == '__main__':
    main()
