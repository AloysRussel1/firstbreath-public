"""Tests des métriques, erreurs de sortie et absence de fuite de valeurs."""
import copy
import io
import json
from contextlib import redirect_stdout, redirect_stderr
from pathlib import Path
import unittest

from evaluer import aggregate, clean_prediction, compare_page, load_inputs, parse_pages, run_evaluation
from evaluer import same_value, normalize_text, selected_pages


def field(key='profil.age', value=31, status='CONNU', confidence=0.9):
    return dict(champ=key, valeur=value, statut=status, confiance=confidence, page_source=2)


def reference(fields=None):
    return dict(page_no=2, specimen_no=1, type_page='ANTECEDENTS', champs=fields if fields is not None else [field()])


def prediction(fields=None, kind='ANTECEDENTS'):
    return dict(type_page=kind, champs=fields if fields is not None else [field()])


class EvaluationTests(unittest.TestCase):
    def test_numeric_tolerances(self):
        self.assertTrue(same_value('pp_precoce.mere.temperature_c', 37.0, 37.1))
        self.assertFalse(same_value('pp_precoce.mere.temperature_c', 37.0, 37.2))
        self.assertTrue(same_value('nouveau_ne.poids_naissance_g', 3200, 3210))
        self.assertFalse(same_value('nouveau_ne.poids_naissance_g', 3200, 3211))
        self.assertFalse(same_value('profil.age', 30, 31))
        self.assertFalse(same_value('profil.age', 1, True))

    def test_text_accents_ligatures_case_and_negation(self):
        key = 'grossesse.visites[0].col'
        self.assertTrue(same_value(key, 'Fermé', 'Ferm'))
        self.assertEqual(normalize_text('  Œdème  '), 'oedeme')
        self.assertTrue(same_value('accouchement.indication_cesarienne', 'Souffrance foetale', 'SOUFFRANCE FŒTALE'))
        self.assertFalse(same_value(key, 'infection', 'sans infection'))
        self.assertFalse(same_value(key, 'RAS', 'RAT'))
        self.assertFalse(same_value('identification.numero_fiche', '12345678', '12345679'))

    def test_reserved_pages_need_opt_in(self):
        self.assertEqual(selected_pages('1-48'), set(range(1, 49)))
        for selection in ['49', '1-80', '48-49']:
            with self.assertRaises(ValueError):
                selected_pages(selection)
        self.assertEqual(selected_pages('49-80', True), set(range(49, 81)))

    def test_exact_output(self):
        rows, page = compare_page(reference(), prediction())
        scores = aggregate(rows)
        self.assertTrue(page['sortie_valide'])
        self.assertEqual(scores['exactitude_champs'], 1)
        self.assertEqual(scores['exactitude_statuts'], 1)
        self.assertEqual(scores['exactitude_valeurs'], 1)

    def test_missing_fields_are_errors_even_for_null_reference(self):
        expected = [field(), field('profil.consanguinite', None, 'NON_FOURNI')]
        rows, _ = compare_page(reference(expected), prediction([]))
        scores = aggregate(rows)
        self.assertEqual(scores['n_champs_manquants'], 2)
        self.assertEqual(scores['n_champs_exacts'], 0)
        self.assertEqual(scores['n_valeurs_renseignees'], 1)
        self.assertEqual(scores['exactitude_valeurs'], 0)

    def test_status_and_value_scores_are_distinct(self):
        rows, _ = compare_page(reference(), prediction([field(status='A_REVISER', confidence=0.5)]))
        scores = aggregate(rows)
        self.assertEqual(scores['exactitude_valeurs'], 1)
        self.assertEqual(scores['exactitude_statuts'], 0)
        self.assertEqual(scores['exactitude_champs'], 0)

    def test_wrong_page_type_is_not_success(self):
        rows, page = compare_page(reference(), prediction(kind='IDENTIFICATION'))
        self.assertFalse(page['type_page_correct'])
        self.assertEqual(aggregate(rows)['n_champs_exacts'], 0)

    def test_non_annotated_predictions_are_excluded(self):
        rows, page = compare_page(reference(), prediction([field(), field('profil.consanguinite', True)]))
        self.assertEqual(len(rows), 1)
        self.assertEqual(page['predictions_non_annotees'], 1)
        self.assertEqual(aggregate(rows)['exactitude_champs'], 1)

    def test_invalid_and_duplicate_values_cannot_score(self):
        cases = [prediction([field(value=True)]), prediction([field(), field()]),
                 prediction([field(confidence=True)]), prediction([field(confidence=float('nan'))]),
                 prediction([field(value=float('nan'), status='A_REVISER')]),
                 prediction([{'champ': 'profil.age'}]), {'type_page': 'ANTECEDENTS', 'champs': None},
                 prediction([field('nom', 'SECRET')]), prediction([42]), None]
        for output in cases:
            with self.subTest(output=type(output).__name__):
                rows, page = compare_page(reference(), output)
                self.assertFalse(page['sortie_valide'])
                self.assertEqual(aggregate(rows)['n_champs_exacts'], 0)

    def test_choice_list_order_is_irrelevant(self):
        expected = dict(page_no=1, specimen_no=1, type_page='IDENTIFICATION',
                        champs=[field('identification.types_risque', ['HTA', 'ANEMIE'])])
        actual = prediction([field('identification.types_risque', ['ANEMIE', 'HTA'])], 'IDENTIFICATION')
        rows, _ = compare_page(expected, actual)
        self.assertTrue(rows[0]['exact'])

    def test_failure_still_counts_reference_and_suppresses_logs(self):
        def broken(_):
            print('SECRET_PATIENTE')
            raise RuntimeError('SECRET_PATIENTE')
        stdout, stderr = io.StringIO(), io.StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr):
            scores, rows = run_evaluation([(reference(), Path('image.png'))], broken)
        self.assertEqual(scores['global']['n_reference'], 1)
        self.assertEqual(scores['anomalies'], {'echec_extract_page': 1})
        self.assertNotIn('SECRET_PATIENTE', stdout.getvalue() + stderr.getvalue() + json.dumps(scores) + json.dumps(rows))

    def test_rows_never_contain_raw_values(self):
        output = prediction([field('profil.niveau_instruction', 'SECRET_PATIENTE')])
        expected = reference([field('profil.niveau_instruction', 'SECRET_PATIENTE')])
        rows, page = compare_page(expected, output)
        self.assertNotIn('SECRET_PATIENTE', json.dumps([rows, page]))

    def test_page_selection(self):
        self.assertEqual(parse_pages('1,3-5,4'), {1, 3, 4, 5})
        for selection in ('0', '81', '5-3', '1-2-3', ''):
            with self.assertRaises(ValueError):
                parse_pages(selection)

    def test_real_sources_deduplicate_images(self):
        base = Path(__file__).parent
        inputs, duplicates = load_inputs(base / 'verite_terrain.json', base / 'annotations_manuelles.json', {7})
        self.assertEqual(len(inputs), 1)
        self.assertEqual(duplicates, 1)
        self.assertEqual(inputs[0][0]['page_no'], 7)

    def test_evaluation_reproducible(self):
        samples = [(reference(), Path('image.png'))]
        extractor = lambda _: prediction()
        self.assertEqual(run_evaluation(samples, extractor), run_evaluation(samples, extractor))


if __name__ == '__main__':
    unittest.main()
