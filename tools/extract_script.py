"""Extract all translatable text from OUTPUT.BIN into per-entry JSON files.

Output: <out>/<kind>/<entry>.json, each a list of
  {"id": "...", "jp": "<decoded text with {XX} for raw bytes>", "en": ""}

Kinds:
  event  - bytecode scripts (text op 0x16, choice op 0x20)
  rec    - record files (u32 header + text records separated by 00 00 00 00)
  mk     - full-width markup files (u32 header + one long SJIS stream)
"""
import json, os, sys, struct
sys.path.insert(0, os.path.dirname(__file__))
import elanscript as es


def dec(b: bytes) -> str:
    """Decode SJIS; bytes that do not form valid SJIS become {XX}."""
    out, i = [], 0
    while i < len(b):
        c = b[i]
        if (0x81 <= c <= 0x9F or 0xE0 <= c <= 0xEF) and i + 1 < len(b):
            try:
                ch = b[i:i + 2].decode('cp932')
                if ch.encode('cp932') == b[i:i + 2]:      # only keep pairs that round-trip exactly
                    out.append(ch)
                    i += 2
                    continue
            except (UnicodeDecodeError, UnicodeEncodeError):
                pass
        if 0x20 <= c < 0x7F and c not in (0x7B, 0x7D):
            out.append(chr(c))
        else:
            out.append('{%02X}' % c)
        i += 1
    return ''.join(out)


def classify(b: bytes):
    if b[:4] in (b'\x10\0\0\0', b'ST\x02\0'):
        return None
    try:
        ops, bad, end = es.validate(b)
        if ops and not bad and not b[end:].rstrip(b'\0') and any(o[1] in (0x16, 0x20) for o in ops):
            return 'event'
    except es.ParseError:
        pass
    hdr, = struct.unpack_from('<I', b, 0)
    if hdr < 0x100 and len(b) > 8 and b[4] >= 0x81:
        body = b[4:].rstrip(b'\0')
        # markup files use ｝ (81 70) as block terminator and ＊ (81 96) speaker tags heavily
        if body.count(b'\x81\x70') > 20 and body.count(b'\x81\x96') > 100:
            return 'mk'
        # record files must decode mostly as text (binary tables run ~20-25% raw bytes)
        t = dec(body)
        raw = t.count('{')
        if raw / max(1, len(t)) < 0.10:
            return 'rec'
    return None


def extract_event(b, k):
    rows = []
    for off, op, raw, info in es.parse(b):
        if op == 0x16:
            rows.append({'id': f'{k:04d}:{off:05X}', 'jp': dec(info['text']),
                         'end': info['end'].hex(), 'en': ''})
        elif op == 0x20:
            for n, o in enumerate(info['options']):
                rows.append({'id': f'{k:04d}:{off:05X}.{n}', 'jp': dec(o['text']), 'choice': True, 'en': ''})
    return rows


def extract_rec(b, k):
    hdr, = struct.unpack_from('<I', b, 0)
    body = b[4:].rstrip(b'\0')
    parts = body.split(b'\0\0\0\0')
    return [{'id': f'{k:04d}:r{n:03d}', 'jp': dec(p), 'en': ''} for n, p in enumerate(parts)], hdr


def extract_mk(b, k):
    hdr, = struct.unpack_from('<I', b, 0)
    body = b[4:].rstrip(b'\0')
    # one row per dialogue block, split on the block terminator ｝ (keeps it)
    text = dec(body)
    blocks, cur = [], ''
    for ch in text:
        cur += ch
        if ch == '｝':
            blocks.append(cur)
            cur = ''
    if cur:
        blocks.append(cur)
    return [{'id': f'{k:04d}:b{n:03d}', 'jp': t, 'en': ''} for n, t in enumerate(blocks)], hdr


def main(arcdir, out):
    stats = {}
    for name in sorted(os.listdir(arcdir)):
        k = int(name[:4])
        b = open(os.path.join(arcdir, name), 'rb').read()
        kind = classify(b)
        if not kind:
            continue
        if kind == 'event':
            rows, meta = extract_event(b, k), {}
        elif kind == 'rec':
            rows, h = extract_rec(b, k); meta = {'header': h}
        else:
            rows, h = extract_mk(b, k); meta = {'header': h}
        os.makedirs(os.path.join(out, kind), exist_ok=True)
        with open(os.path.join(out, kind, f'{k:04d}.json'), 'w', encoding='utf-8') as f:
            json.dump({'entry': k, 'kind': kind, **meta, 'rows': rows}, f, ensure_ascii=False, indent=1)
        s = stats.setdefault(kind, [0, 0, 0])
        s[0] += 1; s[1] += len(rows); s[2] += sum(len(r['jp']) for r in rows)
    return stats


if __name__ == '__main__':
    st = main(sys.argv[1], sys.argv[2])
    for k, (f, r, c) in st.items():
        print(f'{k:6} files {f:4}  rows {r:6}  chars {c:8}')
