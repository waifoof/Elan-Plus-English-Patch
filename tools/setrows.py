"""Apply translations: python3 setrows.py <file.json> <mapping.json>
mapping.json = {"<row id>": "<English with markup>" | null, ...}. Only "en"/"skip" change; null marks a row to skip."""
import json, sys
p, m = sys.argv[1], json.load(open(sys.argv[2], encoding='utf-8'))
d = json.load(open(p, encoding='utf-8'))
ids = {r['id'] for r in d['rows']}
unknown = [k for k in m if k not in ids]
if unknown:
    sys.exit(f'unknown row ids: {unknown[:5]}')
for r in d['rows']:
    if r['id'] in m:
        if m[r['id']] is None:          # null = not real text, never patch this slot
            r['skip'] = True
            r['en'] = ''
        else:
            r.pop('skip', None)
            r['en'] = m[r['id']]
json.dump(d, open(p, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
print(f'{len(m)} rows set in {p}')
