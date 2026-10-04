"""Contrôles des conventions et de la protection du jeu réservé."""
import copy
import json
from pathlib import Path
import unittest

from aligner_conventions import align_corpus, align_fields, BOOLEAN_KEYS, NOT_APPLICABLE


class AlignmentTests(unittest.TestCase):
    def test_reserved_page_unchanged(self):
        page = dict(page_no=50, champs=[dict(champ='profil.niveau_instruction', valeur='RAS', statut='CONNU')])
        before = copy.deepcopy(page)
        align_fields(page)
        self.assertEqual(page, before)

    def test_boolean_and_inapplicable_lists(self):
        corpus = json.loads((Path(__file__).parent / 'verite_terrain.json').read_text(encoding='utf-8'))
        fields = [f for p in corpus['pages'] if p['page_no'] <= 48 for f in p['champs']]
        self.assertTrue(all(f['statut'] == 'CONNU' and type(f['valeur']) is bool
                            for f in fields if f['champ'] in BOOLEAN_KEYS))
        self.assertTrue(all(f['statut'] == 'NON_APPLICABLE' for f in fields
                            if f['champ'] in NOT_APPLICABLE and f['valeur'] is None))

    def test_visual_corrections_and_idempotence(self):
        base = Path(__file__).parent
        corpus = json.loads((base / 'verite_terrain.json').read_text(encoding='utf-8'))
        annotations = json.loads((base / 'annotations_manuelles.json').read_text(encoding='utf-8'))
        before = copy.deepcopy(corpus)
        align_corpus(corpus, annotations)
        self.assertEqual(corpus, before)
        def value(number, key):
            return next(f['valeur'] for f in corpus['pages'][number - 1]['champs'] if f['champ'] == key)
        self.assertEqual(value(10, 'profil.niveau_instruction'), 'Aucun')
        self.assertEqual(value(18, 'profil.niveau_instruction'), 'Collège')
        self.assertEqual(value(12, 'accouchement.indication_cesarienne'), 'Souffrance foetale')
        self.assertEqual(value(28, 'accouchement.indication_cesarienne'), 'Utérus cicatriciel')
        self.assertEqual(value(10, 'antecedents.familiaux.maladies_hereditaires'), 'femme : oncle ; mari : RAS')


if __name__ == '__main__':
    unittest.main()
