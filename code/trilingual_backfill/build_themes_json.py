#!/usr/bin/env python3
"""Parse the Hecht archive_folders.tsv to build a theme-tags map per
Family Collection (G-F-NNNN), with EN/DE/HE labels for each tag.

Writes the result as JSON for the LivelyTrilingual theme to consume at
render time:  themes/LivelyTrilingual/data/themes.json

Format:
  {
    "G-F-0008": [
      {"he": "מלח\"ע I", "en": "First World War", "de": "Erster Weltkrieg"},
      ...
    ],
    ...
  }
"""
import csv, json, re
from collections import OrderedDict
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SRC = REPO / "data" / "hecht" / "archive_folders.tsv"
OUT = REPO / "themes" / "LivelyTrilingual" / "data" / "themes.json"

# Curated translations for the most-common tags (covers ~80% of occurrences).
# Tags not in this map fall through with HE = original, EN/DE = HE (so HE locale
# still works; EN/DE will show the HE word — better than nothing).
TRANSLATIONS = {
    'תולדות משפחה':   ('Family history',         'Familiengeschichte'),
    'תעודות אישיות':  ('Personal documents',     'Persönliche Dokumente'),
    'התכתבות':        ('Correspondence',         'Korrespondenz'),
    'ביוגרפיה':       ('Biography',              'Biographie'),
    'תמונות':         ('Photographs',            'Fotografien'),
    'מנהגים':         ('Customs',                'Bräuche'),
    'הרייך השלישי':   ('Third Reich',            'Drittes Reich'),
    'אמנות':          ('Art',                    'Kunst'),
    'אומנות':         ('Art',                    'Kunst'),
    'מלח"ע I':        ('First World War',        'Erster Weltkrieg'),
    'מלח"ע II':       ('Second World War',       'Zweiter Weltkrieg'),
    'פלשתינה':        ('Palestine',              'Palästina'),
    'כתיבה אישית':    ('Personal writing',       'Persönliche Schriften'),
    'צבא':            ('Military',               'Militär'),
    'הגירה':          ('Migration',              'Migration'),
    'מחנות מעצר':     ('Internment camps',       'Internierungslager'),
    'מחנות':          ('Camps',                  'Lager'),
    'פעילות פוליטית': ('Political activity',     'Politische Tätigkeit'),
    'פרסומים':        ('Publications',           'Publikationen'),
    'פירסומים':       ('Publications',           'Publikationen'),
    'ספרות':          ('Literature',             'Literatur'),
    'גלויות':         ('Postcards',              'Postkarten'),
    'אירגונים':       ('Organisations',          'Organisationen'),
    'משפחה':          ('Family',                 'Familie'),
    'הגנה':           ('Haganah',                'Haganah'),
    'נהריה':          ('Nahariya',               'Naharija'),
    'יומן':           ('Diary',                  'Tagebuch'),
    'יומנים':         ('Diaries',                'Tagebücher'),
    'מכתבים':         ('Letters',                'Briefe'),
    'מסחר':           ('Commerce',               'Handel'),
    'כלכלה':          ('Economy',                'Wirtschaft'),
    'חינוך':          ('Education',              'Bildung'),
    'דת':             ('Religion',               'Religion'),
    'ילדות':          ('Childhood',              'Kindheit'),
    'נעורים':         ('Youth',                  'Jugend'),
    'שואה':           ('Holocaust',              'Schoah'),
    'אנטישמיות':      ('Antisemitism',           'Antisemitismus'),
    'אישי':           ('Personal',               'Persönlich'),
    'ספורט':          ('Sport',                  'Sport'),
    'תיאטרון':        ('Theatre',                'Theater'),
    'מוסיקה':         ('Music',                  'Musik'),
    'רפואה':          ('Medicine',               'Medizin'),
    'משפט':           ('Law',                    'Recht'),
}

def normalise(tag: str) -> str:
    tag = tag.strip().strip('.').strip()
    tag = re.sub(r'^\d+\.?\s+', '', tag)   # strip "1 ", "1. ", "2. "
    tag = re.sub(r'^\*+', '', tag).strip()
    # Drop noise: free-text continuations after asterisk
    tag = re.sub(r'\s*\*.*$', '', tag).strip()
    return tag

def main():
    themes = OrderedDict()
    with open(SRC, newline='') as f:
        reader = csv.DictReader(f, delimiter='\t')
        for row in reader:
            acc = (row.get('accession_id') or '').strip()
            if not acc:
                continue
            parts = acc.split('-')
            if len(parts) < 3:
                continue
            fid = '-'.join(parts[:3])
            desc = (row.get('description') or '').strip()
            m = re.search(r'קטגוריות[:\s]*([^|]*?\|.+)', desc)
            if not m:
                continue
            seen_he = set()
            for raw in m.group(1).split('|'):
                tag_he = normalise(raw)
                if not (2 < len(tag_he) < 50):
                    continue
                if 'קטגוריות' in tag_he:
                    continue
                if tag_he in seen_he:
                    continue
                seen_he.add(tag_he)
                en, de = TRANSLATIONS.get(tag_he, (tag_he, tag_he))
                themes.setdefault(fid, []).append({'he': tag_he, 'en': en, 'de': de})

    # Cap each family at 10 themes (most distinctive first by insertion order).
    for fid in themes:
        themes[fid] = themes[fid][:10]

    OUT.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT, 'w', encoding='utf-8') as f:
        json.dump(themes, f, ensure_ascii=False, indent=2, sort_keys=True)

    print(f"Families with themes: {len(themes)}")
    print(f"Average tags per family: {sum(len(v) for v in themes.values()) / len(themes):.1f}")
    print(f"Wrote: {OUT}")
    # Sample
    sample = next(iter(themes.items()))
    print(f"\nSample ({sample[0]}):")
    for t in sample[1]:
        print(f"  he={t['he']:<20} en={t['en']:<22} de={t['de']}")

if __name__ == '__main__':
    main()
