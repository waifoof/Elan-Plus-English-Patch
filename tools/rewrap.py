"""Re-wrap English text so no dialogue line is longer than the box allows.

  python3 rewrap.py [--apply] [--limit 33] FILE...

The dialogue box shows 33 characters per line (8 px each; the 34th touches the frame).
Only line breaks (￥) move; words, codes and pages stay as they are. A page is
rewrapped only when it is one plain run of text (inline codes ； ｝ ｛n ＜n ”n allowed),
it has a line over the limit, and the result still fits in 3 lines. Everything else is
listed as needing a manual edit.
"""
import json, re, sys

INLINE = re.compile(r'；|｝|｛[０-９]|＜[０-９]|”[０-９]')
# structural pieces that end a run of text
STRUCT = re.compile(r'(\{[0-9A-F]{2}\}|＠[０-９]{1,3}＿[０-９]{1,3}|＊[^＊]*＊|＋％[^％]*％：.％[^％]*％：.|'
                    r'＝：.|：ｅ|＃.|＞|＝|－)')
MAX_LINES = 3
NAME_W = 8


def width(s):
    s2 = INLINE.sub(lambda m: '' if m.group() != '；' else '\0', s)
    return len(s2.replace('\0', '')) + s2.count('\0') * NAME_W


def wrap(words, limit):
    lines, cur = [], ''
    for w in words:
        cand = w if not cur else cur + ' ' + w
        if width(cand) <= limit or not cur:
            cur = cand
        else:
            lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines


def process(en, limit):
    """Return (new_en, n_rewrapped_pages, n_unfixable_pages)."""
    parts = STRUCT.split(en)
    # parts alternates text / structural; pages are separated by a bare ＝ (not ＝：X)
    out, fixed, bad = [], 0, 0
    # collect text runs per page to know whether a page has more than one run
    page_runs = []                                   # list of lists of indexes into parts
    cur = []
    for i, p in enumerate(parts):
        if i % 2 == 1:
            if p in ('＝',) or p.startswith('＊') or p.startswith('＃') or p.startswith('＋') or p == '：ｅ' or p.startswith('＝：') or p.startswith('{'):
                page_runs.append(cur); cur = []
        elif p:
            cur.append(i)
    page_runs.append(cur)
    owner = {}
    for runs in page_runs:
        for i in runs:
            owner[i] = runs
    for i, p in enumerate(parts):
        if i % 2 == 1 or not p:
            out.append(p)
            continue
        lines = p.split('￥')
        if all(width(l) <= limit for l in lines):
            out.append(p)
            continue
        runs = owner.get(i, [i])
        if len(runs) > 1 or '　' in p or p.startswith(' '):
            bad += 1
            out.append(p)
            continue
        joined = ''
        for l in lines:
            l = l.strip()
            if joined and not joined.endswith('-'):
                joined += ' '
            joined += l                      # a line ending in '-' was a hyphenated word split at the break
        words = joined.split(' ')
        new = wrap([w for w in words if w], limit)
        if len(new) <= MAX_LINES and all(width(l) <= limit for l in new):
            out.append('￥'.join(new))
            fixed += 1
        else:
            bad += 1
            out.append(p)
    return ''.join(out), fixed, bad


def main(argv):
    apply = '--apply' in argv
    limit = 33
    if '--limit' in argv:
        limit = int(argv[argv.index('--limit') + 1])
    files = [a for a in argv if a.endswith('.json')]
    tot_fixed = tot_bad = 0
    bad_rows = []
    for f in files:
        doc = json.load(open(f, encoding='utf-8'))
        changed = False
        for r in doc['rows']:
            if r.get('skip') or not r.get('en') or r.get('choice'):
                continue
            if 'max' in r and '＠' not in r['jp'] and '￥' not in r['en']:
                continue
            new, fx, bd = process(r['en'], limit)
            tot_fixed += fx
            tot_bad += bd
            if bd:
                bad_rows.append(r['id'])
            if new != r['en']:
                r['en'] = new
                changed = True
        if apply and changed:
            json.dump(doc, open(f, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print(f'pages rewrapped: {tot_fixed}, pages needing a manual edit: {tot_bad} (in {len(bad_rows)} rows)')
    return bad_rows


if __name__ == '__main__':
    rows = main(sys.argv[1:])
    if '--list' in sys.argv:
        print('\n'.join(rows))
