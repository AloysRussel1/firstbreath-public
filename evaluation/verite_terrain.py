"""Vérité terrain textuelle du spécimen. Aucune image ni donnée source modifiée."""
import argparse
from collections import Counter
from datetime import datetime
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
import uuid

sys.dont_write_bytecode = True

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from shared.valider import SCHEMA, valider_page, valider_dossier, definition, hors_plage, verifier_type

DATE = r"\d{2}/\d{2}/\d{4}"
NUM = r"\d+(?:[.,]\d+)?"
TYPES = list(SCHEMA['pages'])
EMPTY = {'—', '–', '--', '-'}


def iso(s):
    return datetime.strptime(s, '%d/%m/%Y').date().isoformat()


def normalized(s):
    s = s.strip()
    return 'RAS' if s.casefold() in {'ras', 'aucun', 'aucune', 'néant'} else s


def find_tool(explicit=None):
    candidates = [explicit, shutil.which('pdftotext'), r'C:\Program Files\Git\mingw64\bin\pdftotext.exe']
    for candidate in candidates:
        if candidate and Path(candidate).is_file():
            return str(candidate)
    raise RuntimeError('pdftotext introuvable : utiliser --pdftotext chemin\\pdftotext.exe')


def extract_text(tool, pdf, mode):
    result = subprocess.run([tool, '-f', '1', '-l', '48', '-enc', 'UTF-8', '-eol', 'unix', mode, str(pdf), '-'], capture_output=True, check=True)
    pages = result.stdout.decode('utf-8').split('\f')
    if not pages[-1].strip():
        pages.pop()
    if len(pages) != 48:
        raise ValueError(f'48 pages de développement attendues, {len(pages)} trouvées')
    # Le texte complet reste seulement en mémoire : il contient des identifiants interdits.
    return pages


class Page:
    def __init__(self, number):
        self.number = number
        self.kind = TYPES[(number - 1) % 8]
        self.fields = {}
        self.pending = {}

    def put(self, key, value, status=None):
        d = definition(key)
        if d is None:
            raise ValueError(f'Clé absente du schéma : {key}')
        if isinstance(value, str) and value.strip() in EMPTY:
            value, status = None, 'NON_FOURNI'
        status = status or ('NON_FOURNI' if value is None else 'CONNU')
        if d['type'] == 'texte' and isinstance(value, str) and any(len(word) == 1 for word in re.findall(r'[^\W\d_]+', value)):
            self.pending[key] = 'Glyphes manquants dans la couche texte ; vérifier sur l’image sans deviner.'
            return
        if value is not None and not verifier_type(d, value):
            self.pending[key] = 'Texte présent mais format ambigu ; vérifier visuellement.'
            return
        if value is not None and d['type'] in ('entier', 'decimal', 'tension') and hors_plage(d, value):
            status = 'A_REVISER'
        self.fields[key] = dict(champ=key, valeur=value, statut=status, confiance=1.0, page_source=self.number)

    def match(self, text, key, pattern, convert=normalized, flags=0):
        match = re.search(pattern, text, flags)
        if match:
            self.put(key, convert(match.group(1)))

    def result(self):
        return dict(page_no=self.number, specimen_no=(self.number - 1) // 8 + 1,
                    type_page=self.kind, champs=list(self.fields.values()))


def identification(p, raw):
    p.match(raw, 'identification.numero_fiche', r'N° de la fiche\s*:\s*([\d-]+)')
    p.match(raw, 'identification.region', r'Région\s*:\s*(.*?)\s+Province\s*:', flags=re.S)
    p.match(raw, 'identification.province', r'Province\s*:\s*([^\n]+)')
    p.match(raw, 'identification.etablissement', r"Nom de l'établissement sanitaire\s*:\s*([^\n]+)")


def antecedents(p, raw, layout):
    p.match(raw, 'profil.age', r'Age\s*:\s*(\d+)', int)
    p.match(raw, 'profil.niveau_instruction', r"Niveau d'instruction\s*:\s*(.*?)\s+Profession\s*:", convert=str.strip, flags=re.S)
    for label, key in [('Gestation', 'gestite'), ('Parité', 'parite'), ("Nombre d'enfants vivants", 'enfants_vivants')]:
        p.match(raw, 'obstetrique.' + key, re.escape(label) + r'\s*:\s*(\d+)', int)
    p.match(raw, 'depistage.frottis_iva', r'Frottis cervical / IVA \(moins de 3 ans\)\s*:\s*([^\n]+)')
    # Les deux colonnes familiales sont conservées, sans inventer de sous-clés.
    for label, key in [('HTA', 'hta'), ('Diabète', 'diabete'), ('Maladies héréditaires', 'maladies_hereditaires'), ('Malformations', 'malformations'), ('Allergie(s)', 'allergies')]:
        m = re.search(r'^' + re.escape(label) + r'\s+(.+)$', raw, re.M)
        if m:
            cells = m.group(1).rsplit(' ', 1)
            if len(cells) == 2 and cells[1] == 'RAS':
                value = 'RAS' if cells[0] == 'RAS' else f'Famille de la femme : {cells[0]}; mari/famille : RAS'
                p.put('antecedents.familiaux.' + key, value)
    for line in layout.splitlines():
        cells = re.split(r'\s{2,}', line.strip())
        if len(cells) == 3 and cells[1] in {'Aucun', 'Appendicectomie'}:
            for key, value in zip(['medicaux', 'chirurgicaux', 'gynecologiques'], cells):
                p.put('antecedents.femme.' + key, normalized(value))
    for label, key in [('Avortement', 'avortements'), ('Accouchement prématuré', 'prematures'), ('Mort fœtale in utéro', 'morts_foetales')]:
        m = re.search(r'^' + re.escape(label) + r'([^\n]*)$', raw, re.M)
        if m:
            count = re.match(r'\s+(\d+)\b', m.group(1))
            p.put('obstetrique.' + key, int(count.group(1)) if count else None)
    p.pending['obstetrique.accouchements_anterieurs'] = 'Tableau à annoter selon les six sous-clés de la section 7.'


def pregnancy(p, raw, layout):
    for key, label in [('ddr', 'DDR'), ('date_prevue_accouchement', "DATE PRÉVUE D'ACCOUCHEMENT"), ('date_depassement_terme', 'DATE DE DÉPASSEMENT DE TERME')]:
        p.match(raw, 'grossesse.' + key, re.escape(label) + r'\s*:\s*(' + DATE + ')', iso)
    p.match(raw, 'grossesse.taille_cm', r'Taille\s*:\s*(\d+)\s*cm', int)
    header = next(line for line in layout.splitlines() if 'Prestations / Visites' in line)
    anchors = [m.start() for m in re.finditer(r'Visite [123]|[789]\S* mois', header)]
    if len(anchors) == 8:
        anchors.append(anchors[-1] + anchors[-1] - anchors[-2])
    positions = [m.start() for line in layout.splitlines() for m in re.finditer(r'\d+ SA', line)]
    slots = sorted(min(range(len(anchors)), key=lambda i: abs(anchors[i] - pos)) for pos in positions)
    if len(anchors) != 9 or len(set(slots)) != len(slots):
        raise ValueError(f'Page {p.number} : colonnes des visites ambiguës')
    payload = raw.rsplit('Examen fait par', 1)[1].split('Document synthétique', 1)[0]
    lines = [line.strip() for line in payload.splitlines() if line.strip()]
    blocks, block = [], []
    for line in lines:
        block.append(line)
        if re.fullmatch(r'(?:Dr\s+.+|Inf\.\s+.+|Sage-femme)', line):
            blocks.append(block)
            block = []
    if block or len(blocks) != len(slots):
        raise ValueError(f'Page {p.number} : nombre de visites incohérent')
    for visit_no, (slot, rows) in enumerate(zip(slots, blocks)):
        prefix = f'grossesse.visites[{slot}].'
        # Certains glyphes accentués/dashes manquent dans le PDF lui-même.
        # Seuls les champs dont la position reste certaine sont retenus.
        age_idx = next(i for i, row in enumerate(rows) if re.fullmatch(r'\d+ SA', row))
        dates = rows[:age_idx]
        if len(dates) == 3:
            for key, value in zip(['date_rdv', 'date_venue', 'relance'], dates):
                if key == 'relance':
                    p.put(prefix + key, value == 'Oui') if value in {'Oui', 'Non'} else None
                elif re.fullmatch(DATE, value):
                    p.put(prefix + key, iso(value))
                elif value in EMPTY:
                    p.put(prefix + key, None)
        elif len(dates) == 2 and re.fullmatch(DATE, dates[0]) and dates[1] in {'Oui', 'Non'}:
            p.put(prefix + 'date_venue', iso(dates[0]))
            p.put(prefix + 'relance', dates[1] == 'Oui')
        p.put(prefix + 'age_gestationnel_sa', int(rows[age_idx].split()[0]))
        clinical = rows[age_idx + 1:]
        p.put(prefix + 'poids_kg', float(clinical[0]))
        p.put(prefix + 'tension', clinical[1])
        # Squelette, conjonctives, seins sont hors schéma des visites.
        if clinical[5] not in {'Oui', 'Non'}:
            raise ValueError(f'Page {p.number} : séquence clinique inattendue')
        p.put(prefix + 'oedemes', clinical[5] == 'Oui')
        bio_start = next(i for i, row in enumerate(clinical) if row in {'Neg', 'Pos +', 'Pos', 'Positif', 'Négatif'})
        middle = clinical[6:bio_start]
        if len(middle) == 7:
            for key, value in zip(['mouvements_actifs', 'hauteur_uterine_cm', 'bcf', '_speculum', 'col', 'presentation', '_bassin'], middle):
                if key.startswith('_'):
                    continue
                if value in EMPTY:
                    p.put(prefix + key, None)
                elif key == 'mouvements_actifs' and value in {'Oui', 'Non'}:
                    p.put(prefix + key, value == 'Oui')
                elif key in {'hauteur_uterine_cm', 'bcf'} and value.isdigit():
                    p.put(prefix + key, int(value))
                elif key == 'col':
                    p.put(prefix + key, value)
                elif key == 'presentation' and value == 'Céphalique':
                    p.put(prefix + key, 'CEPHALIQUE')
        else:
            numbers = [int(row) for row in middle if row.isdigit()]
            if len(numbers) == 2:
                p.put(prefix + 'hauteur_uterine_cm', numbers[0])
                p.put(prefix + 'bcf', numbers[1])
            if middle and middle[0] in {'Oui', 'Non'}:
                p.put(prefix + 'mouvements_actifs', middle[0] == 'Oui')
            if 'Fermé' in middle:
                p.put(prefix + 'col', 'Fermé')
            if 'Céphalique' in middle:
                p.put(prefix + 'presentation', 'CEPHALIQUE')
        bio = clinical[bio_start:-1]
        for key, value in zip(['glucosurie', 'albuminurie'], bio[:2]):
            p.put(prefix + key, {'Neg': 'NEGATIF', 'Pos +': 'POSITIF', 'Pos': 'POSITIF'}.get(value, value))
        hb = next((row for row in bio if re.fullmatch(NUM + r' g/dL', row)), None)
        if hb:
            p.put(prefix + 'hemoglobine_g_dl', float(hb.split()[0]))
        role = rows[-1]
        p.put(prefix + 'examine_par_fonction', 'MEDECIN' if role.startswith('Dr ') else 'INFIRMIER' if role.startswith('Inf.') else 'SAGE_FEMME')
        if visit_no == 0:
            keys = ['rubeole', 'toxoplasmose', 'syphilis', 'hepatite_b', 'vih']
            mapping = {'Neg': 'NEGATIF', 'Pos +': 'POSITIF', 'Immune': 'IMMUNE', 'Non immune': 'NON_IMMUNE'}
            for key, value in zip(keys, bio[2:7]):
                p.put('grossesse.tests.' + key, mapping.get(value, value))
            for row in bio:
                if re.fullmatch(r'\d+k', row):
                    p.put('grossesse.tests.plaquettes', int(row[:-1]))
                if re.fullmatch(NUM + r' g/L', row):
                    p.put('grossesse.tests.glycemie_g_l', float(row.split()[0]))
            if len(bio) >= 2 and bio[-1] in {'Oui', 'Non'}:
                p.put('grossesse.traitement.fer', bio[-1] == 'Oui')
                p.put('grossesse.tests.rai', mapping.get(bio[-2], bio[-2]))


def delivery(p, raw):
    p.match(raw, 'accouchement.date', r"Date de l'accouchement\s*:\s*(" + DATE + ')', iso)
    p.match(raw, 'accouchement.indication_cesarienne', r"Préciser l'indication\s*:[ \t]*([^\n]+)")
    p.match(raw, 'nouveau_ne.sexe', r'Sexe\s*:\s*([FM])\b', str)
    p.match(raw, 'nouveau_ne.poids_naissance_g', r'Poids à la naissance\s*:\s*(\d+)\s*g', int)
    p.match(raw, 'nouveau_ne.perimetre_cranien_cm', r'Périmètre crânien à la naissance\s*:\s*(' + NUM + r')\s*cm', float)
    p.match(raw, 'nouveau_ne.age_gestationnel_sa', r'Âge gestationnel\s*:\s*(\d+)\s*SA', int)
    p.match(raw, 'nouveau_ne.anomalie', r'Anomalie à préciser\s*:\s*([^\n]+)')


def postpartum(p, raw, newborn, late):
    prefix = ('pp_tardif.' if late else 'pp_precoce.') + ('nouveau_ne.' if newborn else 'mere.')
    p.match(raw, prefix + 'date_consultation', r'Date de la consultation\s*:\s*(' + DATE + ')', iso)
    if newborn:
        patterns = [('age_jours', r'Age\s*(\d+)\s*jours', int), ('temperature_c', r'Température\s*(' + NUM + ')', float), ('poids_g', r'Poids\s*(\d+)\s*g', int), ('taille_cm', r'Taille\s*(\d+)\s*cm', float), ('perimetre_cranien_cm', r'Périmètre crânien\s*(' + NUM + ')', float)]
        p.match(raw, prefix + 'prochaine_visite', r'Revenir pour une visite de suivi nécessaire le\s*(' + DATE + ')', iso)
    else:
        patterns = [('temperature_c', r'T°\s*(' + NUM + ')', float), ('tension', r'TA\s*(\d{2,3}/\d{2,3})', str), ('pouls', r'Pouls\s*(\d+)', int), ('poids_kg', r'Poids\s*(' + NUM + r')\s*kg', float)]
        m = re.search(r'Prochain rendez-vous le([^\n]*)', raw)
        if m:
            date = re.search(DATE, m.group(1))
            p.put(prefix + 'prochain_rdv', iso(date.group()) if date else None)
    for key, pattern, converter in patterns:
        p.match(raw, prefix + key, pattern, converter)


def expected_keys(kind):
    page = SCHEMA['pages'][kind]
    keys = [c['cle'] for c in page['champs']]
    if 'visites' in page:
        keys += [f'grossesse.visites[{i}].{c["cle"]}' for i in range(9) for c in page['visites']['champs']]
    return keys


def load_annotations(path, pdf_hash, max_page=48):
    """Vérifie les corrections et leur provenance avant toute fusion."""
    data = json.loads(path.read_text(encoding='utf-8-sig'))
    if data.get('source_sha256') != pdf_hash:
        raise ValueError('Les annotations correspondent à un autre PDF.')
    annotations = {}
    for page in data['pages']:
        number = page['page_no']
        if type(number) is int and number > max_page:
            continue
        if type(number) is not int or not 1 <= number <= 80 or number in annotations:
            raise ValueError('Page annotée invalide ou dupliquée.')
        kind = TYPES[(number - 1) % 8]
        if page['type_page'] != kind:
            raise ValueError(f'Page {number} : type annoté incorrect.')
        if not re.fullmatch(rf'dossiers_specimen_10_patientes-{number:02d}(?:__[^/\\]+)?\.png', page['image_source']):
            raise ValueError(f'Page {number} : nom image incompatible.')
        image = ROOT / 'data/Paper Registry' / page['image_source']
        if image.parent.resolve() != (ROOT / 'data/Paper Registry').resolve():
            raise ValueError('Chemin image hors du dossier source.')
        if hashlib.sha256(image.read_bytes()).hexdigest() != page['image_sha256']:
            raise ValueError(f'Page {number} : image modifiée depuis l’annotation.')
        keys = set()
        for field in page['champs']:
            key = field['champ']
            if key not in expected_keys(kind) or key in keys or field['page_source'] != number:
                raise ValueError(f'Page {number} : champ annoté incompatible ou dupliqué.')
            keys.add(key)
            d = definition(key)
            if field['valeur'] is not None and not verifier_type(d, field['valeur']):
                raise ValueError(f'Page {number} : type de valeur annotée incorrect.')
            if key == 'obstetrique.accouchements_anterieurs' and field['valeur'] is not None:
                validate_previous_deliveries(field['valeur'])
        errors, warnings = valider_page(page)
        if errors or warnings:
            raise ValueError(f'Page annotée {number} invalide : {errors + warnings}')
        annotations[number] = page['champs']
    return annotations


def validate_previous_deliveries(deliveries):
    keys = {'date', 'modalite', 'indication_cesarienne', 'complication',
            'poids_g', 'complication_nouveau_ne'}
    if not isinstance(deliveries, list) or len(deliveries) > 5:
        raise ValueError('Liste des accouchements antérieurs invalide.')
    for item in deliveries:
        if not isinstance(item, dict) or set(item) != keys:
            raise ValueError('Sous-clés des accouchements antérieurs invalides.')
        for key, value in item.items():
            if value is None:
                continue
            if key == 'poids_g':
                if type(value) is not int or value <= 0:
                    raise ValueError('Poids antérieur invalide.')
            elif not isinstance(value, str) or not value.strip():
                raise ValueError('Valeur textuelle antérieure invalide.')
            elif key == 'date':
                if not re.fullmatch(r'\d{4}-\d{2}-\d{2}', value):
                    raise ValueError('Date antérieure invalide.')
                datetime.strptime(value, '%Y-%m-%d')


def write_pending(path, pending):
    groups = {}
    for item in pending:
        group = (item['type_page'], item['champ'], item['raison'])
        groups.setdefault(group, []).append(item['page_source'])
    lines = ['# Annotations restantes', '',
             f'{len(pending)} champs restent hors du corpus de référence.', '',
             'Les numéros ci-dessous sont les pages globales du PDF. Les champs en attente ne doivent pas être évalués comme des valeurs absentes.', '',
             '| Type de page | Champ | Pages | Motif |',
             '|---|---|---|---|']
    for (kind, key, reason), numbers in sorted(groups.items()):
        lines.append(f'| {kind} | `{key}` | {", ".join(map(str, numbers))} | {reason} |')
    path.write_text('\n'.join(lines) + '\n', encoding='utf-8')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--pdf', type=Path, default=ROOT / 'data/Paper Registry/dossiers_specimen_10_patientes.pdf')
    parser.add_argument('--pdftotext')
    parser.add_argument('--annotations', type=Path, default=Path(__file__).parent / 'annotations_manuelles.json')
    args = parser.parse_args()
    pdf_hash = hashlib.sha256(args.pdf.read_bytes()).hexdigest()
    annotations = load_annotations(args.annotations, pdf_hash)
    tool = find_tool(args.pdftotext)
    raw_pages, layout_pages = extract_text(tool, args.pdf, '-raw'), extract_text(tool, args.pdf, '-layout')
    pages, pending = [], []
    for number, (raw, layout) in enumerate(zip(raw_pages, layout_pages), 1):
        p = Page(number)
        kind = (number - 1) % 8
        if kind == 0:
            identification(p, raw)
        elif kind == 1:
            antecedents(p, raw, layout)
        elif kind == 2:
            pregnancy(p, raw, layout)
        elif kind == 3:
            delivery(p, raw)
        else:
            postpartum(p, raw, kind in {5, 7}, kind >= 6)
        for field in annotations.get(number, []):
            p.fields[field['champ']] = dict(field)
        if number == 69:
            p.pending['pp_precoce.mere.complications'] = 'Présence de complication cochée, mais aucun type coché ; demander une clarification.'
        if kind in {5, 7}:
            prefix = ('pp_tardif.' if kind == 7 else 'pp_precoce.') + 'nouveau_ne.'
            p.pending[prefix + 'signes_danger'] = 'Cases vides et mention Néant dans Autres : convenir du codage de cette absence pour liste_choix (RAS incompatible).'
            p.pending[prefix + 'vaccins_du_jour'] = 'Cases de vaccins à annoter visuellement.'
        page = p.result()
        errors, warnings = valider_page(page)
        if errors or warnings:
            raise ValueError(f'Page {number} invalide : {errors + warnings}')
        pages.append(page)
        for key in expected_keys(p.kind):
            if key not in p.fields:
                d = definition(key)
                reason = p.pending.get(key, 'Case cochée à lire visuellement.' if d['type'] in {'booleen', 'choix', 'liste_choix'} else 'Valeur absente ou alignement/glyphes ambigus ; vérifier visuellement.')
                pending.append(dict(page_source=number, specimen_no=page['specimen_no'], type_page=p.kind, champ=key, raison=reason))
    corpus = dict(corpus_id=str(uuid.uuid4()), etat='A_REVISER', pages=pages)
    errors, warnings = valider_dossier(corpus)
    if errors or warnings:
        raise ValueError(str(errors + warnings))
    output = Path(__file__).parent
    # Le jeu réservé n'est ni relu ni régénéré pendant le développement.
    previous = json.loads((output / 'verite_terrain.json').read_text(encoding='utf-8'))
    corpus['pages'] += [page for page in previous['pages'] if page['page_no'] > 48]
    annotation_data = json.loads(args.annotations.read_text(encoding='utf-8-sig'))
    from evaluation.aligner_conventions import align_corpus
    columns = align_corpus(corpus, annotation_data)
    available = {(page['page_no'], f['champ']) for page in corpus['pages'] for f in page['champs']}
    previous_report = json.loads((output / 'rapport_verite_terrain.json').read_text(encoding='utf-8'))
    pending += [item for item in previous_report['a_verifier'] if item['page_source'] > 48]
    pending = [item for item in pending if (item['page_source'], item['champ']) not in available]
    pages = corpus['pages']
    errors, warnings = valider_dossier(corpus)
    if errors or warnings:
        raise ValueError('Corpus aligné invalide.')
    counts = Counter(p['type_page'] for p in pages)
    report = dict(source_pdf=args.pdf.name, source_sha256=pdf_hash,
                  pages=len(pages), specimens=10, champs_extraits=sum(len(p['champs']) for p in pages),
                  champs_a_verifier=len(pending), pages_par_type=dict(counts),
                  champs_annotes=sum(len(page['champs']) for page in annotation_data['pages']),
                  visites_vides_non_applicables_dev=columns,
                  methode='pdftotext UTF-8 raw + layout et annotations visuelles persistantes ; texte brut non enregistré',
                  a_verifier=pending)
    for name, value in [('verite_terrain.json', corpus), ('rapport_verite_terrain.json', report)]:
        (output / name).write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    write_pending(output / 'A_ANNOTER.md', pending)
    from evaluation.couverture_dev import write_coverage
    write_coverage()
    print(f'VALIDE : {len(pages)} pages, {report["champs_extraits"]} champs ; {len(pending)} champs à vérifier.')


if __name__ == '__main__':
    main()




