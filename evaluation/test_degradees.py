"""Protection du dev et association des dégradations à leur vérité terrain."""
import copy
from contextlib import redirect_stderr
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from evaluer_degradees import BASE, VARIANTS, load_inputs, validate_index, main


class DegradedTests(unittest.TestCase):
    def setUp(self):
        self.inputs, _ = load_inputs(BASE / 'verite_terrain.json', BASE / 'annotations_manuelles.json', {1})
        source = json.loads((BASE / 'annotations_manuelles.json').read_text(encoding='utf-8'))['pages'][0]
        self.entries = [dict(page_pdf=1, degradation=v, split='dev', type_page=self.inputs[0][0]['type_page'],
                             patiente=1, fichier_origine=str(self.inputs[0][1]),
                             sha256_origine=source['image_sha256'],
                             fichier=str(BASE / 'degradees' / f'page_01_{v}.jpg'), sha256=v)
                        for v in VARIANTS]

    def validate(self, entries):
        # L'index temporaire reste dans evaluation/, les images ne sont jamais modifiées.
        with tempfile.TemporaryDirectory(dir=BASE) as directory:
            index = Path(directory) / 'index.json'
            index.write_text(json.dumps(dict(images=entries)), encoding='utf-8')
            def fingerprint(path):
                if path == self.inputs[0][1].resolve():
                    return self.entries[0]['sha256_origine']
                return next(e['sha256'] for e in self.entries if Path(e['fichier']) == path)
            with patch('evaluer_degradees.digest', side_effect=fingerprint):
                return validate_index(index, self.inputs)

    def test_origin_shared_by_six_variants(self):
        entries = self.validate(self.entries)
        self.assertEqual(len(entries), 6)
        self.assertEqual({e['page_pdf'] for e in entries}, {1})

    def test_cli_refuses_reserved_pages_before_generation(self):
        with patch('sys.argv', ['evaluer_degradees', '--pages', '49']), patch('evaluer_degradees.generate') as generate:
            with redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as raised:
                main()
            self.assertEqual(raised.exception.code, 2)
            generate.assert_not_called()

    def test_reserved_duplicate_and_incomplete_rejected(self):
        reserved = copy.deepcopy(self.entries)
        reserved[0]['page_pdf'] = 49
        for entries in [reserved, self.entries + self.entries[:1], self.entries[:-1]]:
            with self.subTest(entries=len(entries)), self.assertRaises(ValueError):
                self.validate(entries)

    def test_wrong_source_type_hash_and_destination_rejected(self):
        for key, value in [('sha256_origine', 'incorrect'), ('sha256', 'incorrect'),
                           ('type_page', 'ACCOUCHEMENT'), ('patiente', 2),
                           ('fichier', str(BASE.parent / 'data/interdit.jpg'))]:
            entries = copy.deepcopy(self.entries)
            entries[0][key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                self.validate(entries)


if __name__ == '__main__':
    unittest.main()
