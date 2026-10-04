"""Les champs rétablis du développement respectent le contrat commun."""
import copy
import json
from pathlib import Path
import unittest
from verite_terrain import validate_previous_deliveries


class RestoredDevTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.pages = json.loads((Path(__file__).parent / 'verite_terrain.json').read_text(encoding='utf-8'))['pages'][:48]

    def field(self, number, key):
        return next(f for f in self.pages[number - 1]['champs'] if f['champ'] == key)

    def test_vaccines_and_anomalies(self):
        for start in range(0, 48, 8):
            self.assertEqual(self.field(start + 4, 'nouveau_ne.anomalie')['valeur'], 'RAS')
            for offset, prefix, value in [(6, 'pp_precoce', ['BCG', 'HB']), (8, 'pp_tardif', [])]:
                f = self.field(start + offset, prefix + '.nouveau_ne.vaccins_du_jour')
                self.assertEqual((f['statut'], f['valeur']), ('CONNU', value))

    def test_previous_delivery_counts_and_example(self):
        for n, count in zip(range(2, 49, 8), [1, 3, 1, 4, 1, 3]):
            f = self.field(n, 'obstetrique.accouchements_anterieurs')
            self.assertEqual(f['statut'], 'CONNU')
            self.assertEqual(len(f['valeur']), count)
            validate_previous_deliveries(f['valeur'])
        self.assertEqual(self.field(2, 'obstetrique.accouchements_anterieurs')['valeur'][0],
                         dict(date='2022-11-12', modalite='Voie basse', indication_cesarienne=None,
                              complication='RAS', poids_g=3626, complication_nouveau_ne='RAS'))

    def test_nested_invalid_types_are_rejected(self):
        values = self.field(2, 'obstetrique.accouchements_anterieurs')['valeur']
        for key, value in [('poids_g', True), ('poids_g', '3626'), ('date', '2022-02-30')]:
            bad = copy.deepcopy(values); bad[0][key] = value
            with self.assertRaises(ValueError):
                validate_previous_deliveries(bad)
        bad = copy.deepcopy(values); bad[0]['autre'] = 'RAS'
        with self.assertRaises(ValueError):
            validate_previous_deliveries(bad)


if __name__ == '__main__':
    unittest.main()
