"""Interface strings embedded in the code modules (written back in place).

  python3 code_text.py extract <disc_dir> <out_dir>
      -> <out_dir>/code/<MODULE>.json  rows: id "<MODULE>:<hex off>", jp, max (bytes), en
Insertion (used by build_patch): patch_module(data, doc, encoder) -> bytes
English is encoded with the pair encoder and must fit in "max" bytes;
the rest of the original slot is zero-filled, so no pointers change.
"""
import json, os, sys

MODULES = ['SLPS_027.59', 'GAME/GAME.BIN', 'GAME/TITLE.BIN', 'GAME/SIKEN.BIN']


def find_strings(d, minchars=2):
    out, i = [], 0
    while i < len(d) - 1:
        j, n = i, 0
        while j < len(d) - 1 and (0x81 <= d[j] <= 0x9F or 0xE0 <= d[j] <= 0xEA) and 0x40 <= d[j + 1] <= 0xFC:
            j += 2; n += 1
        if n >= minchars and j < len(d) and d[j] == 0 and (i == 0 or not (0x81 <= d[i - 1] <= 0x9F or 0xE0 <= d[i - 1] <= 0xEF)):
            try:
                s = d[i:j].decode('cp932')
                if s.encode('cp932') == d[i:j]:
                    out.append((i, j - i, s))
                    i = j + 1
                    continue
            except UnicodeDecodeError:
                pass
        i += 1
    return out


def extract(disc, out):
    os.makedirs(os.path.join(out, 'code'), exist_ok=True)
    for m in MODULES:
        d = open(os.path.join(disc, m), 'rb').read()
        name = os.path.basename(m).replace('.', '_')
        rows = [{'id': f'{name}:{o:05X}', 'jp': s, 'max': n, 'en': ''} for o, n, s in find_strings(d)]
        json.dump({'module': m, 'kind': 'code', 'rows': rows},
                  open(os.path.join(out, 'code', name + '.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
        print(f'{m:16} {len(rows):4} strings')


def patch_module(data, doc, encoder):
    d = bytearray(data)
    for r in doc['rows']:
        if not r.get('en'):
            continue
        o = int(r['id'].split(':')[1], 16)
        b = encoder(r['en'])
        if len(b) > r['max']:
            raise ValueError(f"{r['id']}: English needs {len(b)} bytes, slot is {r['max']}")
        d[o:o + r['max']] = b + b'\0' * (r['max'] - len(b))
    return bytes(d)


if __name__ == '__main__':
    if sys.argv[1] == 'extract':
        extract(sys.argv[2], sys.argv[3])
