"""Replace the burned-in captions of the prologue movie (MOVIE/PR.STR) with English.

  python3 str_captions.py <frames_dir> <out_dir>

Writes out_dir/fNNNN.png for every caption frame plus out_dir/replace.xml for
jPSXdec -replaceframes (partial replace limited to the caption band).
For each caption: the Japanese glyph pixels (found against a clean plate taken
just before the caption fades in) are restored from the plate, then the English
lines are drawn at the original line positions with the frame's fade level.

Fade handling: the scene's own fade (caption 7 fades to black with the whole picture) is measured
as the band's brightness outside the glyphs relative to the plate (r); the restored background is
the plate scaled by r and the English is drawn with colour fill*r and alpha = the caption's own
level (text brightness above r*plate, divided by r). All lines of a caption start at the same x
(the Japanese first line of caption 5 was indented for its opening bracket).
"""
import glob, os, sys
import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from fontpath import FONTS

BAND = (30, 158, 320, 230)            # x0, y0, x1, y1 of the caption area
FONT = FONTS + '/truetype/dejavu/DejaVuSansCondensed.ttf'
SIZE = 12
FILL = (255, 255, 255, 255)        # the Japanese glyphs are pure white
BLUR = 0.3

# (first frame, last frame, english lines) -- one entry per caption, lines in the
# same count as the original so each sits where a Japanese line was.
CAPTIONS = [
    (88, 198, ['Through a global nuclear war,',
               'humanity, by its own hand,',
               'turned the Earth into a dead world.']),
    (253, 363, ['The survivors left the Earth',
                'and moved their lives to "Sophia,"',
                'a giant artificial spherical colony.']),
    (418, 528, ['187 years later...',
                'Humanity discovered a planet',
                'that seemed fit for settlement.']),
    (628, 738, ['Elan: the third planet of Tau Ceti.',
                'This planet, so like the Earth,',
                "became humanity's one remaining hope."]),
    (792, 904, ['"Project Elan"',
                'Its aim: to move humanity there en masse',
                'by placing a jump wormhole, "the Gate,"',
                'in orbit around the planet Elan.']),
    (958, 1069, ['To reach faraway Elan,',
                 'construction began on a starship',
                 'equipped with a new means of travel.']),
    (1079, 1187, ['Its crew: only two.',
                  'Six months until the ship is complete.']),
]


def load(frames, i):
    p = glob.glob(os.path.join(frames, f'*[[]{i:04d}[]].png'))[0]
    return np.asarray(Image.open(p).convert('RGB'), dtype=np.float32)


def lum(a):
    return a[..., 0] * 0.3 + a[..., 1] * 0.59 + a[..., 2] * 0.11


def lines_of(mask):
    """Group mask rows into text lines: [(y0, y1, x0)]."""
    rows = mask.any(axis=1)
    out, s = [], None
    for y, v in enumerate(list(rows) + [False]):
        if v and s is None:
            s = y
        elif not v and s is not None:
            if y - s >= 5:
                xs = np.where(mask[s:y].any(axis=0))[0]
                out.append((s, y - 1, int(xs.min())))
            s = None
    return out


def main(frames, out):
    os.makedirs(out, exist_ok=True)
    x0, y0, x1, y1 = BAND
    font = ImageFont.truetype(FONT, SIZE)
    xml = ['<?xml version="1.0"?>', '<str-replace version="0.3">']
    report = []
    for s, e, text in CAPTIONS:
        plate = load(frames, s - 6)
        mid = load(frames, (s + e) // 2)
        d = lum(mid) - lum(plate)
        m = np.zeros(d.shape, bool)
        m[y0:y1, x0:x1] = d[y0:y1, x0:x1] > 35
        lines = lines_of(m)
        if len(lines) != len(text):
            report.append(f'caption {s}: {len(lines)} lines found, {len(text)} English lines')
        mask = Image.fromarray((m * 255).astype(np.uint8)).filter(ImageFilter.MaxFilter(5))
        mk = np.asarray(mask) > 0
        # background reference: the band away from the glyphs
        far = np.asarray(Image.fromarray((m * 255).astype(np.uint8)).filter(ImageFilter.MaxFilter(9))) == 0
        ring = np.zeros_like(m)
        ring[y0:y1, x0:x1] = True
        ring &= far
        plate_ring = lum(plate)[ring].mean()
        # English layer (white text + dark shadow) and its alpha
        layer = Image.new('RGBA', (320, 240), (0, 0, 0, 0))
        dr = ImageDraw.Draw(layer)
        lx = min(l[2] for l in lines)          # one left edge for every line
        for (ly0, ly1, _), t in zip(lines, text):
            top = ly0 + (ly1 - ly0 + 1 - SIZE) // 2 - 1
            dr.text((lx + 1, top + 1), t, font=font, fill=(10, 10, 30, 150))
            dr.text((lx, top), t, font=font, fill=FILL)
            w = dr.textlength(t, font=font)
            if lx + w > 318:
                report.append(f'caption {s}: line too wide ({int(lx + w)}px): {t}')
        layer = layer.filter(ImageFilter.GaussianBlur(BLUR))
        la = np.asarray(layer, dtype=np.float32)
        peak = np.percentile(d[m], 75) if m.any() else 1
        for i in range(s - 4, e + 6):
            fr = load(frames, i)
            r = float(np.clip(lum(fr)[ring].mean() / plate_ring, 0, 1))
            if r > 0.985:
                r = 1.0                         # encoder noise, not a fade
            di = lum(fr) - lum(plate) * r
            t_lv = float(np.clip(np.percentile(di[m], 75) / peak, 0, 1)) if m.any() else 0
            if t_lv < 0.03:
                continue
            level = min(1.0, t_lv / max(r, 1e-3))         # the caption's own alpha
            tint = t_lv / level                 # brightness the text is drawn at (= r unless r was clipped)
            new = fr.copy()
            new[mk] = plate[mk] * r             # restore background under old text, at the frame's fade
            a = la[..., 3:4] / 255 * level
            new = new * (1 - a) + la[..., :3] * tint * a
            Image.fromarray(np.clip(new, 0, 255).astype(np.uint8)).save(os.path.join(out, f'f{i:04d}.png'))
            xml.append(f'<partial-replace frame="{i}" tolerance="6" rect="{x0},{y0},{x1 - x0},{y1 - y0}">f{i:04d}.png</partial-replace>')
            if r < 1:
                report.append(f'  frame {i}: scene fade {r:.3f}, text {t_lv:.3f}, alpha {level:.3f}')
    xml.extend(end_captions(frames, out))
    xml.append('</str-replace>')
    open(os.path.join(out, 'replace.xml'), 'w').write('\n'.join(xml) + '\n')
    return report




# ---- the closing captions: white serif italic on plain black, centre-left, cross-fading ----
END_FONT = FONTS + '/truetype/dejavu/DejaVuSerifCondensed-Italic.ttf'
END_RECT = (55, 84, 292, 138)          # area repainted black
END_CAPS = [
    # (peak frame used to measure the Japanese glyph mask, english lines, top y of first line)
    (1240, ['Out of the nine candidates,', 'the two to be chosen...'], 92),
    (1290, ['...who will they be?'], 101),
]
END_FRAMES = range(1216, 1320)
END_FLOOR = 0.05


def end_captions(frames, out):
    x0, y0, x1, y1 = END_RECT
    font = ImageFont.truetype(END_FONT, 15)
    masks, peaks, layers = [], [], []
    for pf, lines, top in END_CAPS:
        a = lum(load(frames, pf))
        m = np.zeros(a.shape, bool)
        m[y0:y1, x0:x1] = a[y0:y1, x0:x1] > 60
        masks.append(m)
        peaks.append(np.percentile(a[m], 75))
        layer = Image.new('RGBA', (320, 240), (0, 0, 0, 0))
        dr = ImageDraw.Draw(layer)
        for n, t in enumerate(lines):
            dr.text((67, top + n * 20), t, font=font, fill=(245, 245, 245, 255))
        layers.append(np.asarray(layer.filter(ImageFilter.GaussianBlur(0.4)), dtype=np.float32))
    only = [masks[0] & ~masks[1], masks[1] & ~masks[0]]
    # raw level per card; each card's mask also picks up ~0.04 of the other card (encoder halo),
    # so the level is normalised between that floor and the card's own plateau.
    raw = {i: [np.percentile(lum(load(frames, i))[o], 90) / p if o.any() else 0 for o, p in zip(only, peaks)]
           for i in END_FRAMES}
    plateau = [max(v[k] for v in raw.values()) for k in range(len(END_CAPS))]
    xml = []
    for i in END_FRAMES:
        fr = load(frames, i)
        lv = [float(np.clip((v - END_FLOOR) / (pl - END_FLOOR), 0, 1)) for v, pl in zip(raw[i], plateau)]
        if max(lv) < 0.03:
            continue
        new = fr.copy()
        new[y0:y1, x0:x1] = 0
        for la, level in zip(layers, lv):
            al = la[..., 3:4] / 255 * level
            new = new * (1 - al) + la[..., :3] * al
        Image.fromarray(np.clip(new, 0, 255).astype(np.uint8)).save(os.path.join(out, f'f{i:04d}.png'))
        xml.append(f'<partial-replace frame="{i}" tolerance="6" rect="{x0},{y0},{x1 - x0},{y1 - y0}">f{i:04d}.png</partial-replace>')
    return xml


def needed_frames():
    """Sorted list of the decoded frame numbers main() reads (plates, mid frames, caption ranges, closing cards)."""
    need = set()
    for s, e, _ in CAPTIONS:
        need |= {s - 6, (s + e) // 2} | set(range(s - 4, e + 6))
    need |= set(END_FRAMES) | {pf for pf, _, _ in END_CAPS}
    return sorted(need)


if __name__ == '__main__':
    r = main(*sys.argv[1:3])
    print('\n'.join(r) or 'ok')
