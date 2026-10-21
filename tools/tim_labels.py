"""Redraw Japanese UI words inside paletted TIM atlases with English (palette aware).

  python3 tim_labels.py <arc_dir> <out_bin_dir> [preview_dir]

Each job: (entry, tim_offset, boxes[, pal]). A box is (x0, x1, y0, y1, text[, opt]).
pal = the CLUT row the game draws these sprites with (default 0); a box can override it with
opt['pal']. Colour choices by brightness ('top'/'dark', grad 'auto', ramp 'auto') use that row.
Renderers:
  default  labels.ink() TrueType pixels, the brightest original glyph colour of the row, a 1px
           shadow in the darkest one;
  'ttf'    bold outlined text with a vertical gradient (banners), fixed indices or grad 'auto';
  'aa'     anti-aliased text: coverage mapped onto a ramp of palette indices (dark -> light),
           like the original anti-aliased kana/title items.
Common options: 'clr' (x0, x1, y0, y1) wider area to blank first, 'keep' = indices never
overwritten (frame lines), 'area' (x0, x1, y0, y1) = where the ink may go ('aa').
"""
import os as _os, sys as _sys
_sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))
from fontpath import FONTS
import os, struct, sys
from collections import Counter
sys.path.insert(0, os.path.dirname(__file__))
import timtool
from labels import render, ink

DJ = FONTS + '/truetype/dejavu/'
CARLITO_B = FONTS + '/truetype/crosextra/Carlito-Bold.ttf'
# exam/meeting banners: heavy italic, white->cyan gradient, blue outline (like the original glyphs)
BANNER = {'ttf': DJ + 'DejaVuSans-BoldOblique.ttf',
          'grad': [11, 1, 1, 2, 3, 4, 5, 6, 7, 8], 'edge': 15, 'drop': 13}
# 0538 is drawn with CLUT row 13 for the prompts (1 = white ... 15 = dark navy) and row 10 for the
# title / extras menu items (1 = near black ... 14 = light grey, a plain ramp), read from the GP0
# sprite packets of the title, quit, map, meeting and partner-selection states.
P_PROMPT, P_TITLE = 13, 10
# title menu items: anti-aliased heavy italic caps on the row-10 grey ramp, cap height 9 like
# CONTINUE / NEW GAME. The game's sprite windows: EXTRAS u192-231 v144-159, INTERVIEWS u120-207
# v176-191 (the Japanese ink was x192-226 / x122-207, rows 144-153 / 176-185).
TITLE = {'aa': True, 'ttf': FONTS + '/opentype/inter/Inter-BlackItalic.otf', 'size': 12, 'xscale': 0.7,
         'ramp': list(range(1, 15)), 'thr': 0.2, 'pal': P_TITLE}
PROMPT = {'fg': 1, 'sh': 15}          # CLUT row 13: 1 = white, 15 = dark navy
OPTIONS = [
    # はい: sprite u216-247 v32-47; the old glyph left a dot at x217 y42-43
    (218, 240, 35, 45, 'Yes', {**PROMPT, 'solid': True, 'clr': (214, 247, 32, 47)}),
    (89, 136, 48, 60, 'Partner?', {**PROMPT, 'align': 'left', 'font': 'narrow', 'clr': (80, 136, 44, 60)}),   # shown x89-137, then the shared tail "Choose one."
    (142, 214, 48, 60, 'will you talk to?', {**PROMPT, 'align': 'left', 'clr': (137, 215, 46, 61)}),          # sprite u136-215, shown after "Who" (x0-23 of the mail prompt): starts at x142 for a word space
    (216, 247, 49, 61, 'No', {**PROMPT, 'solid': True, 'clr': (216, 247, 48, 63)}),                           # いいえ: sprite u216-247 v48-63
    (0, 120, 63, 76, "You've got mail!", PROMPT),
    # 移動先 + を選んで下さい: the tail (x161-247) is reused after 'Partner?' on the Partner Selection screen
    (121, 160, 63, 76, 'Where?', {**PROMPT, 'align': 'left', 'font': 'narrow', 'clr': (118, 160, 60, 78)}),
    (164, 247, 63, 76, 'Choose one.', {**PROMPT, 'align': 'left', 'font': 'narrow', 'clr': (161, 247, 60, 78)}),
    # sprite u0-135 v80-95; row 93 shows on top of the 'Training' header; the old か reached x131 (it left
    # a blob at x129-131). Same font as 'will you talk to?' (the meeting prompt is "Who" x0-23 + that piece):
    # the narrow font squeezed "Who" (W ran into h); the Inter "Who" ends at x23 (only its shadow falls outside)
    (0, 133, 80, 92, 'Who will you mail?', {**PROMPT, 'align': 'left', 'clr': (0, 135, 79, 92)}),
    # x0-23 of this sprite ("Who") is reused in front of the meeting prompt: 誰に + 声をかけますか
    (0, 22, 96, 109, 'Solo', {**PROMPT, 'solid': True, 'align': 'right'}),
    (25, 47, 96, 109, 'Joint', {**PROMPT, 'clr': (23, 59, 94, 110), 'solid': True, 'align': 'right'}),   # 'Solo Training' also shows x48-59: keep it blank
    (60, 118, 96, 109, 'Training', {**PROMPT, 'clr': (57, 119, 93, 110), 'solid': True, 'align': 'left'}),
    (186, 231, 142, 159, 'EXTRAS', dict(TITLE, area=(193, 229, 144, 153))),
    (118, 209, 174, 191, 'INTERVIEWS', dict(TITLE, area=(122, 205, 176, 185))),
    # パートナー選択: sprite u0-127 v192-215, drawn with the CLUT of 0870 (VRAM 896,253: a grey ramp,
    # 1 = black ... 15 = white), not with 0538's own CLUT: fixed indices, white fill, black outline
    (0, 127, 192, 215, 'Partner Select', {'ttf': BANNER['ttf'], 'grad': [15, 15, 15, 14, 14, 13, 13, 12],
                                          'edge': 1, 'drop': 3, 'padl': 1, 'padr': 1,
                                          'clr': (0, 130, 191, 216)}),
    # ゲームを終了しますか: sprite u136-247 v192-207 (its か reached x247, hence the clear to 247)
    (135, 246, 192, 205, 'Quit the game?', {**PROMPT, 'clr': (135, 247, 190, 207)}),
]
# name entry tabs: one font for all four (the inactive copies used to fall back to another font),
# anti-aliased on each tab's own grey ramp like the kana; ink kept 2px inside the frames
# (frame indices 0x32-0x35 are never overwritten)
FRAME = {0x32, 0x33, 0x34, 0x35}
TAB = {'aa': True, 'ttf': DJ + 'DejaVuSans-Bold.ttf', 'size': 11, 'xscale': 0.75, 'ramp': 'auto', 'thr': 0.2,
       'keep': FRAME, 'ref': 'Hg'}
NAME_ENTRY = [
    (33, 146, 1, 13, 'Enter your name'),
    (50, 99, 82, 92, 'Hiragana', dict(TAB, area=(52, 93, 82, 92))),
    (114, 159, 82, 92, 'Hiragana', dict(TAB, area=(116, 157, 82, 92))),
    (50, 99, 98, 108, 'Katakana', dict(TAB, area=(52, 93, 98, 108))),
    (114, 159, 98, 108, 'Katakana', dict(TAB, area=(116, 157, 98, 108))),
    # 戻す / 決定 buttons (active rows 130-141, inactive 162-173): same face, inside the slanted frames
    (50, 78, 130, 141, 'Back', dict(TAB, ref='H', area=(52, 74, 130, 141))),
    (98, 127, 130, 141, 'OK', dict(TAB, ref='H', area=(100, 122, 130, 141))),
    (50, 78, 162, 173, 'Back', dict(TAB, ref='H', area=(52, 74, 162, 173))),
    (98, 127, 162, 173, 'OK', dict(TAB, ref='H', area=(100, 122, 162, 173))),
]
GENDER = [
    (12, 146, 9, 24, 'Choose your gender', {'grid': (8, 10), 'fg': 20, 'sh': 5}),
    (16, 145, 170, 186, 'Is this OK?', {'grid': (168, 10), 'fg': 20, 'sh': 5}),
    (95, 132, 104, 116, 'Name:'),
]
# the game puts 'Total'/'Exam' directly left of 'Rank' (Total = u48-95 and Exam = u176-223, both drawn at
# x160; Rank = u96-135 at x200): keep a gap on the facing sides. Exam uses the same font and size as Total/Rank;
# its box is placed in its own sprite window like Total's (ink ends at window column 39, as Total's does).
# Row 48 holds the tops of the left bar and the '1' digit: the boxes stop at row 47.
EXAM = [
    (53, 90, 2, 20, 'Total', dict(BANNER, padr=3)),
    (96, 135, 2, 20, 'Rank', dict(BANNER, padl=3)),
    (3, 133, 27, 47, 'Group Meeting', BANNER),
    (176, 216, 24, 47, 'Exam', dict(BANNER, clr=(176, 223, 24, 47))),   # clr: the old 独 reached x219
]
# 総合順位 = "Tot Rank": both words in the same (narrow) font
RESULTS = [
    (160, 176, 192, 203, 'Tot', {'font': 'narrow'}),
    (177, 206, 192, 203, 'Rank', {'font': 'narrow'}),
    (80, 188, 208, 219, 'Joint Training'),
    (80, 114, 224, 235, 'Talks'),
    (120, 199, 224, 235, 'Events'),
]
JOBS = [
    (538, 0x0, OPTIONS, P_PROMPT),
    (519, 0x8234, OPTIONS, P_PROMPT),
    (997, 0x0, NAME_ENTRY),
    (995, 0x0, GENDER),
    (870, 0x0, EXAM),
    (872, 0x0, RESULTS), (909, 0x0, RESULTS), (910, 0x0, RESULTS),
]


class Tim:
    def __init__(self, data, off, pal=0):
        self.d = bytearray(data)
        self.t = timtool.parse(self.d, off)
        self.bpp, self.w = self.t['bpp'], self.t['w']
        self.row = self.w * self.bpp // 8
        self.set_pal(pal)

    def set_pal(self, pal):
        """Brightness of each index in CLUT row `pal` (the row the game draws the sprite with)."""
        co, cw, ch = self.t['clut']
        pal = min(pal, ch - 1)
        self.pal = pal
        self.lum = []
        for i in range(cw):
            v, = struct.unpack_from('<H', self.d, co + (pal * cw + i) * 2)
            r, g, b = v & 31, (v >> 5) & 31, (v >> 10) & 31
            self.lum.append(-1 if v == 0 else 3 * r + 6 * g + b)

    def get(self, x, y):
        o = self.t['pix'] + y * self.row
        if self.bpp == 8:
            return self.d[o + x]
        b = self.d[o + x // 2]
        return (b >> 4) if x & 1 else (b & 15)

    def put(self, x, y, v):
        o = self.t['pix'] + y * self.row
        if self.bpp == 8:
            self.d[o + x] = v
            return
        o += x // 2
        b = self.d[o]
        self.d[o] = (b & 0x0F) | (v << 4) if x & 1 else (b & 0xF0) | v


def draw_ttf(tim, box, opt):
    """Bold outlined text from a TrueType font, filled with a vertical palette gradient."""
    from PIL import Image, ImageDraw, ImageFont
    import numpy as np
    from scipy import ndimage
    x0, x1, y0, y1, text = box[:5]
    W, H = x1 - x0 + 1, y1 - y0 + 1
    pl, pr = opt.get('padl', 0), opt.get('padr', 0)     # empty columns kept on each side
    if 'clr' in opt:
        clear(tim, opt['clr'], opt.get('keep', ()), 0)
    size = opt.get('size', H)
    while size > 6:
        f = ImageFont.truetype(opt['ttf'], size)
        im = Image.new('L', (W * 2, H * 2), 0)
        ImageDraw.Draw(im).text((2, 2), text, font=f, fill=255)
        m = np.asarray(im) > 110
        ys, xs = np.where(m)
        if xs.max() - xs.min() + 1 + 3 + pl + pr <= W and ys.max() - ys.min() + 1 + 3 <= H:
            break
        size -= 1
    m = m[ys.min():ys.max() + 1, xs.min():xs.max() + 1]
    h, w = m.shape
    canvas = np.zeros((H, W), bool)
    ox, oy = pl + 1 + (W - pl - pr - 3 - w) // 2, 1 + (H - 3 - h) // 2
    canvas[oy:oy + h, ox:ox + w] = m
    edge_m = ndimage.binary_dilation(canvas, structure=np.ones((3, 3))) & ~canvas
    drop_m = np.zeros_like(canvas)
    drop_m[1:, 1:] = (canvas | edge_m)[:-1, :-1]
    drop_m &= ~(canvas | edge_m)
    g = opt['grad']
    edge, drop = opt.get('edge'), opt.get('drop')
    if g == 'auto':                     # brightest indices for the fill, darkest for the outline
        used = sorted((i for i in range(len(tim.lum)) if tim.lum[i] > 0), key=lambda i: -tim.lum[i])
        g = used[:3] + [used[3]] if len(used) > 3 else used
        edge, drop = used[-1], used[-2] if len(used) > 1 else used[-1]
    for y in range(H):
        for x in range(W):
            v = 0
            if canvas[y, x]:
                v = g[min(len(g) - 1, (y - oy) * len(g) // max(h, 1))]
            elif edge_m[y, x]:
                v = edge
            elif drop_m[y, x]:
                v = drop
            tim.put(x0 + x, y0 + y, v)
    return None


def clear(tim, area, keep=(), bg=None):
    """Blank an area with its most common index (or bg), leaving `keep` indices (frame lines) alone."""
    cx0, cx1, cy0, cy1 = area
    if bg is None:
        bg = Counter(tim.get(x, y) for y in range(cy0, cy1 + 1) for x in range(cx0, cx1 + 1)).most_common(1)[0][0]
    for y in range(cy0, cy1 + 1):
        for x in range(cx0, cx1 + 1):
            if tim.get(x, y) not in keep:
                tim.put(x, y, bg)
    return bg


def aa_mask(text, ttf, size, xscale=1.0, ref=None, ss=4):
    """Anti-aliased coverage (0..1) of `text`, x-scaled, cropped to its ink columns and to the rows
    of `ref` (default 'H', or 'Hg' when the text has descenders) so baselines stay put."""
    from PIL import Image, ImageDraw, ImageFont
    import numpy as np
    if ref is None:
        ref = 'Hg' if any(c in text for c in 'gjpqy,') else 'H'
    f = ImageFont.truetype(ttf, size * ss)
    W, H = int(f.getlength(text)) + 16 * ss, size * ss * 3
    a = np.zeros((2, H, W))
    for k, t in enumerate((text, ref)):
        im = Image.new('L', (W, H), 0)
        ImageDraw.Draw(im).text((8 * ss, 8 * ss), t, font=f, fill=255)
        a[k] = np.asarray(im) / 255.0
    ty = np.where(a[0].max(axis=1) > 0.02)[0]
    ry = np.where(a[1].max(axis=1) > 0.02)[0]
    tx = np.where(a[0].max(axis=0) > 0.02)[0]
    top = ry.min() - ss * -(-(ry.min() - min(ry.min(), ty.min())) // ss)   # cap top on a pixel edge
    bot = max(ry.max(), ty.max())
    m = a[0][top:bot + 1, tx.min():tx.max() + 1]
    h, w = m.shape
    ws = max(1, int(round(w * xscale)))
    m = np.asarray(Image.fromarray((m * 255).astype(np.uint8)).resize((ws, h), Image.LANCZOS)) / 255.0
    Hp, Wp = -(-h // ss), -(-ws // ss)
    b = np.zeros((Hp * ss, Wp * ss))
    b[:h, :ws] = m
    return b.reshape(Hp, ss, Wp, ss).mean(axis=(1, 3))


def draw_aa(tim, box, opt):
    """Anti-aliased text: coverage mapped onto a ramp of indices (dark -> light) on a transparent
    background, like the original anti-aliased glyphs."""
    import numpy as np
    x0, x1, y0, y1, text = box[:5]
    keep = set(opt.get('keep', ()))
    ax0, ax1, ay0, ay1 = opt.get('area', (x0, x1, y0, y1))
    ramp = opt.get('ramp', 'auto')
    if ramp == 'auto':                  # the original glyph colours of the box, darkest first
        used = Counter(tim.get(x, y) for y in range(y0, y1 + 1) for x in range(x0, x1 + 1))
        bg0 = used.most_common(1)[0][0]
        ramp = sorted((v for v in used if v != bg0 and v not in keep and tim.lum[v] > 0), key=lambda v: tim.lum[v])
    bg = clear(tim, opt.get('clr', (x0, x1, y0, y1)), keep, opt.get('bg', 0))
    AW, AH = ax1 - ax0 + 1, ay1 - ay0 + 1
    m = None
    for size in range(opt.get('size', AH), 6, -1):
        xs = opt.get('xscale', 1.0)
        while xs >= 0.6:
            m = aa_mask(text, opt['ttf'], size, xs, opt.get('ref'))
            if m.shape[1] <= AW and m.shape[0] <= AH:
                break
            xs -= 0.05
        if m.shape[1] <= AW and m.shape[0] <= AH:
            break
    else:
        return f'{text!r}: does not fit {AW}x{AH}'
    h, w = m.shape
    ox = ax0 if opt.get('align') == 'left' else ax0 + (AW - w) // 2
    oy = ay0 + (AH - h) // 2
    thr, n = opt.get('thr', 0.2), len(ramp)
    for y in range(h):
        for x in range(w):
            c = m[y, x]
            if c < thr or tim.get(ox + x, oy + y) in keep:
                continue
            tim.put(ox + x, oy + y, ramp[min(n - 1, int((c - thr) / (1 - thr) * n))])
    return None


def draw_box(tim, box):
    x0, x1, y0, y1, text = box[:5]
    opt = box[5] if len(box) > 5 else {}
    if isinstance(opt, int):
        opt = {'xs': opt}
    if 'aa' in opt:
        return draw_aa(tim, box, opt)
    if 'ttf' in opt:
        return draw_ttf(tim, box, opt)
    pts, prob = ink(text, x0, x1, y0, y1, align=opt.get('align', 'center'), font=opt.get('font'))
    if prob:
        return prob
    bg, fg = {}, {}
    allc = Counter()
    gbg = Counter(tim.get(x, y) for y in range(y0, y1 + 1) for x in range(x0, x1 + 1)).most_common(1)[0][0]
    for y in range(y0, y1 + 1):
        row = [tim.get(x, y) for x in range(x0, x1 + 1)]
        bg[y] = gbg
        glyph = Counter(v for v in row if v != bg[y])
        allc.update(glyph)
        if glyph:
            fg[y] = max(glyph, key=lambda v: (tim.lum[v], glyph[v]))
    if not allc:
        return f'{text!r}: empty box'
    top = opt.get('fg', max(allc, key=lambda v: tim.lum[v]))
    dark = opt.get('sh', min(allc, key=lambda v: tim.lum[v]))
    if 'fg' in opt or opt.get('solid'):
        fg = {}            # one colour for every row (thin letters look striped with the old per-row gradient)
    if 'clr' in opt:                       # wider area to blank (leftover bits of the old glyphs)
        clear(tim, opt['clr'])
    grid = opt.get('grid')
    if grid:   # restore a line grid: grid=(clean_row, clean_col)
        cr, cc = grid
        colv = {x: tim.get(x, cr) for x in range(x0, x1 + 1)}
        rowv = {y: tim.get(cc, y) for y in range(y0, y1 + 1)}
        base = Counter(colv.values()).most_common(1)[0][0]
    for y in range(y0, y1 + 1):
        for x in range(x0, x1 + 1):
            if grid:
                tim.put(x, y, rowv[y] if rowv[y] != base else colv[x])
            else:
                tim.put(x, y, bg[y])
    def colour(y):
        f = fg.get(y, top)
        return top if tim.lum[f] < tim.lum[top] * 0.6 else f
    for (x, y) in pts:
        if (x + 1, y + 1) not in pts and x + 1 <= x1 and y + 1 <= y1 and dark != colour(y):
            tim.put(x + 1, y + 1, dark)
    for (x, y) in pts:
        tim.put(x, y, colour(y))
    return None


def main(arc_dir, out_dir, preview=None):
    os.makedirs(out_dir, exist_ok=True)
    probs = []
    cache = {}
    for job in JOBS:
        entry, off, boxes = job[:3]
        pal = job[3] if len(job) > 3 else 0
        path = os.path.join(out_dir, f'{entry:04d}.bin')
        src = cache.get(entry) or open(os.path.join(arc_dir, f'{entry:04d}.bin'), 'rb').read()
        tim = Tim(src, off, pal)
        for b in boxes:
            bpal = b[5].get('pal', pal) if len(b) > 5 and isinstance(b[5], dict) else pal
            tim.set_pal(bpal)
            p = draw_box(tim, b)
            if p:
                probs.append(f'{entry}: {p}')
        assert len(tim.d) == len(src), f'{entry}: size changed'
        cache[entry] = bytes(tim.d)
        open(path, 'wb').write(cache[entry])
        if preview:
            im = timtool.to_image(tim.d, tim.t, pal)
            im.resize((im.width * 2, im.height * 2)).save(os.path.join(preview, f'tl_{entry:04d}.png'))
    return probs


if __name__ == '__main__':
    print('problems:', main(*sys.argv[1:4]) or 'none')
