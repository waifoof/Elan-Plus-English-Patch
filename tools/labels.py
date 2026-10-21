"""Redraw the Japanese location/name labels in the 4bpp UI atlas with English.

The atlas (256 px wide, 4bpp, 128 bytes per row) exists twice in OUTPUT.BIN:
  entry 0514 @ 0x17AB4 and entry 0847 @ 0x220 (row 0 = VRAM texture row 0).
Each label is redrawn inside its original glyph box, using the original
per-row gradient colour index, with a 1 px dark shadow.

  python3 labels.py <arc_dir> <out_bin_dir> [preview.png]
"""
import os as _os, sys as _sys
_sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))
from fontpath import FONTS
import os, sys
from collections import Counter
sys.path.insert(0, os.path.dirname(__file__))
import enfont

COPIES = {514: 0x17AB4, 847: 0x220}
ROW = 128

# (x0, x1, y0, y1, english[, clear box[, ink() options]])
# All location labels use hinted monochrome rendering for the Carlito fallback (mono=True).
M = {'mono': True}
LABELS = [
    (2, 61, 43, 53, 'Indoor Gym', (2, 61, 43, 53), M),
    (66, 125, 43, 53, 'Weight Rm', (66, 125, 43, 53), M),
    (132, 167, 43, 53, 'Archive*', (132, 167, 43, 53), M),
    (172, 207, 43, 53, 'Maint.', (172, 207, 43, 53), M),
    (212, 247, 43, 53, 'Hangar', (212, 247, 43, 53), M),
    (4, 39, 56, 70, 'Lab', (4, 39, 56, 70), M),
    (50, 109, 56, 70, 'Flight Rm', (50, 109, 56, 70), M),             # 航行演習場 = Flight Training Room (STYLE_GUIDE)
    (112, 159, 56, 70, 'High-G Rm', (110, 159, 56, 70), M),   # game window starts x112; Flight Rm's ends x111
    (164, 222, 56, 70, 'My Room', (164, 222, 56, 70), M),
    (1, 71, 72, 87, 'By Comm Ctr', (1, 71, 72, 87), M),
    (76, 142, 72, 87, "Natsuno's Rm", (76, 142, 72, 87), M),
    (149, 172, 72, 87, 'Hall', (149, 172, 72, 87), M),
    (178, 238, 72, 87, 'Commons', (178, 238, 72, 87), M),
    (3, 77, 89, 101, 'Monitor Room', (3, 77, 89, 101), M),
    (84, 107, 89, 101, 'Cafe', (84, 107, 89, 101), M),
    (116, 189, 89, 101, 'Shower Room', (116, 189, 89, 101), M),
    (194, 253, 89, 101, 'Env. Zone', (194, 253, 89, 101), M),
    (2, 72, 104, 116, 'Comm Center', (2, 72, 104, 116), M),
    (76, 146, 104, 116, 'Medical Room', (75, 146, 104, 116), M),   # the old メ outline reached x75
    (151, 228, 104, 116, 'Meeting Room*', (147, 230, 104, 116), M),   # narrow + margin: the M touched the plate border
    (42, 121, 136, 148, 'By Control Ctr', (42, 121, 136, 148), M),
    (122, 184, 136, 148, 'Grav. Block', (122, 184, 136, 148), M),
    (144, 180, 176, 190, 'Moving', (144, 180, 176, 190), M),
    (184, 213, 176, 190, 'Port', (184, 218, 176, 190), M),   # the old 港 reached x218
]
# name tags: see NAMES below

# training-stat labels on grey panels: (x0, x1, y0, y1, text); bg 4, glyph 1, sparkle 15
STATS = [
    (0, 35, 177, 189, 'Stam'), (0, 35, 192, 204, 'Str'), (0, 35, 208, 220, 'Int'), (0, 35, 224, 237, 'Tech'),
    (40, 75, 177, 189, 'Pilot'), (40, 75, 192, 204, 'Sense'), (40, 75, 208, 220, 'Judge'), (40, 75, 224, 237, 'Grit'),
]


# Second texture in entry 0514 (facility/menu panel atlas, VRAM x=768 words, y=256),
# base 0x1F4D4, 246 rows. Boxes are the measured text extents; the text is
# stretched/squeezed vertically to the box height.
MENU_BASE = 0x1F4D4
MENU = [
    (2, 45, 3, 14, 'Rest', (0, 45, 1, 16)), (47, 87, 3, 14, 'Load'), (89, 132, 3, 14, 'Save'),
    (136, 172, 1, 12, 'Rapport*', {'ink': M}),
    (178, 229, 2, 14, 'Leave', (176, 230, 1, 15)),        # old 立ち去る bits at x176-177 y14, x215-216 y15, x230 y9-12
    (0, 86, 19, 31, 'Send Mail'),
    (88, 171, 19, 31, 'Exam Info', (88, 171, 18, 31)),     # 試験内容確認 started on row 18
    (178, 219, 18, 30, 'Talk', (178, 222, 18, 31)),        # old 話す bits at x220-222 y20-21, x179 y31
    # The training buttons are two sprites side by side: the type cell (Solo x184-214 / Joint x216-246,
    # 31 px each) and then the left 80 px of this cell. "Solo   Start Training" read as one run-on
    # phrase (play-tester W), so the buttons now read "Solo Training" / "Joint Training": the type word
    # is right-aligned 1 px short of its cell's edge and "Training" starts 5 px into this one (a clear
    # word space), all three with the cap top on row 36.
    (5, 78, 34, 46, 'Training', (0, 111, 34, 47), {'align': 'left', 'ink': {'top': 36, 'padb': False}}),   # row 47: old 開始 bits above the R2 icon
    (112, 182, 35, 46, 'Cancel'),
    (184, 213, 34, 46, 'Solo', (184, 214, 35, 47), {'align': 'right', 'ink': {'top': 36}}),
    (216, 245, 34, 46, 'Joint', (216, 246, 34, 47), {'align': 'right', 'ink': {'top': 36}}),    # 共同 reached rows 46-47
    (3, 77, 81, 89, 'Candidates', (0, 81, 80, 92)),   # whole dark box: old glyph bits sat at x2 and x78-80
    # 段階内: the g hangs into rows 89-91 so "Stage" gets the same 11 px size and cap top as Candidates
    (89, 122, 81, 91, 'Stage', (89, 122, 81, 91), {'ink': {'padb': False}}),
    (50, 125, 98, 107, 'Exam Results', (50, 125, 97, 107)),   # natural 10-row height: an 11-row stretch doubles the top row, which the game shows as dots
    # DejaVu Sans Condensed with hinted mono rendering: Carlito 10 ran "kly" together (review item 6)
    (140, 212, 87, 96, 'Weekly Results', (140, 212, 84, 97),
     {'ink': {'mono': True, 'padb': False, 'maxsize': 10, 'fonts': [FONTS + '/truetype/dejavu/DejaVuSansCondensed.ttf']}}),   # drawn under 'Exam Results' on that screen: rows <87 peek out above it
    (136, 183, 156, 169, 'Results', (134, 185, 154, 173)),
    # mood cells: rows with no dark pixel in the old glyph had been cleared to 0 (transparent); force bg 1
    (48, 71, 177, 187, 'Mood', {'bg': 1, 'ink': M}), (48, 71, 193, 203, 'Show', {'bg': 1, 'ink': M}),
    (48, 71, 209, 219, 'Okay', {'bg': 1, 'ink': M}), (48, 71, 225, 235, 'Shift*', {'bg': 1, 'ink': M}),
]


def redraw_menu(atlas):
    problems = []
    for x0, x1, y0, y1, text, *extra in MENU:
        opt = next((e for e in extra if isinstance(e, dict)), {})
        clr = [e for e in extra if isinstance(e, tuple)]
        pts, prob = ink(text, x0, x1, y0, y1, align=opt.get('align', 'center'), **opt.get('ink', {}))
        if prob:
            problems.append(prob)
            continue
        fill, bg = {}, {}
        for y in range(y0, y1 + 1):
            row = [atlas.get(x, y) for x in range(x0, x1 + 1)]
            c = Counter(v for v in row if v >= 6)
            if c:
                fill[y] = max(v for v, n in c.items() if n >= 2) if any(n >= 2 for n in c.values()) else max(c)
            bg[y] = Counter(v for v in row if v <= 2).most_common(1)[0][0] if any(v <= 2 for v in row) else 0
            if 'bg' in opt:
                bg[y] = opt['bg']
        hi = max(fill.values()) if fill else 15
        cx0, cx1, cy0, cy1 = clr[0] if clr else (x0, x1, y0, y1)
        for y in range(cy0, cy1 + 1):
            b = bg.get(y, bg[y0] if y < y0 else bg[y1])
            for x in range(cx0, cx1 + 1):
                atlas.put(x, y, b)
        shade(atlas, pts, lambda y: fill.get(y, hi), opt.get('sh', 3), x1, y1)
    return problems


# dark text on a light panel: (x0, x1, y0, y1, text)
DARK = [(116, 144, 25, 35, 'Sent')]


HELP_GLYPHS = {
    'H': ['#...#', '#...#', '#####', '#...#', '#...#', '#...#'],
    'E': ['#####', '#....', '####.', '#....', '#....', '#####'],
    'L': ['#....', '#....', '#....', '#....', '#....', '#####'],
    'P': ['####.', '#...#', '#...#', '####.', '#....', '#....'],
}


def redraw_help(atlas):
    """'HELP' next to the R2 icon (menu atlas x101-139): the game shows only rows ~48-55 of this
    sprite, so the letters are 6 px caps (light fill e, dark outline 1) like the original."""
    x0, x1, y0, y1 = 101, 139, 46, 55
    for y in range(y0, y1 + 1):
        for x in range(x0, x1 + 1):
            atlas.put(x, y, 0)
    for y in range(47, 56):          # the outlines of で (x100) and プ (x140) sat just outside the box
        atlas.put(100, y, 0)
        atlas.put(140, y, 0)
    word = 'HELP'
    w = len(word) * 5 + (len(word) - 1)
    left, top = x0 + (x1 - x0 + 1 - w) // 2, 49
    pts = set()
    for n, ch in enumerate(word):
        for ry, row in enumerate(HELP_GLYPHS[ch]):
            for rx, c in enumerate(row):
                if c == '#':
                    pts.add((left + n * 6 + rx, top + ry))
    for (x, y) in pts:
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                q = (x + dx, y + dy)
                if q not in pts and x0 <= q[0] <= x1 and y0 <= q[1] <= y1:
                    atlas.put(q[0], q[1], 1)
    for (x, y) in pts:
        atlas.put(x, y, 14)


def redraw_dark(atlas):
    for x0, x1, y0, y1, text in DARK:
        c = Counter(atlas.get(x, y) for y in range(y0, y1 + 1) for x in range(x0, x1 + 1))
        bg = c.most_common(1)[0][0]
        ink_i = min(c, key=lambda v: (v == 0, v))      # darkest non-zero index used by the old glyphs
        pts, prob = ink(text, x0, x1, y0, y1, shadow=False)
        for y in range(y0, y1 + 1):
            for x in range(x0, x1 + 1):
                atlas.put(x, y, bg)
        if pts:
            shade(atlas, pts, lambda y: ink_i, None, x1, y1)


def redraw_stats(atlas):
    for x0, x1, y0, y1, text in STATS:
        pts, prob = ink(text, x0, x1, y0, y1)
        for y in range(y0, y1 + 1):
            for x in range(x0, x1 + 1):
                atlas.put(x, y, 4)
        if not pts:
            continue
        for (x, y) in pts:
            if (x + 1, y + 1) not in pts and x + 1 <= x1 and y + 1 <= y1:
                atlas.put(x + 1, y + 1, 2)                  # soft shadow
        for (x, y) in pts:
            atlas.put(x, y, 1 if (x, y - 1) in pts else 15)  # white sparkle at the top of each stroke



def glyph_cols(ch):
    g = enfont.G[ch]
    if ch == ' ':
        return [[False] * 11] * 3
    cols = [[g[y][x] == '#' for y in range(11)] for x in range(5)]
    while cols and not any(cols[0]):
        cols.pop(0)
    while cols and not any(cols[-1]):
        cols.pop()
    return cols


def narrow(cols):
    """Squeeze a 5-column glyph to 4 columns by OR-ing its two middle columns."""
    if len(cols) < 5:
        return cols
    mid = [a or b for a, b in zip(cols[1], cols[2])]
    return [cols[0], mid] + cols[3:]


# ---- TrueType label renderer (v0.9): crisp letters at their natural size instead of the
# stretched 5x10 pixel font. '*' suffix = tight box: use the narrower font first.
TTF_WIDE = FONTS + '/opentype/inter/Inter-SemiBold.otf'
TTF_NARROW = FONTS + '/truetype/crosextra/Carlito-Bold.ttf'


SOFT_MIN = 100
LAST = {}      # text -> (font file, size) of the last ink() call, for the build log


def ink(text, x0, x1, y0, y1, shadow=True, maxsize=11, align='center', font=None,
        mono=False, minsize=8, fonts=None, padb=True, top=None, soft=None):
    """Pixels to light for `text` centred in the box -> (set of (x, y), None) or (None, problem).

    Opt-in extras (defaults keep the v0.9 behaviour, which tim_labels.py also uses):
      mono    render TrueType fonts (Carlito) with FreeType's hinted monochrome rasteriser instead of
              thresholding the anti-aliased one: stems and gaps snap to whole pixels, so i dots stay apart
              from their stems at 10-11 px. (Inter is CFF and gets no hinting; it stays anti-aliased.)
      fonts   explicit list of font paths to try at each size (overrides the Inter-then-Carlito order).
      minsize smallest size tried.
      padb    False: the drop shadow may hang one row below y1 (shade() clips it), so the ink itself can
              use the full box height.
      top     put the reference cap top ('H') on this row instead of centring vertically; the
              same row for every label of a set gives them one baseline.
      soft    a set: filled with the pixels of coverage soft..120 next to the ink (the grey edge
              pixels the kana have), not counted for fitting.
    """
    from PIL import Image, ImageDraw, ImageFont
    import numpy as np
    narrow_first = text.endswith('*')
    text = text.rstrip('*')
    W, H = x1 - x0 + 1, y1 - y0 + 1
    pad = 1 if shadow else 0
    padv = pad if padb else 0
    order = [TTF_WIDE, TTF_NARROW]          # one look everywhere; the narrow font only when Inter can't fit
    if narrow_first:
        order = [TTF_NARROW, TTF_WIDE]  # '*' suffix: tight box, the narrow font is preferred
    if font == 'narrow':
        order = [TTF_NARROW]
    if fonts:
        order = list(fonts)
    best = None
    for size in range(maxsize, minsize - 1, -1):
        for path in order:
            f = ImageFont.truetype(path, size)
            hint = mono and not path.endswith('.otf')
            im = Image.new('L', (W * 3 + 20, H * 3 + 20), 0)
            d = ImageDraw.Draw(im)
            ref = Image.new('L', im.size, 0)
            dr = ImageDraw.Draw(ref)
            if hint:
                d.fontmode = dr.fontmode = '1'
            d.text((4, 4), text, font=f, fill=255)
            dr.text((4, 4), 'Hg' if any(c in text for c in 'gjpqy') else 'H', font=f, fill=255)
            g = np.asarray(im)
            a = g > 120
            r = np.asarray(ref) > 120
            if not a.any():
                continue
            ys, xs = np.where(a)
            ry, _ = np.where(r)
            if top is not None:
                capt = ry.min()
                # rows used relative to the cap top: must stay inside y0..y1
                lo, hi = top + ys.min() - capt, top + ys.max() - capt
                if xs.max() - xs.min() + 1 + pad <= W and lo >= y0 and hi + padv <= y1:
                    best = (a, xs.min(), capt, xs.max() - xs.min() + 1, None, g)
                    break
                continue
            tp, bot = min(ry.min(), ys.min()), max(ry.max(), ys.max())
            w, h = xs.max() - xs.min() + 1, bot - tp + 1
            if w + pad <= W and h + padv <= H:
                best = (a, xs.min(), tp, w, h, g)
                break
        if best:
            break
    if not best:
        return None, f'{text!r}: does not fit {W}x{H}'
    a, lx, ty, w, h, g = best
    LAST[text] = (os.path.basename(path), size)
    ox = x0 if align == 'left' else x1 - pad - w + 1 if align == 'right' else x0 + (W - pad - w) // 2
    oy = top if top is not None else y0 + (H - padv - h + 1) // 2
    pts = set()
    for y, x in zip(*np.where(a)):
        pts.add((ox + x - lx, oy + y - ty))
    if soft is not None:
        for y, x in zip(*np.where((g > SOFT_MIN) & ~a)):
            q = (ox + x - lx, oy + y - ty)
            if x0 <= q[0] <= x1 and y0 <= q[1] <= y1:
                soft.add(q)
    return pts, None


def shade(atlas, pts, fill_of, dark, x1, y1):
    """Draw ink pixels with a 1px drop shadow (down-right) where nothing else is drawn."""
    for (x, y) in pts:
        if (x + 1, y + 1) not in pts and x + 1 <= x1 and y + 1 <= y1 and dark is not None:
            atlas.put(x + 1, y + 1, dark)
    for (x, y) in pts:
        atlas.put(x, y, fill_of(y))


def render(text):
    """Return list of columns (each 11 bools) for proportional text ('*' suffix = narrow)."""
    squeeze = text.endswith('*')
    text = text.rstrip('*')
    out = []
    for i, ch in enumerate(text):
        g = glyph_cols(ch)
        out += narrow(g) if squeeze else g
        if i < len(text) - 1:
            out.append([False] * 11)
    return out


class Atlas:
    def __init__(self, data, base):
        self.d = bytearray(data)
        self.base = base

    def get(self, x, y):
        b = self.d[self.base + y * ROW + x // 2]
        return (b >> 4) if x & 1 else (b & 15)

    def put(self, x, y, v):
        o = self.base + y * ROW + x // 2
        b = self.d[o]
        self.d[o] = (b & 0x0F) | (v << 4) if x & 1 else (b & 0xF0) | v


# Location labels are drawn with two CLUT rows: the room banner (row 13 of the CLUT at VRAM 768,496:
# 1 = 414041 ... 9 = bdbabd, 10 = dedade, 11 = f7f3f7, 15 = ffffff; 12/13 mid grey, 14 red) and the
# facility-map list (row 6: the same order in dark navy, 15 = 6b6b9c brightest, 12/13 near-black).
# The old per-row "most common index" fill picked mid-tones such as 7, 9 or 12 for some rows, which
# put a grey band through the middle of the letters (the d of "Indoor" broke up, "Moving" came out
# all 9). Fill = a top-down ramp over the brightest indices the original glyph used.
BRIGHT = (15, 11, 10, 9)


def ramp_fill(atlas, x0, x1, y0, y1, pts):
    c = Counter(atlas.get(x, y) for y in range(y0, y1 + 1) for x in range(x0, x1 + 1))
    ramp = [i for i in BRIGHT if c[i] >= 2] or [max(c)]
    ys = [y for _, y in pts]
    t0, t1 = min(ys), max(ys)
    n = len(ramp)

    def fill(y):
        k = int((y - t0) / (t1 - t0 + 1) * (n + 1)) - 1
        return ramp[max(0, min(n - 1, k))]
    return fill


# Name tags (mail recipient grid, etc.): dark text on the silver card, no shadow, like the kana.
# CLUT row 11 of the same table: male tags use 4 (211842, lightest) .. 8 (000010), female tags
# 10 (421821) .. 14 (100000); 9 / 15 are the grey edge pixels. The kana have a vertical ramp,
# lighter in the middle rows; the English uses the same ramp per row. Row 0 of a tag (121 / 137)
# was only used by dakuten; it gets row 1's index (the old code fell back to the highest index,
# the darkest bottom-row colour). One font and size for the whole set, cap top on row 1 of the tag.
# (x0, x1, tag top row, text, ramp rows 0..9)
M_RAMP = (7, 7, 6, 5, 4, 4, 5, 6, 7, 8)
F_RAMP = (13, 13, 12, 11, 10, 10, 11, 12, 13, 14)
NAMES = [
    (2, 35, 121, 'Eiji', M_RAMP), (42, 73, 121, 'Kairi', M_RAMP), (82, 101, 121, 'Yoh', M_RAMP),
    (105, 139, 121, 'Amane', M_RAMP), (145, 179, 121, 'Kaname', F_RAMP), (185, 205, 121, 'Riko', F_RAMP),
    (210, 240, 121, 'Tomoe', F_RAMP, (210, 241, 121, 130)),     # the old エ reached x240 (shown in game)
    (1, 35, 137, 'Natsuno', F_RAMP, (1, 35, 136, 148)),
]
NAME_FONT = FONTS + '/opentype/inter/Inter-SemiBold.otf'
NAME_SOFT = True      # grey edge pixels (index 9 / 15) where the letter covers part of a pixel


def redraw_names(atlas):
    problems = []
    for size in (10, 9, 8):          # largest size at which every name fits its tag
        out = []
        for x0, x1, top, text, ramp, *ex in NAMES:
            soft = set()
            pts, prob = ink(text, x0, x1, top, top + 9, shadow=False, maxsize=size, minsize=size,
                            fonts=[NAME_FONT], top=top + 1, soft=soft)
            if prob:
                break
            out.append((pts, soft))
        else:
            break
    else:
        return ['name tags: no common size fits']
    for (x0, x1, top, text, ramp, *ex), (pts, soft) in zip(NAMES, out):
        cx0, cx1, cy0, cy1 = ex[0] if ex else (x0, x1, top, top + 9)
        for y in range(cy0, cy1 + 1):
            for x in range(cx0, cx1 + 1):
                atlas.put(x, y, 0)
        edge = 9 if ramp is M_RAMP else 15
        if NAME_SOFT:
            for (x, y) in soft:
                atlas.put(x, y, edge)
        for (x, y) in pts:
            atlas.put(x, y, ramp[min(9, max(0, y - top))])
    return problems


def redraw(atlas):
    problems = []
    for x0, x1, y0, y1, text, *extra in LABELS:
        clr = extra[0] if extra else (x0, x1, y0, y1)
        opt = extra[1] if len(extra) > 1 else {}
        pts, prob = ink(text, x0, x1, y0, y1, **opt)
        if prob:
            problems.append(prob)
            continue
        fill = ramp_fill(atlas, x0, x1, y0, y1, pts)
        allc = Counter(atlas.get(x, y) for y in range(y0, y1 + 1) for x in range(x0, x1 + 1) if atlas.get(x, y))
        dark = min((i for i in allc if i > 0), default=1)
        for y in range(clr[2], clr[3] + 1):
            for x in range(clr[0], clr[1] + 1):
                atlas.put(x, y, 0)
        shade(atlas, pts, fill, dark, x1, y1)
    return problems + redraw_names(atlas)


def main(arc_dir, out_dir, preview=None):
    os.makedirs(out_dir, exist_ok=True)
    allp = []
    for entry, base in COPIES.items():
        data = open(os.path.join(arc_dir, f'{entry:04d}.bin'), 'rb').read()
        a = Atlas(data, base)
        allp = redraw(a)
        redraw_stats(a)
        redraw_dark(a)
        if entry == 514:
            m = Atlas(a.d, MENU_BASE)
            allp = allp + redraw_menu(m)
            redraw_help(m)
            a.d = m.d
        open(os.path.join(out_dir, f'{entry:04d}.bin'), 'wb').write(bytes(a.d))
        if preview and entry == 514:
            from PIL import Image
            im = Image.new('L', (256, 256))
            p = im.load()
            for y in range(256):
                for x in range(256):
                    p[x, y] = a.get(x, y) * 17
            im.resize((768, 768), Image.NEAREST).save(preview)
            m = Atlas(a.d, MENU_BASE)
            im = Image.new('L', (256, 246))
            p = im.load()
            for y in range(246):
                for x in range(256):
                    p[x, y] = m.get(x, y) * 17
            im.resize((768, 738), Image.NEAREST).save(preview.replace('.png', '_menu.png'))
    return allp


if __name__ == '__main__':
    probs = main(*sys.argv[1:4])
    print('labels that do not fit:', probs or 'none')
