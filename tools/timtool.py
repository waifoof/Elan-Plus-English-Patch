"""PS1 TIM image <-> PNG converter and TIM scanner.

  python3 timtool.py scan FILE            list embedded TIMs (offset, bpp, size)
  python3 timtool.py topng FILE OFF OUT   convert TIM at offset to PNG
  python3 timtool.py frompng PNG TIMFILE OFF OUTFILE
        re-encode PNG into the TIM at OFF (same size/bpp, keeps CLUT order)
"""
import struct, sys
from PIL import Image


def c15(v):
    r, g, b = v & 31, (v >> 5) & 31, (v >> 10) & 31
    a = 0 if v == 0 else 255
    return (r << 3 | r >> 2, g << 3 | g >> 2, b << 3 | b >> 2, a)


def to15(rgba):
    r, g, b, a = rgba
    if a < 128:
        return 0
    v = (r >> 3) | (g >> 3) << 5 | (b >> 3) << 10
    return v or 0x8000  # keep opaque black distinct from transparent


def parse(d, off=0):
    if d[off:off + 4] != b'\x10\0\0\0':
        return None
    flags, = struct.unpack_from('<I', d, off + 4)
    pmode, has_clut = flags & 7, bool(flags & 8)
    if pmode > 3 or flags & ~0xF:
        return None
    p = off + 8
    clut = None
    if has_clut:
        ln, cx, cy, cw, ch = struct.unpack_from('<IHHHH', d, p)
        if ln != 12 + cw * ch * 2 or cw == 0:
            return None
        clut = (p + 12, cw, ch)
        p += ln
    elif pmode < 2:
        return None
    ln, ix, iy, iw, ih = struct.unpack_from('<IHHHH', d, p)
    if ln != 12 + iw * ih * 2 or iw == 0 or ih == 0 or p + ln > len(d):
        return None
    w = iw * [4, 2, 1, 1][pmode] if pmode < 3 else iw * 2 // 3
    return dict(off=off, bpp=[4, 8, 16, 24][pmode], clut=clut, pix=p + 12,
                w=w, h=ih, end=p + ln)


def scan(d):
    out, i = [], 0
    while True:
        i = d.find(b'\x10\0\0\0', i)
        if i < 0:
            return out
        t = parse(d, i)
        if t:
            out.append(t)
            i = t['end']
        else:
            i += 4


def to_image(d, t, pal=0):
    w, h, bpp = t['w'], t['h'], t['bpp']
    img = Image.new('RGBA', (w, h))
    px = img.load()
    if bpp in (4, 8):
        co, cw, ch = t['clut']
        cols = [c15(struct.unpack_from('<H', d, co + (pal * cw + k) * 2)[0]) for k in range(cw)]
        p = t['pix']
        for y in range(h):
            for x in range(w):
                if bpp == 4:
                    b = d[p + (y * w + x) // 2]
                    idx = b >> 4 if x & 1 else b & 15
                else:
                    idx = d[p + y * w + x]
                px[x, y] = cols[idx] if idx < len(cols) else (255, 0, 255, 255)
    elif bpp == 16:
        for y in range(h):
            for x in range(w):
                px[x, y] = c15(struct.unpack_from('<H', d, t['pix'] + (y * w + x) * 2)[0])
    return img


def from_image(d, t, img, pal=0):
    d = bytearray(d)
    img = img.convert('RGBA')
    w, h, bpp = t['w'], t['h'], t['bpp']
    assert img.size == (w, h), f'size must stay {w}x{h}'
    px = img.load()
    if bpp in (4, 8):
        co, cw, ch = t['clut']
        cols = [struct.unpack_from('<H', d, co + (pal * cw + k) * 2)[0] for k in range(cw)]
        rgb = [c15(c) for c in cols]
        cache = {}
        def near(c):
            if c not in cache:
                v = to15(c)
                if v in cols:
                    cache[c] = cols.index(v)
                else:
                    cache[c] = min(range(len(rgb)), key=lambda k: sum((a - b) ** 2 for a, b in zip(rgb[k], c)))
            return cache[c]
        p = t['pix']
        for y in range(h):
            for x in range(w):
                idx = near(px[x, y])
                if bpp == 4:
                    o = p + (y * w + x) // 2
                    d[o] = (d[o] & 0x0F) | idx << 4 if x & 1 else (d[o] & 0xF0) | idx
                else:
                    d[p + y * w + x] = idx
    elif bpp == 16:
        for y in range(h):
            for x in range(w):
                struct.pack_into('<H', d, t['pix'] + (y * w + x) * 2, to15(px[x, y]))
    return bytes(d)


if __name__ == '__main__':
    cmd = sys.argv[1]
    if cmd == 'scan':
        d = open(sys.argv[2], 'rb').read()
        for t in scan(d):
            print(f"0x{t['off']:08X} {t['bpp']:2}bpp {t['w']}x{t['h']}")
    elif cmd == 'topng':
        d = open(sys.argv[2], 'rb').read()
        t = parse(d, int(sys.argv[3], 0))
        to_image(d, t).save(sys.argv[4])
    elif cmd == 'frompng':
        d = open(sys.argv[3], 'rb').read()
        t = parse(d, int(sys.argv[4], 0))
        open(sys.argv[5], 'wb').write(from_image(d, t, Image.open(sys.argv[2])))
