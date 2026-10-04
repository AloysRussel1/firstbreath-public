"""Contrôles de la fusion des annotations ; bibliothèque standard uniquement."""
import copy
import json
from pathlib import Path
import tempfile
import unittest

from verite_terrain import load_annotations, valider_dossier

BASE = Path(__file__).parent


class AnnotationsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = json.loads((BASE / 'annotations_manuelles.json').read_text(encoding='utf-8'))
        cls.corpus = json.loads((BASE / 'verite_terrain.json').read_text(encoding='utf-8'))
        cls.report = json.loads((BASE / 'rapport_verite_terrain.json').read_text(encoding='utf-8'))

    def load_changed(self, change):
        data = copy.deepcopy(self.data)
        change(data)
        with tempfile.TemporaryDirectory(dir=BASE) as directory:
            path = Path(directory) / 'annotations.json'
            path.write_text(json.dumps(data), encoding='utf-8')
            return load_annotations(path, self.data['source_sha256'])

    def test_annotations_preserved_in_corpus(self):
        pages = {p['page_no']: p for p in self.corpus['pages']}
        annotations = load_annotations(BASE / 'annotations_manuelles.json', self.data['source_sha256'])
        self.assertEqual(sum(map(len, annotations.values())), 278)
        for number, fields in annotations.items():
            actual = {f['champ']: f for f in pages[number]['champs']}
            for field in fields:
                self.assertEqual(actual[field['champ']], field)
        self.assertEqual(valider_dossier(self.corpus), ([], []))

    def test_visual_cases_and_empty_status(self):
        def field(number, key):
            return next(f for f in self.corpus['pages'][number - 1]['champs'] if f['champ'] == key)
        self.assertEqual(field(1, 'identification.grossesse_a_risque')['statut'], 'CONNU')
        self.assertIs(field(1, 'identification.grossesse_a_risque')['valeur'], False)
        self.assertEqual(field(9, 'identification.types_risque')['valeur'], ['HTA'])
        self.assertEqual(field(35, 'grossesse.rhesus')['valeur'], 'NEGATIF')
        self.assertEqual(field(20, 'accouchement.mode')['valeur'], 'VOIE_BASSE_INSTRUMENTALE_FORCEPS')
        self.assertEqual(field(37, 'pp_precoce.mere.complications')['valeur'], ['ANEMIE'])
        self.assertEqual(field(8, 'pp_tardif.nouveau_ne.allaitement')['valeur'], 'MIXTE')

    def test_wrong_pdf_rejected(self):
        with self.assertRaises(ValueError):
            load_annotations(BASE / 'annotations_manuelles.json', '0' * 64)

    def test_wrong_image_hash_rejected(self):
        with self.assertRaises(ValueError):
            self.load_changed(lambda d: d['pages'][0].update(image_sha256='0' * 64))

    def test_duplicate_annotation_rejected(self):
        with self.assertRaises(ValueError):
            self.load_changed(lambda d: d['pages'][0]['champs'].append(d['pages'][0]['champs'][0]))

    def test_wrong_page_image_rejected(self):
        with self.assertRaises(ValueError):
            self.load_changed(lambda d: d['pages'][0].update(image_source=d['pages'][1]['image_source']))

    def test_wrong_value_type_rejected(self):
        with self.assertRaises(ValueError):
            self.load_changed(lambda d: d['pages'][0]['champs'][0].update(valeur='INVENTE'))

    def test_pending_fields_excluded_from_truth(self):
        actual = {(p['page_no'], f['champ']) for p in self.corpus['pages'] for f in p['champs']}
        pending = {(p['page_source'], p['champ']) for p in self.report['a_verifier']}
        self.assertFalse(actual & pending)
        self.assertIn((69, 'pp_precoce.mere.complications'), pending)
        self.assertEqual(sum(k.endswith('vaccins_du_jour') for _, k in pending), 8)
        self.assertEqual(len(pending), self.report['champs_a_verifier'])


if __name__ == '__main__':
    unittest.main()
