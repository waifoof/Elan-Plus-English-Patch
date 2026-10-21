"""Replace the Japanese title cards at the end of the exam movies (MOVIE/TEST01..09.STR).

  python3 exam_cards.py <frames_root> <out_root>
      frames_root/fN/*.png  = decoded frames of TEST0N.STR (jPSXdec -vf png)
      writes out_root/N/fNNNN.png + out_root/N/replace.xml for jPSXdec -replaceframes

Each movie ends with a still card (frames ~215-239): "Monthly Exam" label top-left and
bottom-right with white rules, the exam name in the middle, on a brick pattern that repeats
every 96x32 px. The card cross-fades in over the exam footage (~frames 195-214).
1. clean card = last frame with the Japanese glyphs replaced by the repeating background tile
2. English drawn at the same positions (labels left/right aligned, title centred)
3. every frame where the card is visible: frame + t * (new card - old card). TEST01-08 cross-fade:
   t = global fade level (old glyph pixels vs the pixels around them). TEST09 assembles from
   flying tiles: t = 1 where the frame already matches the final card.
"""
import glob, os, re, sys
import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont
from scipy import ndimage

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from fontpath import FONTS

FONT = FONTS + '/truetype/dejavu/DejaVuSans-BoldOblique.ttf'
LABEL = 'MONTHLY EXAM'
TITLES = {1: 'Rescue', 2: 'EVA', 3: 'Sample Analysis', 4: 'Worker Assembly',
          5: 'Geological Survey', 6: 'Wildlife Capture', 7: 'SL Gate Navigation',
          8: 'SL Atmospheric Entry', 9: 'Final Exam'}
PX, PY = 96, 32                      # background repeat
TITLE_MAXW = 296
FIRST, LAST = 150, 239               # frames read: everything before 150 is skipped; 239 = the final card
LABEL_SIZE = 14
KERN = {'NT': 1}                    # px; the oblique N-T pair reads as a word gap otherwise


def frames_of(root, n):
    """[(frame number, path)] sorted by number; the number is jPSXdec's index in the file name
    (...[NNN].png), so a partial decode (-start/-end) is read the same as a full one."""
    out = []
    for p in glob.glob(os.path.join(root, f'f{n}', '*.png')):
        m = re.search(r'\[(\d+)\]\.png$', p)
        if m:
            out.append((int(m.group(1)), p))
    return sorted(out)


def rgb(p):
    return np.asarray(Image.open(p).convert('RGB'), dtype=np.float32)


def fit_font(text, size, maxw):
    while True:
        f = ImageFont.truetype(FONT, size)
        if f.getlength(text) <= maxw or size <= 8:
            return f
        size -= 1


def longest_run(row):
    best = cur = 0
    for v in row:
        cur = cur + 1 if v else 0
        best = max(best, cur)
    return best


def card(last, n):
    """-> (clean card with english, old-glyph core mask, changed-area mask)"""
    l = last.mean(2)
    bright = l > 110
    rule_rows = np.array([longest_run(r) > 150 for r in bright])   # the white rules: one unbroken line
    glyph = bright & ~rule_rows[:, None]
    mask = ndimage.binary_dilation(glyph, iterations=2) & ~rule_rows[:, None]
    # background tile: median per phase over pixels outside the mask and away from the rules
    rule_zone = ndimage.binary_dilation(rule_rows, iterations=2)[:, None] & np.ones_like(bright)
    keep = ~ndimage.binary_dilation(bright, iterations=3) & ~rule_zone
    H, W = l.shape
    yy, xx = np.mgrid[0:H, 0:W]
    tile = np.zeros((PY, PX, 3), np.float32)
    for py in range(PY):
        for px in range(PX):
            sel = keep & (yy % PY == py) & (xx % PX == px)
            tile[py, px] = np.median(last[sel], axis=0) if sel.any() else 0
    bg = tile[yy % PY, xx % PX]
    clean = last.copy()
    clean[mask] = bg[mask]
    # glyph groups: top label, title, bottom label
    def bbox(sel):
        ys, xs = np.where(glyph & sel)
        return ys.min(), ys.max(), xs.min(), xs.max()
    top = bbox(yy < 80)
    mid = bbox((yy >= 80) & (yy < 170))
    bot = bbox(yy >= 170)
    layer = Image.new('RGBA', (W, H), (0, 0, 0, 0))
    dr = ImageDraw.Draw(layer)

    def run(text, font, x, base, fill):
        """draw text with its baseline at `base`; pairs in KERN are pulled together"""
        for k, ch in enumerate(text):
            dr.text((x, base), ch, font=font, fill=fill, anchor='ls')
            x += font.getlength(ch) - KERN.get(text[k:k + 2], 0)

    def width(text, font):
        return sum(font.getlength(c) for c in text) - sum(KERN.get(text[k:k + 2], 0) for k in range(len(text)))

    def put(text, font, x, base):
        run(text, font, x + 1, base + 1, (0, 0, 20, 200))
        run(text, font, x, base, (250, 250, 250, 255))

    lf = ImageFont.truetype(FONT, LABEL_SIZE)
    cap = -lf.getbbox('M', anchor='ls')[1]          # cap height in px
    ink_l = lf.getbbox(LABEL, anchor='ls')[0]
    ink_r = width(LABEL, lf) - lf.getlength(LABEL[-1]) + lf.getbbox(LABEL[-1], anchor='ls')[2]
    # top label: left edge and bottom on the kanji's (1 row clear above the top rule)
    put(LABEL, lf, top[2] - ink_l, top[1] + 1)
    # bottom label: right edge on the kanji's, cap top 2 rows below the bottom rule (as the kanji were)
    put(LABEL, lf, bot[3] + 1 - ink_r, bot[0] + cap)
    title = TITLES[n]
    tf = fit_font(title, 23, TITLE_MAXW)
    cx = (mid[2] + mid[3]) / 2
    tw = tf.getlength(title)
    x = int(round(min(max(cx - tw / 2, 12), W - 12 - tw)))
    put(title, tf, x, mid[1] + 1)                   # baseline on the kanji bottom; descenders hang below
    la = np.asarray(layer.filter(ImageFilter.GaussianBlur(0.35)), dtype=np.float32)
    a = la[..., 3:4] / 255
    new = clean * (1 - a) + la[..., :3] * a
    core = l > 180
    core &= ~rule_rows[:, None]
    changed = np.abs(new - last).max(2) > 2
    yy2 = np.mgrid[0:H, 0:W][0]
    groups = [core & (yy2 < 80), core & (yy2 >= 80) & (yy2 < 170), core & (yy2 >= 170)]
    return new, core, changed, dict(layer=la, kanji=mask, groups=groups)


def fade_map(fr, last, core, ring, B=16):
    H, W = core.shape
    lf, ll = fr.mean(2), last.mean(2)
    nb = (H // B, W // B)
    t = np.full(nb, np.nan)
    for by in range(nb[0]):
        for bx in range(nb[1]):
            s = np.s_[by * B:(by + 1) * B, bx * B:(bx + 1) * B]
            c, r = core[s], ring[s]
            if c.sum() >= 6 and r.sum() >= 6:
                den = ll[s][c].mean() - ll[s][r].mean()
                if den > 40:
                    t[by, bx] = (lf[s][c].mean() - lf[s][r].mean()) / den
    if np.isnan(t).all():
        return None
    idx = ndimage.distance_transform_edt(np.isnan(t), return_distances=False, return_indices=True)
    t = np.clip(t[tuple(idx)], 0, 1)
    full = np.kron(t, np.ones((B, B)))
    out = np.zeros((H, W))
    out[:full.shape[0], :full.shape[1]] = full
    return out


def tiles9(fr, last, delta, core, ex):
    """TEST09: the footage breaks into flying tiles over the (static) card; the title is drawn
    over the tiles. Card pixels get the new card; Japanese still visible elsewhere (in the seams,
    at tile edges, on the title over the tiles) is painted out from its neighbours; a glyph group
    that is fully on top gets the English drawn over whatever is under it."""
    d = np.abs(fr - last).mean(2)
    # sure card: a 5x5 neighbourhood matches the final frame; then grow up to 4 px into pixels
    # that match on their own (the edges, where the neighbourhood test fails)
    sure = ndimage.binary_opening(ndimage.uniform_filter(d, 5) < 10, iterations=2)
    tm = sure.copy()
    for _ in range(4):
        tm |= ndimage.binary_dilation(tm) & (d < 30)
    out = fr + tm[..., None] * delta
    lf = fr.mean(2)
    sat = fr.max(2) - fr.min(2)
    la = ex['layer']
    ontop = np.zeros_like(tm)
    white = (lf > 150) & (sat < 40)                 # neutral white: glyphs, not the WARNING footage
    for g, need in zip(ex['groups'], (0.8, 0.5, 0.8)):
        if white[g].mean() > need:                  # this group is drawn over the tiles (the title
                                                    # is the layer above them; it comes in moving)
            ys, xs = np.where(g)
            ontop[max(ys.min() - 8, 0):ys.max() + 9, max(xs.min() - 12, 0):xs.max() + 13] = True
    # Japanese pixels outside the card area: in a group drawn on top, or next to card pixels
    # (seams, tile edges). White footage (the WARNING letters) is neither.
    # (the glyphs are neutral white, sat < 25; the footage's whites are tinted)
    near_card = ndimage.binary_dilation((d < 10) & (lf < 30), iterations=3)
    seed = ex['kanji'] & ~tm & (lf > 180) & (sat < 25) & (near_card | ontop)
    vis = ndimage.binary_dilation(seed, iterations=2) & ex['kanji'] & ~tm & (lf > 60)
    if vis.any():                                   # paint out from the neighbours
        keep = (~vis).astype(np.float32)
        fill = out.copy()
        todo = vis.copy()
        for _ in range(12):
            num = ndimage.gaussian_filter(out * keep[..., None], (1.5, 1.5, 0))
            den = ndimage.gaussian_filter(keep, 1.5)[..., None]
            ok = todo & (den[..., 0] > 0.05)
            fill[ok] = (num / np.maximum(den, 1e-6))[ok]
            out[ok] = fill[ok]
            keep[ok] = 1
            todo &= ~ok
            if not todo.any():
                break
    a = (la[..., 3] / 255 * (ontop & ~tm))[..., None]
    out = out * (1 - a) + la[..., :3] * a
    return np.clip(out, 0, 255).astype(np.uint8)


def main(root, outroot, tests=range(1, 10)):
    for n in tests:
        fs = frames_of(root, n)
        assert fs and fs[-1][0] == LAST, f'TEST0{n}: frame {LAST} (the final card) is missing'
        assert all(i in dict(fs) for i in range(FIRST, LAST + 1)), f'TEST0{n}: frames {FIRST}-{LAST} needed'
        last = rgb(fs[-1][1])
        new, core, changed, ex = card(last, n)
        ring = ndimage.binary_dilation(core, iterations=5) & ~ndimage.binary_dilation(core, iterations=2)
        delta = new - last
        out = os.path.join(outroot, str(n))
        os.makedirs(out, exist_ok=True)
        ys, xs = np.where(ndimage.binary_dilation(changed, iterations=2))
        x0, x1 = max(xs.min() - 1, 0) & ~1, min(xs.max() + 2, 320)
        y0, y1 = max(ys.min() - 1, 0) & ~1, min(ys.max() + 2, 240)
        xml = ['<?xml version="1.0"?>', '<str-replace version="0.3">']
        used = 0
        l = last.mean(2)
        den = l[core].mean() - l[ring].mean()
        if n == 9:   # first frame where the card's glyphs show through the breaking footage
            start9 = next(i for i, p in fs if i >= FIRST and ndimage.binary_opening(
                ndimage.uniform_filter(np.abs(rgb(p) - last).mean(2), 5) < 10, iterations=2).any())
        for i, p in fs:
            if i < FIRST:
                continue
            fr = rgb(p)
            if n == 9:
                if i < start9:
                    continue
                img = tiles9(fr, last, delta, core, ex)
                name = f'f{i:04d}.png'
                Image.fromarray(img).save(os.path.join(out, name))
                xml.append(f'<partial-replace frame="{i}" tolerance="6" rect="{x0},{y0},{x1 - x0},{y1 - y0}">{name}</partial-replace>')
                used += 1
                continue
            else:
                if i < 194:                     # the card starts fading in at ~197 in TEST01-08
                    continue
                f = fr.mean(2)
                g = (f[core].mean() - f[ring].mean()) / den
                if g < 0.05:
                    continue
                tm = np.full(l.shape, min(max(g, 0), 1), np.float32)
            if tm[changed].max() < 0.03:
                continue
            img = np.clip(fr + tm[..., None] * delta, 0, 255).astype(np.uint8)
            name = f'f{i:04d}.png'
            Image.fromarray(img).save(os.path.join(out, name))
            xml.append(f'<partial-replace frame="{i}" tolerance="6" rect="{x0},{y0},{x1 - x0},{y1 - y0}">{name}</partial-replace>')
            used += 1
        xml.append('</str-replace>')
        open(os.path.join(out, 'replace.xml'), 'w').write('\n'.join(xml) + '\n')
        print(f'TEST0{n}: {used} frames, rect {x0},{y0} {x1 - x0}x{y1 - y0}')


if __name__ == '__main__':
    main(*sys.argv[1:3])
