"""Copy the current redrawn textures into the VRAM of a save state (for screenshots/tests only).

  python3 vram_paint.py <in.state> <out.state>

For each redrawn texture, an unchanged stretch of pixels (same in the original and the new file)
is searched for in VRAM to find where the game put that texture; then every row of the new texture
is written there. Textures the state doesn't hold are skipped.
"""
import os, sys
sys.path.insert(0, os.path.dirname(__file__))
import labels, timtool

VR = 2725701                     # VRAM offset in a PCSX-ReARMed state (1024x512 16-bit words)
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ARC = os.environ.get('ELAN_ARC', os.path.join(_ROOT, 'work', 'arc', 'OUTPUT'))
BIN = os.environ.get('ELAN_BIN', os.path.join(_ROOT, 'work', 'text', 'bin'))

# (file, kind, offset): 'atlas' = 4bpp 256x? block at offset (labels.Atlas), 'tim' = TIM at offset
TEXTURES = [(514, 'atlas', 0x17AB4, 244), (514, 'atlas', labels.MENU_BASE, 246),
            (538, 'tim', 0x0, 0), (997, 'tim', 0, 0), (995, 'tim', 0, 0),
            (870, 'tim', 0, 0), (872, 'tim', 0, 0), (909, 'tim', 0, 0), (910, 'tim', 0, 0)]


def rows_of(data, kind, off, nrows):
    """-> (list of row byte strings, bytes per row)"""
    if kind == 'atlas':
        rb = labels.ROW
        return [data[off + y * rb: off + (y + 1) * rb] for y in range(nrows)], rb
    t = timtool.parse(bytearray(data), off)
    rb = t['w'] * t['bpp'] // 8
    return [data[t['pix'] + y * rb: t['pix'] + (y + 1) * rb] for y in range(t['h'])], rb


def locate(vram, old_rows, new_rows, rb):
    """Find the VRAM byte offset of row 0: a candidate position must match at least 80% of the
    texture's unchanged, non-blank rows exactly (avoids false matches on repeated patterns)."""
    ref = [(y, a) for y, (a, b) in enumerate(zip(old_rows, new_rows)) if a == b and len(set(a)) > 4]
    if len(ref) < 4:
        return None
    tried = set()
    for y, a in ref[:12]:
        for x0 in range(0, rb - 16, 8):
            chunk = a[x0:x0 + 16]
            if len(set(chunk)) < 6:
                continue
            i = vram.find(chunk)
            while i >= 0:
                base = i - x0 - y * 2048
                if base not in tried and base >= 0:
                    tried.add(base)
                    hits = sum(vram[base + yy * 2048: base + yy * 2048 + rb] == r for yy, r in ref)
                    if hits >= 0.8 * len(ref):
                        return base
                i = vram.find(chunk, i + 1)
    return None


def paint(state_in, state_out):
    st = bytearray(open(state_in, 'rb').read())
    vram = bytes(st[VR:VR + 1024 * 512 * 2])
    done = []
    used = set()
    for k, kind, off, n in TEXTURES:
        old = open(os.path.join(ARC, f'{k:04d}.bin'), 'rb').read()
        newp = os.path.join(BIN, f'{k:04d}.bin')
        if not os.path.exists(newp):
            continue
        new = open(newp, 'rb').read()
        orow, rb = rows_of(old, kind, off, n)
        nrow, _ = rows_of(new, kind, off, n)
        base = locate(vram, orow, nrow, rb)
        if base is None or base in used:
            continue
        used.add(base)
        for y, (r, r0) in enumerate(zip(nrow, orow)):
            if r == r0:
                continue                 # only rows the redraw changed (the label rows)
            o = VR + base + y * 2048
            if len(r) != rb or base + y * 2048 + rb > 1024 * 512 * 2:
                break                    # past the end of the texture data or of VRAM
            st[o:o + rb] = r
        done.append(f'{k:04d}@{off:X}')
    open(state_out, 'wb').write(st)
    return done


if __name__ == '__main__':
    print(paint(sys.argv[1], sys.argv[2]))
