"""Re-insert {XX} raw-byte tokens that a translation dropped, anchored on the
preceding markup code (same index in the jp and en code sequences).
  python3 fix_raw.py <file.json> [...]"""
import json, re, sys, os
sys.path.insert(0, os.path.dirname(__file__))
import validate as v
RAW = re.compile(r'\{[0-9A-F]{2}\}')
NONRAW = re.compile(r'＃[Ａ-Ｚａ-ｚ]|：[Ａ-Ｚａ-ｚ]|[＋％＝｝；＞]')


def fix(jp, en):
    if RAW.findall(en) == RAW.findall(jp):
        return en
    en = RAW.sub('', en)
    # insertion plan from jp: list of (k_nonraw_codes_before, rawtext)
    plan, k, pos = [], 0, 0
    toks = [(m.start(), m.end(), m.group()) for m in re.finditer(NONRAW.pattern + r'|\{[0-9A-F]{2}\}', jp)]
    for s, e, t in toks:
        if RAW.fullmatch(t):
            if plan and plan[-1][0] == k and plan[-1][2] == s:
                plan[-1] = (k, plan[-1][1] + t, e)
            else:
                plan.append((k, t, e))
        else:
            k += 1
    ends = [m.end() for m in NONRAW.finditer(en)]
    for k, raw, _ in reversed(plan):
        at = ends[k - 1] if k > 0 else 0
        en = en[:at] + raw + en[at:]
    return en


if __name__ == '__main__':
    for p in sys.argv[1:]:
        d = json.load(open(p, encoding='utf-8')); n = 0
        for r in d['rows']:
            if r.get('en') and RAW.findall(r['en']) != RAW.findall(r['jp']):
                if NONRAW.findall(r['en']) == NONRAW.findall(r['jp']):
                    r['en'] = fix(r['jp'], r['en']); n += 1
        json.dump(d, open(p, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
        bad = sum(1 for r in d['rows'] if v.check_row(r) and r.get('en'))
        print(f'{os.path.basename(p)}: raw tokens restored in {n} rows; rows still failing: {bad}')
