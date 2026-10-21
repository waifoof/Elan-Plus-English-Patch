"""Print a script file's rows: id, [CHOICE], Japanese, and current English if any."""
import json, sys
for p in sys.argv[1:]:
    d = json.load(open(p, encoding='utf-8'))
    print(f"### entry {d.get('entry', d.get('module'))} ({d['kind']}), {len(d['rows'])} rows")
    for r in d['rows']:
        tag = '[CHOICE] ' if r.get('choice') else ''
        print(f"{r['id']}\t{tag}{r['jp']}")
        if r.get('en'):
            print(f"{'':10}\tEN: {r['en']}")
