"""Redraw the R2 help overlay of the conversation (Talk) screen in English.

  python3 help_labels.py [arc_dir] [out_bin_dir] [preview_png] [game_bin] [table_json]

Defaults (relative to the repository): arc_dir work/arc/OUTPUT, out_bin_dir work/text/bin,
preview (none), game_bin work/disc/GAME/GAME.BIN, table_json work/text/tables/GAME_BIN_help.json.
Run it after labels.py: it reads and rewrites out_bin_dir/0514.bin (the menu atlas there already
holds the redrawn menu labels).

What the overlay is (see docs/ENGINE_NOTES.md, "Talk help overlay"):
  * Holding R2 on the Talk screen shows labelled leader lines explaining the mood panel. The labels
    are a sprite list in GAME/GAME.BIN at 0x2F974 (RAM 0x8009F974; GAME.BIN is loaded at
    0x80070000): a u32 count (51) and 12-byte sprites  u8 u, u8 v, u8 x, u8 y | u16 clut,
    u16 tpage | u16 w, u16 h  (the same layout as the staff-roll table in SIKEN.BIN). The list is
    drawn by the routine at 0x80014360 (code at 0x800795E0 passes the table); tpage bit 0x4000
    mirrors a sprite horizontally (the closing parentheses are mirrored opening ones), bit 0x8000
    vertically. The leader lines are separate line primitives.
  * Sprites 0-46 are text in the 0514 menu atlas (tpage 0x3C = VRAM 768,256, CLUT 0x3EBC =
    VRAM 960,250, a grey ramp: 1 near-black ... 14 near-white). They are word and single-kana
    fragments shared with the mood panel (気分, 普通, 表示, 変化, 好感度, 育成結果), so translating
    those cells for the panel produced mixed lines like "Rapport レベル (6 Stag)". Sprites 47-50
    are the four coloured arcs of the mood legend (CLUT 0x3C7C).
  * The fragments used only by this overlay sit in the menu atlas at u48-127 v112-175
    (ゲージ 振 切ると / レベル 哀しい / 赤 怒 緑 青 黄 / 楽 が によ 6 ( 8 り); u0-47 v164-206 is empty
    in the original atlas.

This tool clears that fragment block, draws one cell per English word group there and in the
empty area (white text, index 14, with a 1-px dark outline, index 1, on a transparent ground,
like the original glyphs), and writes a new sprite list: the English lines word by word (words
used on several lines share a cell), the original ▲/▼ sprites, then the four arcs. The new list
is shorter than the original and fits its space; the count is rewritten.

Output table_json: {"module": "GAME/GAME.BIN", "patches": [{"off", "orig", "new"}]};
patch_game(data) applies it (build_patch.py, after the pointer-table step).
"""
import os as _os, sys as _sys
_sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))
from fontpath import FONTS
import json, os, struct, sys
import numpy as np
from PIL import Image, ImageDraw, ImageFont

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ARC = os.path.join(_ROOT, 'work', 'arc', 'OUTPUT')
OUT = os.path.join(_ROOT, 'work', 'text', 'bin')
GAME = os.path.join(_ROOT, 'work', 'disc', 'GAME', 'GAME.BIN')
TABLE_JSON = os.path.join(_ROOT, 'work', 'text', 'tables', 'GAME_BIN_help.json')

TABLE_OFF = 0x2F974          # u32 count + count x 12-byte sprites
N_ORIG = 51
MENU_BASE = 0x1F4D4          # 0514: pixels of the 4bpp menu atlas (VRAM 768,256), 128 bytes per row
ROW = 128
ATLAS_ROWS = 240
TPAGE = 0x3C
FLIP = 0x4000
CLUT_TEXT = 0x3EBC
INK, EDGE = 14, 1            # CLUT row 10: 14 = efefef, 1 = 101010

FONT = FONTS + '/truetype/crosextra/Carlito-Bold.ttf'   # Inter SemiBold 11 / Carlito 12 do not fit the free space
SIZE = 11
SPACE = 4                    # px between the ink of two words
CAP_ROW = 2                  # cap top row inside a cell (row 0 = outline, row 1 = tall ascenders/parens)

# Regions of the menu atlas the cells are packed into (u0, v0, u1, v1 inclusive).
CLEAR = (48, 112, 127, 175)              # the overlay-only Japanese fragments: cleared first
REGIONS = [CLEAR, (0, 165, 47, 206)]     # + an area that is empty in the original atlas

# Original sprites kept as they are (index in the original list): ▲ and ▼, the four arcs.
UP, DOWN = 3, 2
ARCS = [47, 48, 49, 50]

# The English lines: (start x of the first ink pixel, cap-top row on screen, items).
# Item: a word cell (text), (text, 'flip') for a mirrored cell, ('keep', n) for an original sprite.
# Words follow each other SPACE px apart; items in a tuple group
# ('tight', ...) touch with 1 px between them. Screen rows of the leader lines: y36 (under line 1),
# y60 (between lines 2 and 3), y104 (under "Mood gauge"), y209 (under the last line).
LINES = [
    # 好感度レベル（６段階）: points at the rapport word at the top of the panel
    ('Rapport level (6 stages)', 72, 25, ['Rapport', 'level', ('tight', '(', '6'), ('tight', 'stages', ('(', 'flip'))]),
    # 好感度レベル内ゲージ（振り切るとレベルが変化）
    ('Rapport gauge', 56, 49, ['Rapport', 'gauge']),
    ('(level changes at either end)', 48, 66,
     [('tight', '(', 'level'), 'changes', ('tight', 'at either end', ('(', 'flip'))]),
    # 気分ゲージ and the legend around the coloured arcs (緑 普通 / 赤 怒り / 青 哀しい / 黄 楽しい);
    # the words are the panel's own (NORMAL / ANGER / SAD / HAPPY); the arcs show the colours.
    ('Mood gauge', 32, 93, ['Mood', 'gauge']),
    ('Normal', 110, 112, ['Normal']),
    ('Anger', 50, 128, ['Anger']),
    ('Sad', 104, 144, ['Sad']),
    ('Happy', 162, 128, ['Happy']),
    # 気分により育成結果が変化（▲▼表示）
    ('Mood changes training results', 40, 164, ['Mood', 'changes', 'training results']),
    ('(shown as ▲▼)', 38, 178, [('tight', '(', 'shown as'), ('tight', ('keep', UP), ('keep', DOWN), ('(', 'flip'))]),
    # 気分レベル（８段階）
    ('Mood level (8 stages)', 136, 198, ['Mood', 'level', ('tight', '(', '8'), ('tight', 'stages', ('(', 'flip'))]),
]
# rightmost ink column allowed per line (leader lines / the panel start to the right)
MAX_X = {'Rapport level (6 stages)': 212, 'Rapport gauge': 214, '(level changes at either end)': 212,
         'Happy': 222, 'Mood level (8 stages)': 254}


# ------------------------------------------------------------------ rendering
def render(text):
    """-> (pix array h x w with 0 / EDGE / INK, ink x offset in the cell, cap-top row in the cell)"""
    f = ImageFont.truetype(FONT, SIZE)
    W, H = 8 * len(text) + 20, 40
    im = Image.new('L', (W, H), 0)
    d = ImageDraw.Draw(im)
    d.fontmode = '1'                     # hinted monochrome: stems on whole pixels
    d.text((4, 10), text, font=f, fill=255)
    ref = Image.new('L', (W, H), 0)
    dr = ImageDraw.Draw(ref)
    dr.fontmode = '1'
    dr.text((4, 10), 'H', font=f, fill=255)
    a = np.asarray(im) > 120
    cap = np.where(np.asarray(ref) > 120)[0].min()
    ys, xs = np.where(a)
    top = min(ys.min(), cap - (CAP_ROW - 1))
    a = a[top:ys.max() + 1, xs.min():xs.max() + 1]
    h, w = a.shape
    g = np.zeros((h + 2, w + 2), bool)
    g[1:-1, 1:-1] = a
    edge = np.zeros_like(g)
    for dy in (-1, 0, 1):
        for dx in (-1, 0, 1):
            edge |= np.roll(np.roll(g, dy, 0), dx, 1)
    pix = np.where(g, INK, np.where(edge, EDGE, 0)).astype(np.uint8)
    return pix, 1, cap - top + 1


# ------------------------------------------------------------------ atlas
def load_atlas(data):
    a = np.frombuffer(bytes(data[MENU_BASE:MENU_BASE + ATLAS_ROWS * ROW]), np.uint8).reshape(ATLAS_ROWS, ROW)
    p = np.zeros((ATLAS_ROWS, 256), np.uint8)
    p[:, 0::2] = a & 15
    p[:, 1::2] = a >> 4
    return p


def store_atlas(data, p):
    b = (p[:, 0::2] | (p[:, 1::2] << 4)).astype(np.uint8)
    data[MENU_BASE:MENU_BASE + ATLAS_ROWS * ROW] = b.tobytes()


def pack(cells, regions):
    """Shelf packing, tallest/widest first. -> {text: (u, v)}"""
    order = sorted(cells, key=lambda t: (-cells[t].shape[0], -cells[t].shape[1]))
    shelves = []            # [region index, v, height, next free u]
    pos = {}
    for t in order:
        h, w = cells[t].shape
        for s in shelves:
            r = regions[s[0]]
            if h <= s[2] and s[3] + w - 1 <= r[2]:
                pos[t] = (s[3], s[1])
                s[3] += w
                break
        else:
            for ri, r in enumerate(regions):
                v = max([s[1] + s[2] for s in shelves if s[0] == ri], default=r[1])
                if v + h - 1 <= r[3] and r[0] + w - 1 <= r[2]:
                    shelves.append([ri, v, h, r[0] + w])
                    pos[t] = (r[0], v)
                    break
            else:
                raise SystemExit(f'help_labels: no room in the atlas for {t!r} ({w}x{h})')
    return pos


# ------------------------------------------------------------------ table
def read_table(game):
    n, = struct.unpack_from('<I', game, TABLE_OFF)
    assert n == N_ORIG, f'GAME.BIN @{TABLE_OFF:X}: expected {N_ORIG} help sprites, found {n}'
    return [struct.unpack_from('<BBBBHHHH', game, TABLE_OFF + 4 + 12 * i) for i in range(n)]


def words(items):
    for it in items:
        if isinstance(it, tuple) and it and it[0] == 'tight':
            yield list(it[1:])
        else:
            yield [it]


def layout(cells, info, orig):
    """-> list of sprites (u, v, x, y, clut, tpage, w, h) and {line: (x0, x1)}"""
    out, ext = [], {}
    for name, x0, cap_y, items in LINES:
        x = x0                                  # next ink column
        first = True
        for group in words(items):
            if not first:
                x += SPACE
            first = False
            for k, it in enumerate(group):
                if k:
                    x += 1
                if isinstance(it, tuple) and it[0] == 'keep':
                    u, v, _, _, cl, tp, w, h = orig[it[1]]
                    # the ▲▼ sprites: 8x8 cells with the glyph in columns 1-5 / rows 1-6
                    out.append((u, v, x - 1, cap_y, cl, tp, w, h))
                    x += 5
                    continue
                text, flip = (it[0], True) if isinstance(it, tuple) else (it, False)
                pix = cells[text]
                h, w = pix.shape
                u, v = info[text]
                cap = CAP_ROW_OF[text]
                out.append((u, v, x - 1, cap_y - cap, CLUT_TEXT, TPAGE | (FLIP if flip else 0), w, h))
                x += w - 2
        ext[name] = (x0, x - 1)
    for i in ARCS:
        out.append(orig[i])
    return out, ext


CAP_ROW_OF = {}            # text -> cap-top row inside its cell (filled by build())


def build(data_0514, game, orig_0514=None):
    orig = read_table(game)
    texts = []
    for _, _, _, items in LINES:
        for group in words(items):
            for it in group:
                if isinstance(it, tuple) and it[0] == 'keep':
                    continue
                t = it[0] if isinstance(it, tuple) else it
                if t not in texts:
                    texts.append(t)
    cells = {}
    for t in texts:
        pix, _, cap = render(t)
        cells[t] = pix
        CAP_ROW_OF[t] = cap
    p = load_atlas(data_0514)
    o = load_atlas(orig_0514 if orig_0514 is not None else data_0514)
    for r in REGIONS:
        if r != CLEAR:
            assert not o[r[1]:r[3] + 1, r[0]:r[2] + 1].any(), f'region {r} is not empty in the original atlas'
        p[r[1]:r[3] + 1, r[0]:r[2] + 1] = 0
    pos = pack(cells, REGIONS)
    for t, (u, v) in pos.items():
        h, w = cells[t].shape
        p[v:v + h, u:u + w] = cells[t]
    store_atlas(data_0514, p)
    sprites, ext = layout(cells, pos, orig)
    assert len(sprites) <= N_ORIG
    for name, (a, b) in ext.items():
        lim = MAX_X.get(name, 228)
        assert b <= lim, f'{name!r} ends at x{b}, limit {lim}'
    for s in sprites:
        assert 0 <= s[2] <= 255 and 0 <= s[3] <= 255 and s[0] + s[6] <= 255, s
    new = struct.pack('<I', len(sprites)) + b''.join(struct.pack('<BBBBHHHH', *s) for s in sprites)
    old = bytes(game[TABLE_OFF:TABLE_OFF + len(new)])
    return sprites, ext, pos, cells, [{'off': TABLE_OFF, 'orig': old.hex(), 'new': new.hex()}]


def patch_game(data, table_json=TABLE_JSON):
    """Apply the help-overlay table patch to GAME/GAME.BIN (bytes -> bytes, same size)."""
    d = bytearray(data)
    for p in json.load(open(table_json))['patches']:
        o, old, new = p['off'], bytes.fromhex(p['orig']), bytes.fromhex(p['new'])
        assert d[o:o + len(old)] == old, f'GAME.BIN @{o:X}: unexpected bytes'
        d[o:o + len(new)] = new
    return bytes(d)


def preview(sprites, p, path):
    """The overlay text drawn from the new table and atlas, 3x, on a dark green ground."""
    grey = [0] + [min(255, 16 * i + 8) for i in range(1, 16)]
    im = Image.new('RGB', (320, 240), (30, 50, 30))
    px = im.load()
    for u, v, x, y, cl, tp, w, h in sprites:
        if cl != CLUT_TEXT:
            continue
        for j in range(h):
            for i in range(w):
                c = p[v + j, u + (w - 1 - i if tp & FLIP else i)]
                if c and x + i < 320 and y + j < 240:
                    px[x + i, y + j] = (grey[c],) * 3
    im.resize((960, 720), Image.NEAREST).save(path)


def main(arc=ARC, out=OUT, prev=None, game_path=GAME, table_json=TABLE_JSON):
    src = os.path.join(out, '0514.bin')
    if not os.path.exists(src):
        src = os.path.join(arc, '0514.bin')
    data = bytearray(open(src, 'rb').read())
    game = open(game_path, 'rb').read()
    orig = open(os.path.join(arc, '0514.bin'), 'rb').read()
    sprites, ext, pos, cells, patches = build(data, game, orig)
    os.makedirs(out, exist_ok=True)
    open(os.path.join(out, '0514.bin'), 'wb').write(bytes(data))
    os.makedirs(os.path.dirname(table_json), exist_ok=True)
    json.dump({'module': 'GAME/GAME.BIN', 'patches': patches}, open(table_json, 'w'), indent=1)
    print(f'help overlay: {len(cells)} cells, {len(sprites)} sprites (was {N_ORIG})')
    for name, (a, b) in ext.items():
        print(f'  x{a:3d}-{b:3d}  {name}')
    if prev:
        preview(sprites, load_atlas(data), prev)


if __name__ == '__main__':
    defaults = [ARC, OUT, None, GAME, TABLE_JSON]
    args = sys.argv[1:] + defaults[len(sys.argv) - 1:]
    main(*[None if x in ('', '-') else x for x in args[:5]])
