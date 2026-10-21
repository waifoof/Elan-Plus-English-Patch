"""Redraw the Extras > Interviews / Gallery graphics in English.

  python3 extras_labels.py [arc_dir] [out_bin_dir] [preview_dir] [elanplus_in] [elanplus_out]

Defaults (relative to the repository): arc_dir work/arc/OUTPUT, out_bin_dir work/text/bin,
ELANPLUS.BIN from work/disc/GAME, patched copy to work/text/elanplus/.

Textures (sprite rectangles read from the game's GPU packets in RAM, see docs/ENGINE_NOTES.md):
  0988 (8bpp 248x240, VRAM 320,0): the 12 name panels of the Interviews / Gallery list (neon glow
       text baked on the panel), the header pieces 声優インタビュー / ギャラリー and the help bar
       (○)決定 (×)取り消し.
  0986 (8bpp 248x240, VRAM 448,0): actor / character name plates and the 4 question bars of a
       character's interview page (anti-aliased glyphs on a transparent background; each
       question is two sprites side by side; a light copy (selected) and a dark copy).
  ELANPLUS.BIN TIMs @0x27800 / @0xBD32C (256x200 gallery frame) and @0xBB80C (32x200, its right
       strip): the gallery page help 方向キーで選択 ●で決定. ELANPLUS.BIN is not an OUTPUT.BIN
       entry, so a patched copy of the whole file is written (same size) for the build to use.

Every label is drawn from TrueType outlines rendered 4x and box-filtered down (anti-aliased like
the original glyphs), then mapped onto colours that the original glyphs of that sprite used.
"""
import os as _os, sys as _sys
_sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))
from fontpath import FONTS
import os, struct, sys
from collections import Counter
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from scipy import ndimage

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import timtool
from tim_labels import Tim

INTER = FONTS + '/opentype/inter/Inter-SemiBold.otf'
INTER_I = FONTS + '/opentype/inter/Inter-SemiBoldItalic.otf'
INTER_BI = FONTS + '/opentype/inter/Inter-BoldItalic.otf'
CARLITO = FONTS + '/truetype/crosextra/Carlito-Bold.ttf'
CARLITO_I = FONTS + '/truetype/crosextra/Carlito-BoldItalic.ttf'

# ---------------------------------------------------------------- the labels
# (character, actor JP, actor EN, char JP, char EN, female)
CAST = [
    ('Eiji', '関 智一', 'Tomokazu Seki', 'エイジ', 'Eiji', False),
    ('Yoh', '石田 彰', 'Akira Ishida', 'ヨウ', 'Yoh', False),
    ('Kairi', '千葉 進歩', 'Susumu Chiba', 'カイリ', 'Kairi', False),
    ('Amane', '高山 みなみ', 'Minami Takayama', 'アマネ', 'Amane', False),
    ('Natsuno', '黒崎 彩子', 'Ayako Kurosaki', 'ナツノ', 'Natsuno', True),
    ('Tomoe', '川澄 綾子', 'Ayako Kawasumi', 'トモエ', 'Tomoe', True),
    ('Riko', '金月 真美', 'Mami Kanetsuki', 'リコ', 'Riko', True),
    ('Kaname', '半場 友恵', 'Tomoe Hanba', 'カナメ', 'Kaname', True),
    ('Narusawa', '三木 眞一郎', 'Shinichiro Miki', 'ナルサワ', 'Narusawa', False),
    ('Sakaki', '伊藤 美紀', 'Miki Ito', 'サカキ', 'Sakaki', True),
    ('Rei', '岩田 光央', 'Mitsuo Iwata', 'レイ', 'Rei', False),
    ('Sarai', '保志 総一朗', 'Soichiro Hoshi', 'サライ', 'Sarai', False),
]
CAST_BY = {c[0]: c for c in CAST}

# 0988 list panels: 136x24 each. Left column (face left, text right) drawn at x=-16,
# right column (face right, text left) drawn at x=208 (only u0-111 on screen).
# Rei / Sarai are split: a 24x24 piece (u, v) + the 112x24 rest (u, v).
PANELS = [  # (name, side, [(virtual_x0, u, v, w)])
    ('Eiji', 'L', [(0, 0, 0, 136)]), ('Yoh', 'L', [(0, 0, 24, 136)]),
    ('Kairi', 'L', [(0, 0, 48, 136)]), ('Amane', 'L', [(0, 0, 72, 136)]),
    ('Natsuno', 'L', [(0, 0, 96, 136)]), ('Tomoe', 'L', [(0, 0, 120, 136)]),
    ('Riko', 'R', [(0, 0, 144, 136)]), ('Kaname', 'R', [(0, 0, 168, 136)]),
    ('Narusawa', 'R', [(0, 0, 192, 136)]), ('Sakaki', 'R', [(0, 0, 216, 136)]),
    ('Rei', 'R', [(0, 136, 48, 24), (24, 136, 0, 112)]),
    ('Sarai', 'R', [(0, 160, 48, 24), (24, 136, 24, 112)]),
]
PANEL_TEXT = {'L': (72, 133), 'R': (3, 58)}      # x range of the text area (virtual panel x)

# 0986 per-character page: name sprites (u, v, w), 16 rows high, centred on the plates
PLATES = {  # name: (actor (u, v, w), character (u, v, w))
    'Eiji': ((80, 48, 64), (48, 96, 48)), 'Yoh': ((0, 64, 64), (96, 64, 32)),
    'Kairi': ((160, 0, 80), (96, 96, 48)), 'Amane': ((96, 32, 96), (144, 80, 48)),
    'Natsuno': ((0, 0, 80), (0, 80, 48)), 'Tomoe': ((0, 48, 80), (192, 80, 48)),
    'Riko': ((160, 16, 80), (128, 64, 32)), 'Kaname': ((0, 16, 80), (96, 80, 48)),
    'Narusawa': ((144, 48, 96), (160, 64, 64)), 'Sakaki': ((80, 0, 80), (48, 80, 48)),
    'Rei': ((80, 16, 80), (64, 64, 32)), 'Sarai': ((0, 32, 96), (0, 96, 48)),
}
# questions: JP, EN, [light pieces (u, v, w)], dark copy = same u, v + 32
QUESTIONS = [
    ('宇宙についてどう思いますか？', 'What do you think about space?', [(144, 176, 72), (144, 192, 96)]),
    ('未知の惑星に降りた時、最初に何をしますか？', 'On an unknown planet, what would you do first?',
     [(0, 112, 128), (0, 128, 128)]),
    ('自分が担当したキャラについて、どう思いますか？', 'What do you think of the character you play?',
     [(0, 176, 136), (0, 192, 144)]),
    ('エランを遊ぶプレイヤーさんにひとこと', 'Any message for Elan players?', [(128, 112, 120), (128, 128, 96)]),
]
# bars in 0988: header pieces (u, v, w) left to right, 16 rows; clean rows to rebuild the bar from
HEADERS = [
    ('声優インタビュー', 'Voice Actor Interviews', [(184, 48, 64), (136, 72, 104)], (10, 160)),
    ('ギャラリー', 'Gallery', [(136, 224, 96)], (4, 92)),
]
HELP = [  # piece (u, v, w), text x range inside the piece, keep-symbol columns
    ('決定', 'Confirm', (136, 104, 64)),
    ('取り消し', 'Cancel', (136, 88, 112)),
]
# ELANPLUS.BIN gallery frame help
EP_MAIN = [0x27800, 0xBD32C]
EP_STRIP = 0xBB80C
GAL_HELP = [("方向キーで選択", "D-Pad: Select", (152, 223)), ("で決定", "Confirm", (243, 286))]


# ---------------------------------------------------------------- rendering
def cov(text, font, size, xscale=1.0):
    """Anti-aliased coverage of `text` -> (array HxW in 0..1, cap_top_row, baseline_row)."""
    S = 4
    f = ImageFont.truetype(font, size * S)
    pad = 4 * S
    l, t, r, b = f.getbbox(text)
    _, ht, _, hb = f.getbbox('H')
    W, H = r - l + 2 * pad, b + 2 * pad
    oy = pad
    while (oy + hb) % S:
        oy += 1
    im = Image.new('L', (W + S, H + S), 0)
    ImageDraw.Draw(im).text((pad - l, oy), text, font=f, fill=255)
    w1 = max(1, int(round(im.width / S * xscale)))
    sm = im.resize((w1, im.height // S), Image.BOX)
    a = np.asarray(sm, np.float32) / 255.0
    cols = np.where(a.max(0) > 0.08)[0]
    a = a[:, cols.min():cols.max() + 1]
    return a, (oy + ht) // S, (oy + hb) // S


def fit(text, maxw, fonts, sizes, minscale=0.86):
    """Largest size (then font) whose width fits maxw; squeeze x down to minscale if needed."""
    for size in sizes:
        for font in fonts:
            a, ct, bl = cov(text, font, size)
            if a.shape[1] <= maxw:
                return a, ct, bl, (font, size, 1.0)
        for font in fonts:
            a, ct, bl = cov(text, font, size)
            sc = maxw / a.shape[1]
            if sc >= minscale:
                a, ct, bl = cov(text, font, size, sc * 0.995)
                if a.shape[1] <= maxw:
                    return a, ct, bl, (font, size, round(sc, 3))
    raise ValueError(f'{text!r} does not fit {maxw}px')


def place(canvas, a, ct, bl, x, cap_top):
    """Max-composite coverage `a` into canvas so that its cap top lands on row cap_top."""
    y = cap_top - ct
    h, w = a.shape
    H, W = canvas.shape
    for yy in range(h):
        Y = y + yy
        if 0 <= Y < H:
            xs, xe = max(0, x), min(W, x + w)
            if xe > xs:
                canvas[Y, xs:xe] = np.maximum(canvas[Y, xs:xe], a[yy, xs - x:xe - x])


def rgb_list(tim):
    co, cw, _ = tim.t['clut']
    out = []
    for i in range(cw):
        v, = struct.unpack_from('<H', tim.d, co + i * 2)
        out.append(np.array([(v & 31) << 3, ((v >> 5) & 31) << 3, ((v >> 10) & 31) << 3], np.float32))
    return out


def lum(c):
    return 0.3 * c[0] + 0.59 * c[1] + 0.11 * c[2]


class Nearest:
    def __init__(self, rgbs, idxs):
        self.idx = list(idxs)
        self.arr = np.array([rgbs[i] for i in self.idx])

    def __call__(self, c):
        return self.idx[int(np.argmin(((self.arr - c) ** 2).sum(1)))]


# ---------------------------------------------------------------- 0986: plates and questions
def draw_plain(tim, rgbs, pieces, text, fonts, sizes, cap_top, minscale=0.86, pad=1):
    """Pieces (u, v, w) side by side form one line; text centred on it, mapped onto the
    original glyphs' colours by coverage quantile (same mix of core and edge shades)."""
    W = sum(p[2] for p in pieces)
    orig = []
    for u, v, w in pieces:
        for y in range(v, v + 16):
            for x in range(u, u + w):
                i = tim.get(x, y)
                if i:
                    orig.append(i)
    orig.sort(key=lambda i: lum(rgbs[i]))
    a, ct, bl, how = fit(text, W - 2 * pad, fonts, sizes, minscale)
    canvas = np.zeros((16, W), np.float32)
    place(canvas, a, ct, bl, (W - a.shape[1]) // 2, cap_top)
    vals = np.sort(canvas[canvas > 0.1])
    x0 = 0
    for u, v, w in pieces:
        for y in range(16):
            for x in range(w):
                c = canvas[y, x0 + x]
                if c <= 0.1:
                    tim.put(u + x, v + y, 0)
                    continue
                q = np.searchsorted(vals, c) / max(1, len(vals) - 1)
                tim.put(u + x, v + y, orig[min(len(orig) - 1, int(q * (len(orig) - 1)))])
        x0 += w
    return how


# ---------------------------------------------------------------- 0988: glowing panel names
GREEN = lambda c: c[1] > c[0] + 40 and c[1] > c[2] + 40


def panel_get(tim, segs, x, y):
    for vx, u, v, w in reversed(segs):
        if x >= vx:
            return u + x - vx, v + y
    raise IndexError


def draw_panel(tim, rgbs, name, side, segs, cands, look):
    _, _, actor, _, char, female = CAST_BY[name]
    W, H = 136, 24
    px = lambda x, y: tim.get(*panel_get(tim, segs, x, y))
    tx0, tx1 = PANEL_TEXT[side]
    # protected: green border lines + the 1px border shading next to them, and everything outside the text area
    prot = np.zeros((H, W), bool)
    for y in range(H):
        for x in range(W):
            if GREEN(rgbs[px(x, y)]):
                prot[y, max(0, x - 1):x + 2] = True
    prot[:, :tx0] = True
    prot[:, tx1 + 1:] = True
    prot[0, :] = prot[H - 1, :] = True
    bg = 0x2d
    fill, glowc = look
    cov_l = np.zeros((H, W), np.float32)
    lines = []
    # the M / star / C icons the list draws on top of each panel's second row
    icons = np.zeros((H, W), bool)
    if side == 'L':
        icons[12:, 64:90] = True
    else:
        icons[12:, 51:] = True
    for text, cap in ((actor, 3), (char, 13)):
        for size, sc in ((10, 1.0), (10, 0.92), (9, 1.0), (9, 0.92), (9, 0.86), (8, 1.0), (8, 0.9)):
            a, ct, bl = cov(text, CARLITO, size, sc)
            w = a.shape[1]
            if w > tx1 - tx0 - 1:
                continue
            # right-align (left panels) / left-align (right panels), then slide inwards until the
            # letters and their glow stay clear of the border, its diagonal corner and the icons
            xs = range(tx1 - 1 - w + 1, tx0, -1) if side == 'L' else range(tx0 + 1, tx1 - w + 1)
            for x in xs:
                c = np.zeros((H, W), np.float32)
                place(c, a, ct, 0, x, cap)
                g = ndimage.binary_dilation(c > 0.05, iterations=1)
                if not (g & (prot | icons)).any():
                    break
            else:
                continue
            break
        else:
            raise ValueError(f'{name}: {text!r} collides with the panel border')
        place(cov_l, a, ct, 0, x, cap)
        lines.append((text, a, ct, (CARLITO, size, sc), cap))
    glow = ndimage.gaussian_filter(ndimage.grey_dilation(cov_l, size=(2, 2)), 1.25) * 2.2
    glow = np.clip(glow, 0, 1)
    near = Nearest(rgbs, cands)
    # the old glyphs' glow can reach past the text area: also clear the columns beyond it that
    # hold nothing but glow / background colours (up to the face)
    ok = set(cands) | {0}
    def pure(x):
        return all(px(x, y) in ok or GREEN(rgbs[px(x, y)]) for y in range(1, H - 1))
    ext = []
    step = 1 if side == 'R' else -1
    x = tx1 + 1 if side == 'R' else tx0 - 1
    while 0 <= x < W and len(ext) < 14 and pure(x):
        ext.append(x)
        x += step
    for y in range(1, H - 1):
        for x in ext:
            if not GREEN(rgbs[px(x, y)]) and not (x and GREEN(rgbs[px(x - 1, y)])):
                tim.put(*panel_get(tim, segs, x, y), bg)
    for y in range(1, H - 1):
        for x in range(tx0, tx1 + 1):
            if prot[y, x]:
                continue
            c = cov_l[y, x]
            g = glow[y, x]
            col = c * fill + (1 - c) * g * glowc + (1 - c) * (1 - g) * rgbs[bg]
            i = near(col) if (c > 0.04 or g > 0.06) else bg
            tim.put(*panel_get(tim, segs, x, y), i)
    return [l[3] for l in lines]


def panel_colours(tim, rgbs):
    """Glow colour sets from the original panel text areas: blue (male) and red (female)."""
    sets = {False: Counter(), True: Counter()}
    for name, side, segs in PANELS:
        fem = CAST_BY[name][5]
        tx0, tx1 = PANEL_TEXT[side]
        for y in range(1, 23):
            for x in range(tx0, tx1 + 1):
                i = tim.get(*panel_get(tim, segs, x, y))
                c = rgbs[i]
                if GREEN(c):
                    continue
                if fem and c[0] >= c[1] and c[2] >= c[1] - 8 and (c[0] > 60 or i == 0x2d):
                    sets[True][i] += 1
                if not fem and c[2] >= c[0] and c[2] >= c[1] - 8:
                    sets[False][i] += 1
    sets[True][0x2d] += 1
    sets[False][0x2d] += 1
    return {k: [i for i in v] for k, v in sets.items()}


LOOK = {False: (np.array([226, 226, 240.]), np.array([40, 32, 228.])),     # lavender white, blue glow
        True: (np.array([248, 214, 220.]), np.array([224, 10, 90.]))}       # pink white, red glow


# ---------------------------------------------------------------- 0988: header and help bars
def bar_restore(tim, pieces, text_rows, clean_rows):
    """Rebuild the bar under the old text: copy each text row from the nearest clean row of the
    same parity (the bars are vertical colour bands with 2-row dither at the band edges)."""
    for u, v, w in pieces:
        for y in text_rows:
            cands = [r for r in clean_rows if r % 2 == y % 2] or clean_rows
            src = min(cands, key=lambda r: abs(r - y))
            for x in range(u, u + w):
                tim.put(x, v + y, tim.get(x, v + src))


def bar_text(tim, rgbs, pieces, canvas, fillc, cands):
    near = Nearest(rgbs, cands)
    x0 = 0
    for u, v, w in pieces:
        for y in range(16):
            for x in range(w):
                c = canvas[y, x0 + x]
                if c > 0.06:
                    bgc = rgbs[tim.get(u + x, v + y)]
                    tim.put(u + x, v + y, near(c * fillc + (1 - c) * bgc))
        x0 += w


def draw_header(tim, rgbs, pieces, text, span):
    W = sum(p[2] for p in pieces)
    used = Counter()
    for u, v, w in pieces:
        for y in range(16):
            for x in range(u, u + w):
                used[tim.get(x, v + y)] += 1
    fillc = rgbs[0x4f]                       # brightest cyan of the old glyphs (112,248,240)
    bar_restore(tim, pieces, range(1, 13), [0, 13, 15])
    a, ct, bl, how = fit(text, span[1] - span[0], [INTER_BI], [13, 12, 11])
    canvas = np.zeros((16, W), np.float32)
    x = span[1] - a.shape[1] if len(pieces) > 1 else (span[0] + span[1] - a.shape[1]) // 2
    place(canvas, a, ct, bl, x, 2 if any(ch in text for ch in 'gjpqy') else 3)   # keep descenders off the bar's bottom line
    bar_text(tim, rgbs, pieces, canvas, fillc, list(used))
    return how


def draw_help(tim, rgbs):
    out = []
    # (○)決定: move "(○)" (cols 10-34) 8 px left, then "Confirm" after it
    u, v, w = HELP[0][2]
    used = Counter(tim.get(x, v + y) for y in range(16) for x in range(u, u + w))
    sym = [[tim.get(u + x, v + y) for x in range(w)] for y in range(16)]
    bar = [[tim.get(u + x, v + y) for x in range(w)] for y in range(16)]
    for y in range(2, 14):                      # clean the whole row band from the bar rows 0/1/14/15
        src = 0 if y % 2 == 0 else 1
        for x in range(w):
            tim.put(u + x, v + y, bar[src][x])
    shift = 8
    for y in range(2, 14):
        for x in range(10, 36):
            s = sym[y][x]
            if s != bar[0 if y % 2 == 0 else 1][x]:
                tim.put(u + x - shift, v + y, s)
    a, ct, bl, how = fit('Confirm', w - (36 - shift) - 2, [CARLITO], [11, 10], 0.84)
    canvas = np.zeros((16, w), np.float32)
    place(canvas, a, ct, bl, 36 - shift + 2, 4)
    bar_text(tim, rgbs, [(u, v, w)], canvas, rgbs[0x02], list(used))
    out.append(how)
    # (×)取り消し: keep "(×)" (cols 0-35), replace cols 36-111
    u, v, w = HELP[1][2]
    used = Counter(tim.get(x, v + y) for y in range(16) for x in range(u, u + w))
    for y in range(2, 14):
        src = 0 if y % 2 == 0 else 1
        for x in range(36, w):
            tim.put(u + x, v + y, tim.get(u + x, v + src))
    a, ct, bl, how = fit('Cancel', 60, [CARLITO], [11, 10], 0.84)
    canvas = np.zeros((16, w), np.float32)
    place(canvas, a, ct, bl, 38, 4)
    bar_text(tim, rgbs, [(u, v, w)], canvas, rgbs[0x21], list(used))
    out.append(how)
    return out


# ---------------------------------------------------------------- ELANPLUS.BIN gallery help
def gallery_help(data):
    """Inpaint the white JP help text on the earth photo, draw the English in white with a soft
    dark shadow. Works on the 256x200 frame + its 32px right strip as one 288-wide canvas."""
    import cv2
    d = bytearray(data)
    main = Tim(d, EP_MAIN[0])
    strip = Tim(d, EP_STRIP)
    X0, X1, Y0, Y1 = 140, 288, 2, 26                 # virtual canvas window (x >= 256 is the strip)
    def tim_at(x):
        return (main, x) if x < 256 else (strip, x - 256)
    pal = {id(main): rgb_list(main), id(strip): rgb_list(strip)}
    img = np.zeros((Y1 - Y0, X1 - X0, 3), np.float32)
    for y in range(Y0, Y1):
        for x in range(X0, X1):
            t, xx = tim_at(x)
            img[y - Y0, x - X0] = pal[id(t)][t.get(xx, y)]
    L = img @ np.array([0.3, 0.59, 0.11])
    # old letters: bright pixels in the text band, minus the ● icon (x 230-241)
    mask = np.zeros(L.shape, np.uint8)
    for y in range(9 - Y0, 20 - Y0):
        for x in range(X0, X1):
            if 229 <= x <= 240:
                continue
            if L[y, x - X0] > 150:
                mask[y, x - X0] = 1
    mask = ndimage.binary_dilation(mask, iterations=1).astype(np.uint8)
    for y in range(mask.shape[0]):
        for x in range(229 - X0, 241 - X0):
            mask[y, x] = 0
    fixed = cv2.inpaint(np.clip(img, 0, 255).astype(np.uint8), mask, 2, cv2.INPAINT_TELEA).astype(np.float32)
    canvas = np.zeros(L.shape, np.float32)
    hows = []
    for jp, en, (sx0, sx1) in GAL_HELP:
        a, ct, bl, how = fit(en, sx1 - sx0, [CARLITO_I], [11, 10], 0.86)
        place(canvas, a, ct, bl, sx0 - X0, 11 - Y0)
        hows.append(how)
    shadow = np.zeros_like(canvas)
    shadow[1:, 1:] = canvas[:-1, :-1]
    shadow = np.clip(np.maximum(shadow, ndimage.gaussian_filter(canvas, 0.8) * 1.4), 0, 1) * 0.75
    out = fixed * (1 - shadow[..., None]) + np.array([4, 8, 24.]) * shadow[..., None]
    out = out * (1 - canvas[..., None]) + np.array([248, 248, 248.]) * canvas[..., None]
    nearest = {id(main): Nearest(pal[id(main)], range(256)), id(strip): Nearest(pal[id(strip)], range(256))}
    for y in range(Y0, Y1):
        for x in range(X0, X1):
            if not mask[y - Y0, x - X0] and canvas[y - Y0, x - X0] < 0.02 and shadow[y - Y0, x - X0] < 0.02:
                continue
            t, xx = tim_at(x)
            t.put(xx, y, nearest[id(t)](out[y - Y0, x - X0]))
    # main/strip share the buffer; copy the redrawn 256x200 frame into its identical second copy
    a0 = main.t['off']
    n = main.t['end'] - a0
    new = bytes(main.d)
    out_d = bytearray(new)
    for off in EP_MAIN[1:]:
        out_d[off:off + n] = new[a0:a0 + n]
    # strip edits are in strip.d (separate copy): merge them
    s0, s1 = strip.t['pix'], strip.t['end']
    out_d[s0:s1] = strip.d[s0:s1]
    return bytes(out_d), hows


# ---------------------------------------------------------------- main
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def main(arc_dir=os.path.join(_ROOT, 'work', 'arc', 'OUTPUT'), out_dir=os.path.join(_ROOT, 'work', 'text', 'bin'), preview=None,
         ep_in=os.path.join(_ROOT, 'work', 'disc', 'GAME', 'ELANPLUS.BIN'),
         ep_out=os.path.join(_ROOT, 'work', 'text', 'elanplus', 'ELANPLUS.BIN')):
    os.makedirs(out_dir, exist_ok=True)
    log = []
    # 0986
    t = Tim(open(os.path.join(arc_dir, '0986.bin'), 'rb').read(), 0)
    rgbs = rgb_list(t)
    for name, (act, ch) in PLATES.items():
        _, ajp, aen, cjp, cen, _ = CAST_BY[name]
        h1 = draw_plain(t, rgbs, [act], aen, [CARLITO], [12, 11, 10], 3)
        h2 = draw_plain(t, rgbs, [ch], cen, [CARLITO], [12, 11], 3)
        log.append(('0986', f'plate {name}', ajp, aen, h1))
        log.append(('0986', f'plate {name}', cjp, cen, h2))
    for jp, en, pieces in QUESTIONS:
        h = draw_plain(t, rgbs, pieces, en, [INTER_I], [11, 10], 3, minscale=0.95)
        draw_plain(t, rgbs, [(u, v + 32, w) for u, v, w in pieces], en, [INTER_I], [11, 10], 3, minscale=0.95)
        log.append(('0986', 'question', jp, en, h))
    open(os.path.join(out_dir, '0986.bin'), 'wb').write(bytes(t.d))
    if preview:
        im = timtool.to_image(t.d, t.t)
        bgim = Image.new('RGBA', im.size, (40, 60, 150, 255)); bgim.alpha_composite(im)
        bgim.resize((im.width * 3, im.height * 3), Image.NEAREST).save(os.path.join(preview, 'x_0986.png'))
    # 0988
    t = Tim(open(os.path.join(arc_dir, '0988.bin'), 'rb').read(), 0)
    rgbs = rgb_list(t)
    cols = panel_colours(t, rgbs)
    for name, side, segs in PANELS:
        fem = CAST_BY[name][5]
        hows = draw_panel(t, rgbs, name, side, segs, cols[fem], LOOK[fem])
        log.append(('0988', f'panel {name}', CAST_BY[name][1] + ' / ' + CAST_BY[name][3],
                    CAST_BY[name][2] + ' / ' + CAST_BY[name][4], hows))
    for jp, en, pieces, span in HEADERS:
        log.append(('0988', 'header', jp, en, draw_header(t, rgbs, pieces, en, span)))
    hh = draw_help(t, rgbs)
    log.append(('0988', 'help', '(○)決定', '(○) Confirm', hh[0]))
    log.append(('0988', 'help', '(×)取り消し', '(×) Cancel', hh[1]))
    open(os.path.join(out_dir, '0988.bin'), 'wb').write(bytes(t.d))
    if preview:
        im = timtool.to_image(t.d, t.t)
        im.resize((im.width * 3, im.height * 3), Image.NEAREST).save(os.path.join(preview, 'x_0988.png'))
    # ELANPLUS.BIN
    if ep_in and ep_out:
        data = open(ep_in, 'rb').read()
        new, hows = gallery_help(data)
        assert len(new) == len(data)
        os.makedirs(os.path.dirname(ep_out), exist_ok=True)
        open(ep_out, 'wb').write(new)
        for (jp, en, _), h in zip(GAL_HELP, hows):
            log.append(('ELANPLUS', 'gallery help', jp, en, h))
        if preview:
            m = timtool.parse(bytearray(new), EP_MAIN[0]); s = timtool.parse(bytearray(new), EP_STRIP)
            c = Image.new('RGBA', (288, 40))
            c.paste(timtool.to_image(new, m).crop((0, 0, 256, 40)), (0, 0))
            c.paste(timtool.to_image(new, s).crop((0, 0, 32, 40)), (256, 0))
            c.resize((288 * 4, 160), Image.NEAREST).save(os.path.join(preview, 'x_gallery_help.png'))
    return log


if __name__ == '__main__':
    args = [None if a in ('', '-') else a for a in sys.argv[1:]]
    kw = dict(zip(['arc_dir', 'out_dir', 'preview', 'ep_in', 'ep_out'], args))
    for row in main(**{k: v for k, v in kw.items() if v is not None or k == 'preview'}):
        print(*row, sep=' | ')
