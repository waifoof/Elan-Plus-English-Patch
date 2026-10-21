"""Two-letters-per-glyph English encoding for Élan Plus.

The game font (FONT.BIN @ 0x36FA) holds JIS X 0208 level 1 in JIS order,
22 bytes per glyph (11 rows x u16, MSB-first, 12 px used). English text is
split into letter pairs; each distinct pair gets one kanji slot whose glyph
is redrawn with those two 6-px letters. Full-width characters (markup such as
＊ ￥ ＠ ＿ ０-９ and punctuation the translator keeps) pass through unchanged.
"""
import json, os, struct, sys
sys.path.insert(0, os.path.dirname(__file__))
import enfont

FONT_OFF = 0x36FA
GLYPH = 22


def jis_codes():
    codes = []
    for hi in list(range(0x81, 0xA0)) + list(range(0xE0, 0xF0)):
        for lo in range(0x40, 0xFD):
            if lo == 0x7F:
                continue
            try:
                bytes([hi, lo]).decode('shift_jis')
                codes.append(hi << 8 | lo)
            except UnicodeDecodeError:
                pass
    return codes


CODES = jis_codes()
RANK = {c: i for i, c in enumerate(CODES)}
FIRST_KANJI = RANK[0x889F]
LAST_IN_FONT = RANK[0x9872]
SLOTS = [CODES[r] for r in range(FIRST_KANJI, LAST_IN_FONT + 1)]   # usable codes
# Prefer kanji the original game never uses, then the rarest ones, so partially
# translated builds don't corrupt untranslated Japanese text.
_order = os.path.join(os.path.dirname(__file__), 'slot_order.json')
if os.path.exists(_order):
    SLOTS = json.load(open(_order))
# The renderer draws the neighbouring slots' edge rows above and below each cell. Every kanji slot's
# edge rows are blanked (patch_font), but the first and last kanji slots border non-kanji glyphs
# whose edge rows have ink (a solid bar above the first slot), so no letter pair goes there.
_EDGE = {CODES[FIRST_KANJI], CODES[LAST_IN_FONT]}
SLOTS = [c for c in SLOTS if c not in _EDGE]


RAW = __import__('re').compile(r'(\{[0-9A-F]{2}\})')


def runs(s):
    """Split into (kind, text) runs: True = ASCII text, False = full-width, 'raw' = {XX} byte."""
    out = []
    for part in RAW.split(s):
        if not part:
            continue
        if RAW.fullmatch(part):
            out.append(('raw', part))
        else:
            out.extend(_runs(part))
    return out


def _runs(s):
    out, cur, kind = [], '', None
    for ch in s:
        k = ord(ch) < 0x80
        if kind is None or k == kind:
            cur += ch
        else:
            out.append((kind, cur)); cur = ch
        kind = k
    if cur:
        out.append((kind, cur))
    return out


def pairs_of(text):
    if len(text) % 2:
        text += ' '
    return [text[i:i + 2] for i in range(0, len(text), 2)]


class PairTable:
    def __init__(self, path=None):
        self.map = {}
        if path and os.path.exists(path):
            self.map = json.load(open(path))

    def save(self, path):
        json.dump(self.map, open(path, 'w'), indent=0, sort_keys=True)

    def collect(self, strings):
        need = {}
        for s in strings:
            for is_a, t in runs(s):
                if is_a is True:
                    for p in pairs_of(t):
                        need[p] = need.get(p, 0) + 1
        bad = {c for p in need for c in p if c not in enfont.G}
        if bad:
            raise ValueError('characters missing from font: ' + ''.join(sorted(bad)))
        used = set(self.map.values())
        free = [c for c in SLOTS if c not in used]
        for p in sorted(need, key=lambda p: -need[p]):
            if p not in self.map:
                if not free:
                    raise ValueError(f'out of glyph slots ({len(SLOTS)}); {len(need)} pairs needed')
                self.map[p] = free.pop(0)
        return len(need)

    def encode(self, s):
        out = bytearray()
        for is_a, t in runs(s):
            if is_a == 'raw':
                out.append(int(t[1:3], 16))
            elif is_a:
                for p in pairs_of(t):
                    c = self.map[p]
                    out += bytes([c >> 8, c & 0xFF])
            else:
                out += t.encode('cp932')
        return bytes(out)

    def patch_font(self, font: bytes) -> bytes:
        f = bytearray(font)
        # The text renderer draws one row above and below each 11-row cell, taken from the
        # neighbouring slots. With the kanji slots now holding letter pairs or unused kanji,
        # blank the top and bottom row of every kanji slot so nothing leaks around the letters.
        for rank in range(FIRST_KANJI, LAST_IN_FONT + 1):
            o = FONT_OFF + rank * GLYPH
            struct.pack_into('>H', f, o, 0)
            struct.pack_into('>H', f, o + 10 * 2, 0)
        for p, c in self.map.items():
            o = FONT_OFF + RANK[c] * GLYPH
            for y, bits in enumerate(enfont.cell(p[0], p[1])):
                struct.pack_into('>H', f, o + y * 2, bits)
        patch_wide(f)
        return bytes(f)


# Full-width Latin letters and digits (what the name-entry Alphabet tab produces, and the digits the
# engine inserts into some texts). The original glyphs are ~7 px wide in a 12 px cell, so a name
# like "Ava" reads "A v a". Redraw them as the English letters doubled horizontally (10 px, bold),
# one row higher like the pair cells, so a name reads as one word.
WIDE = {chr(0xFF21 + i): chr(0x41 + i) for i in range(26)}
WIDE.update({chr(0xFF41 + i): chr(0x61 + i) for i in range(26)})
WIDE.update({chr(0xFF10 + i): chr(0x30 + i) for i in range(10)})


def wide_cell(ch):
    rows = []
    for y in range(11):
        bits = 0
        if y < 10:
            for x, px in enumerate(enfont.G[ch][y + 1]):
                if px == '#':
                    bits |= 0b11 << (15 - 1 - 2 * x - 1)      # columns 1..10
        rows.append(bits)
    return rows


def patch_wide(f):
    for fw, ch in WIDE.items():
        code = int.from_bytes(fw.encode('cp932'), 'big')
        o = FONT_OFF + RANK[code] * GLYPH
        for y, bits in enumerate(wide_cell(ch)):
            struct.pack_into('>H', f, o + y * 2, bits)
