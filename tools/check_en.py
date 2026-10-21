"""Check the English-only translation files (no game disc needed; used by CI on every pull request).

  python3 check_en.py [translation_dir] [--base-ref origin/main]

1. Every row passes validate.check_row with its own English standing in for the Japanese source:
   that checks line and page limits, choice lengths, the byte budget of interface strings, the
   name-plate width and the allowed characters.
2. With --base-ref, every row's markup (voice codes, page breaks, speaker tags, labels, raw {XX}
   bytes...) must be identical to the same row at that git ref, so a change can only touch the words.
   (The full check against the Japanese runs locally in "build.py" after the text step.)
"""
import json, os, re, subprocess, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import validate

SIG = re.compile(r'＠[０-９]{1,3}＿[０-９]{1,3}|＊[^＊]*＊|＃[Ａ-Ｚａ-ｚ]|：[Ａ-Ｚａ-ｚ]|\{[0-9A-F]{2}\}|[＋％＝｝；＞”｛＜－]')
KANA_KANJI = re.compile(r'[぀-ヿ一-鿿]')


def signature(en):
    # speaker tags: only their presence/kind matters (names are English and may be fixed)
    return ['＊；＊' if t == '＊；＊' else ('＊＊' if t.startswith('＊') else t) for t in SIG.findall(en)]


def rows_of(doc):
    return {r['id']: r for r in doc.get('rows', [])}


def check_file(path, base_doc=None):
    doc = json.load(open(path, encoding='utf-8'))
    errs = []
    base = rows_of(base_doc) if base_doc else {}
    for r in doc.get('rows', []):
        en = r.get('en', '')
        if KANA_KANJI.search(re.sub(r'\{[0-9A-F]{2}\}', '', en)):
            errs.append(f"{r['id']}: Japanese characters in the English (the repository must not contain game text)")
        fake = dict(r, jp=en)
        if 'tail_len' in r:
            fake.pop('tail_len')
        for e in validate.check_row(fake):
            if 'not translated' in e and r.get('skip'):
                continue
            errs.append(f"{r['id']}: {e}")
        if base_doc is not None:
            b = base.get(r['id'])
            if b is None:
                errs.append(f"{r['id']}: row not in the base version (rows can't be added)")
            elif signature(b.get('en', '')) != signature(en):
                errs.append(f"{r['id']}: markup codes changed (only the words may change)")
            elif {k: v for k, v in b.items() if k != 'en'} != {k: v for k, v in r.items() if k != 'en'}:
                errs.append(f"{r['id']}: fields other than \"en\" changed")
    if base_doc is not None and set(base) - set(rows_of(doc)):
        errs.append(f'{os.path.basename(path)}: rows removed')
    return errs


def git_show(ref, rel):
    r = subprocess.run(['git', 'show', f'{ref}:{rel}'], capture_output=True)
    return json.loads(r.stdout.decode('utf-8')) if r.returncode == 0 else None


def main():
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    ref = sys.argv[sys.argv.index('--base-ref') + 1] if '--base-ref' in sys.argv else None
    if ref in args:
        args.remove(ref)
    root = args[0] if args else os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'translation')
    top = subprocess.run(['git', 'rev-parse', '--show-toplevel'], capture_output=True, text=True, cwd=root).stdout.strip()
    total, nfiles = 0, 0
    for kind in ('event', 'mk', 'rec', 'code'):
        kd = os.path.join(root, kind)
        for name in sorted(os.listdir(kd)) if os.path.isdir(kd) else []:
            if not name.endswith('.json'):
                continue
            p = os.path.join(kd, name)
            base = None
            if ref:
                base = git_show(ref, os.path.relpath(os.path.abspath(p), top)) or {}
            errs = check_file(p, base if ref else None)
            nfiles += 1
            for e in errs:
                print(f'{kind}/{name}: {e}')
            total += len(errs)
    print(f'{nfiles} files, {total} problems')
    sys.exit(1 if total else 0)


if __name__ == '__main__':
    main()
