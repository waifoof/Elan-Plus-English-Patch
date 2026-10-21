"""Validate translated rows against the original's markup and the box limits.

  python3 validate.py <file.json> [...]      (prints problems, exit 1 if any)
"""
import json, re, sys, os
sys.path.insert(0, os.path.dirname(__file__))
import enfont

LINE_MAX = 32
LINES_PER_PAGE = 3
CHOICE_MAX = 24
PLATE_MAX = 8
VOICE = re.compile(r'＠[０-９]{1,3}＿[０-９]{1,3}')
PLATE = re.compile(r'＊([^＊]*)＊')
ALLOWED_FW = set('＊＠＿０１２３４５６７８９￥＝－　；｝｛＜')
CODES = re.compile(r'＠[０-９]{1,3}＿[０-９]{1,3}|｛[０-９]|＜[０-９]|[；｝＝]')
NAME_WIDTH = 8          # ； = player's name (4 full-width cells)


def strip_markup(s):
    s = re.sub(r'[｛＜][０-９]', '', s)
    s = VOICE.sub('', s)
    s = PLATE.sub('', s)
    return s


def encoded_len(s):
    """Bytes the pair encoder will produce: ASCII runs round up to even, full-width = 2."""
    n, run = 0, 0
    for c in s:
        if ord(c) < 0x80:
            run += 1
        else:
            n += (run + 1) // 2 * 2 + 2
            run = 0
    return n + (run + 1) // 2 * 2


MK_CODES = re.compile(r'＃[Ａ-Ｚａ-ｚ]|：[Ａ-Ｚａ-ｚ]|[＋％＝｝；＞]|\{[0-9A-F]{2}\}')
RAWTOK = re.compile(r'\{[0-9A-F]{2}\}')
MK_OPT_MAX = 28


def check_mk(jp, en):
    errs = []
    # final block: bytes after the last end-label terminator are file padding; must be copied verbatim
    k = jp.rfind('＞{00}')
    if k >= 0:
        tail = jp[k + len('＞{00}'):]
        # only the file's last row ends in the binary pointer table (no Japanese text in it);
        # in other rows the text after ＞{00} is the next topic's opening line and is checked
        if tail and re.search(r'\{(?!00\})[0-9A-F]{2}\}', tail):
            # binary trailer of the final block: the build re-uses the original bytes,
            # so whatever the translation has after its last ＞{00} is ignored
            jp = jp[:len(jp) - len(tail)]
            ke = en.rfind('＞{00}')
            if ke < 0:
                errs.append('final block must keep its closing ＞{00}')
            else:
                en = en[:ke + len('＞{00}')]
    if MK_CODES.findall(jp) != MK_CODES.findall(en):
        a, b = MK_CODES.findall(jp), MK_CODES.findall(en)
        k = next((i for i in range(min(len(a), len(b))) if a[i] != b[i]), min(len(a), len(b)))
        errs.append(f'markup sequence differs at code #{k}: jp {a[k:k+4]} / en {b[k:k+4]}')
    jp_pl, en_pl = PLATE.findall(jp), PLATE.findall(en)
    if len(jp_pl) != len(en_pl):
        errs.append(f'speaker tag count differs ({len(jp_pl)} vs {len(en_pl)})')
    else:
        for a, b in zip(jp_pl, en_pl):
            if (a == '；') != (b == '；'):
                errs.append('player tag ＊；＊ must stay as is')
            if len(b) > PLATE_MAX:
                errs.append(f'speaker tag too long: {b!r}')
    bad = sorted({c for c in RAWTOK.sub('', en) if (ord(c) < 0x80 and c not in enfont.G) or (ord(c) >= 0x80 and c not in MK_ALLOWED)})
    if bad:
        errs.append('characters not allowed: ' + ' '.join(repr(c) for c in bad))
    # choice options: ％text％：X
    for o in re.findall(r'％([^％]*)％：', en):
        if len(o.replace('；', '')) + o.count('；') * NAME_WIDTH > MK_OPT_MAX:
            errs.append(f'choice option too long ({len(o)} > {MK_OPT_MAX}): {o!r}')
        if '￥' in o:
            errs.append('choice option must be one line')
    # message text: drop choice blocks, labels, gotos, tags; then check pages/lines
    t = re.sub(r'＋％[^％]*％：.％[^％]*％：.', '\n', RAWTOK.sub('\n', en))
    t = re.sub(r'＝：.|＃.|＊[^＊]*＊|｝', '\n', t)
    for msg in t.split('\n'):
        for page in msg.split('＝'):
            lines = page.split('￥')
            if len(lines) > LINES_PER_PAGE:
                errs.append(f'{len(lines)} lines on one page (max {LINES_PER_PAGE}): {page[:40]!r}')
            for line in lines:
                w = len(line.replace('；', '')) + line.count('；') * NAME_WIDTH
                if w > LINE_MAX:
                    errs.append(f'line {w} chars (max {LINE_MAX}): {line!r}')
    return errs


MK_ALLOWED = set('＊＃：＋％＝｝；＞￥') | {chr(c) for c in range(ord('Ａ'), ord('Ｚ') + 1)} | {chr(c) for c in range(ord('ａ'), ord('ｚ') + 1)}


def check_rec(r):
    jp, en = r['jp'], r['en']
    if r.get('tail'):
        jp = jp[:len(jp) - len(r['tail'])]
    errs = []
    raw = r'\{[0-9A-F]{2}\}'
    if re.findall(raw, jp) != re.findall(raw, en):
        errs.append('raw {XX} tokens differ: jp %s / en %s' % (re.findall(raw, jp)[:8], re.findall(raw, en)[:8]))
    bad = sorted({c for c in re.sub(raw, '', en) if (ord(c) < 0x80 and c not in enfont.G) or (ord(c) >= 0x80 and c not in ALLOWED_FW | set('＜＞'))})
    if bad:
        errs.append('characters not allowed: ' + ' '.join(repr(c) for c in bad))
    js, es_ = jp.split('{00}{00}'), en.split('{00}{00}')
    for n, (a, b) in enumerate(zip(js, es_)):
        al, bl = a.split('￥'), b.split('￥')
        if len(bl) > len(al):
            errs.append(f'message {n + 1}: {len(bl)} lines, Japanese has {len(al)}')
        lim = min(34, 2 * max(len(re.sub(raw, '', x)) for x in al))
        for ln, line in enumerate(bl):
            w = len(line.replace('　', '  ').replace('＜', ' ').replace('＞', ' '))
            if w > lim:
                errs.append(f'message {n + 1} line {ln + 1}: {w} chars (max {lim})')
    return errs


def check_row(r):
    jp, en = r['jp'], r.get('en', '')
    errs = []
    if r.get('skip'):
        return []
    if not en:
        return ['not translated']
    if ':b' in r['id']:                  # markup dialogue block (files 930-977)
        return check_mk(jp, en)
    if ':r' in r['id']:                  # mail record (files 834-843)
        return check_rec(r)
    if 'max' in r:                       # interface string written in place
        allowed = ALLOWED_FW | set('＞”')
        bad = sorted({c for c in en if (ord(c) < 0x80 and c not in enfont.G) or (ord(c) >= 0x80 and c not in allowed)})
        for code in '＞”｛；':
            if jp.count(code) != en.count(code):
                errs.append(f'code {code} count differs ({jp.count(code)} vs {en.count(code)})')
        if bad:
            errs.append('characters not allowed: ' + ' '.join(repr(c) for c in bad))
        if encoded_len(en) > r['max']:
            errs.append(f"too long: {encoded_len(en)} bytes, slot holds {r['max']} (about {r['max']} letters)")
        if '＠' not in jp and '￥' in en:     # help pop-ups, captions: line width only
            for line in re.sub(r'”.|＊[^＊]*＊|[｝＞]', '', en).replace('＝', '￥').split('￥'):
                if len(line.replace('　', '  ')) > LINE_MAX:
                    errs.append(f'line {len(line)} chars (max {LINE_MAX}): {line[:40]!r}')
        if '＠' in jp:                     # voiced dialogue stored in a code module
            if CODES.findall(jp) != CODES.findall(en):
                errs.append('engine codes differ: jp %s / en %s' % (CODES.findall(jp)[:6], CODES.findall(en)[:6]))
            if re.findall(r'”.', jp) != re.findall(r'”.', en):
                errs.append('expression codes ”n differ')
            for pn, page in enumerate(re.sub(r'”.|＠[０-９]{1,3}＿[０-９]{1,3}|＊[^＊]*＊', '', en).split('＝')):
                for line in page.split('￥'):
                    if len(line) > LINE_MAX:
                        errs.append(f'page {pn + 1}: line {len(line)} chars (max {LINE_MAX})')
                if page.count('￥') >= LINES_PER_PAGE:
                    errs.append(f'page {pn + 1}: more than {LINES_PER_PAGE} lines')
        return errs
    bad = sorted({c for c in en if (ord(c) < 0x80 and c not in enfont.G) or (ord(c) >= 0x80 and c not in ALLOWED_FW)})
    if bad:
        errs.append('characters not allowed: ' + ' '.join(repr(c) for c in bad))
    if r.get('choice'):
        if len(en) > CHOICE_MAX:
            errs.append(f'choice too long ({len(en)} > {CHOICE_MAX})')
        if any(c in en for c in '￥＝＊＠'):
            errs.append('choice must not contain markup')
        return errs
    if CODES.findall(jp) != CODES.findall(en):
        errs.append('engine codes differ (must match in order): jp %s / en %s' % (CODES.findall(jp), CODES.findall(en)))
    jp_pl, en_pl = PLATE.findall(jp), PLATE.findall(en)
    if len(jp_pl) != len(en_pl):
        errs.append(f'name plate count differs ({len(jp_pl)} vs {len(en_pl)})')
    else:
        for a, b in zip(jp_pl, en_pl):
            if (a == '') != (b == ''):
                errs.append('name plate emptiness differs')
            if len(b) > PLATE_MAX:
                errs.append(f'name plate too long: {b!r}')
    if jp.count('；') != en.count('；'):
        errs.append(f"player-name codes ； differ ({jp.count('；')} vs {en.count('；')})")
    if jp.count('｝') != en.count('｝'):
        errs.append(f"pause codes ｝ differ ({jp.count('｝')} vs {en.count('｝')})")
    if jp.count('＝') != en.count('＝'):
        errs.append(f"page breaks ＝ differ ({jp.count('＝')} vs {en.count('＝')})")
    if jp.startswith(('－', '＊＊－')) != en.startswith(('－', '＊＊－')):
        errs.append('caption markers (－) differ')
    for pn, page in enumerate(strip_markup(en).split('＝')):
        lines = page.split('￥')
        if len(lines) > LINES_PER_PAGE:
            errs.append(f'page {pn + 1}: {len(lines)} lines (max {LINES_PER_PAGE})')
        for ln, line in enumerate(lines):
            w = len(line.replace('－', '').replace('　', '  ').replace('；', '').replace('｝', '')) + line.count('；') * NAME_WIDTH
            if w > LINE_MAX:
                errs.append(f'page {pn + 1} line {ln + 1}: {w} chars (max {LINE_MAX})')
    return errs


def check_file(path):
    doc = json.load(open(path, encoding='utf-8'))
    probs = []
    for r in doc['rows']:
        for e in check_row(r):
            probs.append((r['id'], e))
    return probs


if __name__ == '__main__':
    bad = 0
    for p in sys.argv[1:]:
        probs = check_file(p)
        untranslated = sum(1 for _, e in probs if e == 'not translated')
        other = [(i, e) for i, e in probs if e != 'not translated']
        print(f'{os.path.basename(p)}: {len(other)} problems, {untranslated} untranslated rows')
        for i, e in other:
            print(f'   {i}  {e}')
        bad += len(other) + untranslated
    sys.exit(1 if bad else 0)
