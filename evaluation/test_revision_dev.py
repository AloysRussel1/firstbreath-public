"""Protection du jeu réservé et validation des corrections de relecture."""
import copy
import json
from pathlib import Path
import unittest
from reviser_cases_dev import merge_corrections
from couverture_dev import write_coverage
from verite_terrain import expected_keys


class ReviewTests(unittest.TestCase):
    def test_complete_development(self):
        corpus = json.loads((Path(__file__).parent / 'verite_terrain.json').read_text(encoding='utf-8'))
        for page in corpus['pages'][:48]:
            self.assertEqual({f['champ'] for f in page['champs']}, set(expected_keys(page['type_page'])))
        report = write_coverage()
        self.assertEqual((report['champs_annotes'], report['champs_non_annotes']), (1470, 0))

    def test_reserved_page_and_invalid_correction_rejected(self):
        data = dict(pages=[dict(page_no=1, type_page='IDENTIFICATION', champs=[])])
        for number, key, value in [(49, 'identification.grossesse_a_risque', False),
                                   (1, 'identification.grossesse_a_risque', 'false'),
                                   (1, 'nom', 'INTERDIT')]:
            with self.assertRaises(ValueError):
                merge_corrections(copy.deepcopy(data), dict(corrections=[dict(page_no=number, champ=key, valeur=value, statut='CONNU')]))

    def test_valid_correction_and_duplicate_rejected(self):
        data = dict(pages=[dict(page_no=1, type_page='IDENTIFICATION', champs=[])])
        correction = dict(page_no=1, champ='identification.grossesse_a_risque', valeur=False, statut='CONNU')
        merge_corrections(data, dict(corrections=[correction]))
        self.assertIs(data['pages'][0]['champs'][0]['valeur'], False)
        with self.assertRaises(ValueError):
            merge_corrections(data, dict(corrections=[correction, correction]))


if __name__ == '__main__':
    unittest.main()
