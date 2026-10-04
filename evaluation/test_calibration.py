"""Vérifie les dénominateurs, la révision obligatoire et l'isolation des patientes."""
import unittest
import hashlib
from unittest.mock import patch
import numpy as np

from calibrer import calibration, choose_method, choose_threshold, fit, threshold_stats, load_rows, BASE


class CalibrationTests(unittest.TestCase):
    def test_ece_weighted_and_confidence_one(self):
        result = calibration([0.1, 0.1, 1.0], [0, 1, 1])
        self.assertAlmostEqual(result['ece'], 0.4 * 2 / 3)
        self.assertEqual(result['groupes'][-1]['n'], 1)
        self.assertEqual(result['groupes'][-1]['bin'], 9)

    def test_absent_and_uncertain_always_reviewed(self):
        ordinary = dict(present=True, confiance=0.99, type_page_correct=True, statut_predit='CONNU', exact=True)
        missing = {**ordinary, 'present': False, 'confiance': None, 'exact': False}
        uncertain = {**ordinary, 'statut_predit': 'A_REVISER', 'exact': False}
        result = threshold_stats([ordinary, missing, uncertain], [0.99, 1, 1], 0.5)
        self.assertEqual((result['n_revision'], result['n_non_revises']), (2, 1))
        self.assertEqual(result['taux_erreur_non_revises'], 0)
        ordinary['exact'] = False
        self.assertEqual(threshold_stats([ordinary], [0.99], 0.5)['taux_erreur_non_revises'], 1)

    def test_empty_automatic_set_has_no_error_estimate(self):
        row = dict(present=False, confiance=None, type_page_correct=False, statut_predit=None, exact=False)
        self.assertIsNone(threshold_stats([row], [0], 1)['taux_erreur_non_revises'])
        self.assertIsNone(calibration([], [])['ece'])

    def test_threshold_does_not_hide_bad_variant_in_average(self):
        rows = [dict(variante='propre', present=True, confiance=0.99, type_page_correct=True, statut_predit='CONNU', exact=True) for _ in range(200)]
        rows += [{**rows[0], 'variante': 'flou', 'exact': False}, {**rows[0], 'variante': 'flou'}]
        probabilities = np.array([0.99] * 200 + [0.8, 0.99])
        choice = choose_threshold(rows, probabilities)
        self.assertEqual(choice['seuil'], 0.99)
        self.assertEqual(choice['n_revision'], 1)

    def test_absent_detailed_files_require_explicit_fallback(self):
        import json
        import tempfile
        from pathlib import Path
        with tempfile.TemporaryDirectory(dir=BASE) as directory:
            result = Path(directory) / 'propre'
            result.mkdir()
            truth_hash = hashlib.sha256((BASE / 'verite_terrain.json').read_bytes()).hexdigest()
            provenance = dict(pages=list(range(1, 49)), reference_sha256=truth_hash,
                              modele='simule', fournisseur='simule', pipeline_sha256='p',
                              client_sha256='c', normalisation_sha256='n')
            (result / 'scores.json').write_text(json.dumps(dict(provenance=provenance)), encoding='utf-8')
            (result / 'comparaisons.jsonl').write_text(json.dumps(dict(page_source=1, present=True)) + '\n', encoding='utf-8')
            with self.assertRaisesRegex(ValueError, 'Sorties détaillées absentes'):
                load_rows(Path(directory), Path(directory) / 'details')

    def test_cv_keeps_entire_patient_out_of_training(self):
        x = np.array([0.1, 0.2, 0.3, 0.4])
        y = np.array([0, 1, 0, 1])
        patients = np.array([1, 2, 3, 4])
        trained = []
        def tracked(method, train_x, train_y):
            trained.append(tuple(train_x))
            return fit(method, train_x, train_y)
        with patch('calibrer.fit', side_effect=tracked):
            choose_method(x, y, patients)
        for inputs in trained:
            self.assertEqual(len(inputs), 3)
        self.assertEqual(set(trained), {(0.2, 0.3, 0.4), (0.1, 0.3, 0.4), (0.1, 0.2, 0.4), (0.1, 0.2, 0.3)})


if __name__ == '__main__':
    unittest.main()
