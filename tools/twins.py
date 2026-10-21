"""Find rows whose Japanese is identical but whose English differs (across all files).

  python3 twins.py [--kind event] [--min 2]      report groups, most-common English first

Only story/interface rows (event, code) are compared: conversation (mk) and mail rows hold whole
topics and are compared as a whole too, but rarely repeat.
"""
import json, glob, os, sys, re
from collections import defaultdict, Counter

WORK = os.path.join(os.path.dirname(__file__), '..', 'work', 'text')   # full text from "build.py prepare"


def norm_jp(s):
    return s.strip()


def groups(kinds=('event',)):
    g = defaultdict(list)
    for k in kinds:
        for p in sorted(glob.glob(os.path.join(WORK, k, '*.json'))):
            for r in json.load(open(p, encoding='utf-8'))['rows']:
                if r.get('skip') or not r.get('en') or len(r['jp']) < 6:
                    continue
                g[norm_jp(r['jp'])].append((os.path.relpath(p, WORK), r['id'], r['en']))
    return g


if __name__ == '__main__':
    kinds = sys.argv[sys.argv.index('--kind') + 1].split(',') if '--kind' in sys.argv else ['event']
    out = []
    for jp, rows in groups(kinds).items():
        c = Counter(e for _, _, e in rows)
        if len(c) > 1:
            out.append((jp, rows, c))
    out.sort(key=lambda x: -len(x[1]))
    print(f'{len(out)} Japanese lines with differing English copies')
    for jp, rows, c in out:
        print(f'\n[{len(rows)} copies, {len(c)} versions] {rows[0][1]}')
        for e, n in c.most_common():
            files = sorted({f.split("/")[-1][:4] for f, _, x in rows if x == e})
            print(f'   {n:3d}x {e[:110]!r}  files {",".join(files[:12])}{"..." if len(files) > 12 else ""}')
