"""Rebuild OUTPUT.BIN entries from translation JSON and repack the archive.

For every row: if "en" is non-empty it is encoded and used, otherwise the
original "jp" is re-encoded. Event scripts are rebuilt op by op and every
relative reference is recomputed:
  0x1F goto        target = op + 3 + s16
  0x38 if-goto     target = op + s16           (s16 at op+2)
  0x20 menu option target = field + 2 + s16    (field = u16 position)
"""
import json, os, struct, sys
sys.path.insert(0, os.path.dirname(__file__))
import elanscript as es
import re

ENCODER = None   # set by load_encoder(); maps an English string -> SJIS-code bytes


def enc_jp(s: str) -> bytes:
    """Inverse of extract_script.dec()."""
    out = bytearray()
    for part in re.split(r'(\{[0-9A-F]{2}\})', s):
        if not part:
            continue
        if re.fullmatch(r'\{[0-9A-F]{2}\}', part):
            out.append(int(part[1:3], 16))
        else:
            out += part.encode('cp932')
    return bytes(out)


def row_bytes(r):
    if r.get('en'):
        if ENCODER is None:
            raise RuntimeError('English text present but no encoder loaded')
        return ENCODER(r['en'])
    return enc_jp(r['jp'])


def rebuild_event(orig: bytes, doc) -> bytes:
    rows = {r['id']: r for r in doc['rows']}
    k = doc['entry']
    ops = es.parse(orig)
    end = ops[-1][0] + len(ops[-1][2])
    pieces = []           # (old_off, new_bytes(bytearray), op, info, extra)
    for off, op, raw, info in ops:
        if op == 0x16:
            r = rows[f'{k:04d}:{off:05X}']
            body = row_bytes(r)
            nb = bytearray([0x16]) + body + bytes.fromhex(r['end'])
            pieces.append((off, nb, op, info, None))
        elif op == 0x20:
            nb = bytearray([0x20])
            fields = []
            for n, o in enumerate(info['options']):
                r = rows[f'{k:04d}:{off:05X}.{n}']
                fields.append(len(nb))
                nb += b'\0\0' + row_bytes(r) + b'\0'
            pieces.append((off, nb, op, info, fields))
        else:
            pieces.append((off, bytearray(raw), op, info, None))
    # map old op offsets -> new offsets
    newpos, pos = {}, 0
    for off, nb, op, info, extra in pieces:
        newpos[off] = pos
        pos += len(nb)
    newpos[end] = pos
    # fix references
    for off, nb, op, info, extra in pieces:
        me = newpos[off]
        if op == 0x1F:
            struct.pack_into('<h', nb, 1, newpos[info['target']] - (me + 3))
        elif op == 0x38:
            struct.pack_into('<h', nb, 2, newpos[info['target']] - me)
        elif op in (0x25, 0x26):
            struct.pack_into('<h', nb, 3, newpos[info['target']] - (me + 5))
        elif op == 0x20:
            for o, f in zip(info['options'], extra):
                struct.pack_into('<h', nb, f, newpos[o['target']] - (me + f + 2))
    out = b''.join(bytes(p[1]) for p in pieces)
    check_jumps(k, ops, es.parse(out + orig[end:]))
    return out + orig[end:]            # keep original trailing padding pattern


def check_jumps(k, old_ops, new_ops):
    """Every jump in the rebuilt script must point at the same instruction (by index) as in the original."""
    if [o[1] for o in old_ops] != [o[1] for o in new_ops[:len(old_ops)]]:
        raise ValueError(f'{k}: instruction sequence changed in rebuild')
    def targets(ops):
        idx = {o[0]: n for n, o in enumerate(ops)}
        end = ops[-1][0] + len(ops[-1][2])
        idx[end] = len(ops)
        out = []
        for off, op, raw, info in ops:
            ts = [info['target']] if 'target' in info else [x['target'] for x in info.get('options', [])]
            out.append([idx.get(t, ('bad', t)) for t in ts])
        return out
    a, b = targets(old_ops), targets(new_ops[:len(old_ops)])
    for n, (x, y) in enumerate(zip(a, b)):
        if x != y:
            raise ValueError(f'{k}: jump in op #{n} (0x{old_ops[n][1]:02X}) points to {y}, original {x}')


def rebuild_rec(orig, doc):
    """Mail / notice files: messages + pointer table (see indexed.py)."""
    import indexed
    rows = list(doc['rows'])
    last = rows[-1]
    if last.get('skip') and not re.search(r'[\u3040-\u30ff\u4e00-\u9fff]', last['jp']):
        rows = rows[:-1]                     # the binary pointer table itself
    def text_of(r):
        if r.get('tail') and not r.get('en'):
            return enc_jp(r['jp'][:len(r['jp']) - len(r['tail'])])
        return row_bytes(r)
    body = b'\0\0\0\0'.join(text_of(r) for r in rows)
    return indexed.rebuild(doc['entry'], orig, doc['header'], body)


def rebuild_mk(orig, doc):
    """Free-roam conversation files: messages + pointer table (see indexed.py)."""
    import indexed
    rows = doc['rows']
    head = b''.join(row_bytes(r) for r in rows[:-1])
    last = rows[-1]
    if last.get('en') and '＞{00}' in last['en']:
        en = last['en']
        tail_bytes = row_bytes({'en': en[:en.rfind('＞{00}') + len('＞{00}')]})
    else:
        b = enc_jp(last['jp'])
        tail_bytes = b[:b.rfind(b'\x81\x84\x00') + 3]
    return indexed.rebuild(doc['entry'], orig, doc['header'], head + tail_bytes)


def pack_archive(entries):
    """entries: list of bytes. Returns archive bytes with sector table."""
    n = len(entries)
    table_secs = (n * 8 + 8 + 2047) // 2048
    table = bytearray(table_secs * 2048)
    data = bytearray()
    sec = table_secs
    for i, e in enumerate(entries):
        cnt = (len(e) + 2047) // 2048
        struct.pack_into('<II', table, i * 8, sec, cnt)
        data += e + b'\0' * (cnt * 2048 - len(e))
        sec += cnt
    return bytes(table + data)


def unpack_archive(d):
    first, = struct.unpack_from('<I', d, 0)
    out = []
    for i in range(0, first * 2048, 8):
        s, n = struct.unpack_from('<II', d, i)
        if s == 0 and n == 0:
            break
        out.append(d[s * 2048:(s + n) * 2048])
    return out, first


def build(output_bin, textdir, out_path, table_secs=None):
    d = open(output_bin, 'rb').read()
    entries, first = unpack_archive(d)
    orig_counts = [len(e) // 2048 for e in entries]
    changed = 0
    for kind, fn in (('event', rebuild_event), ('rec', rebuild_rec), ('mk', rebuild_mk)):
        kd = os.path.join(textdir, kind)
        if not os.path.isdir(kd):
            continue
        for name in sorted(os.listdir(kd)):
            doc = json.load(open(os.path.join(kd, name), encoding='utf-8'))
            k = doc['entry']
            orig = entries[k]
            new = fn(orig.rstrip(b'\0') if kind != 'event' else orig, doc)
            if new.rstrip(b'\0') != orig.rstrip(b'\0'):
                changed += 1
            entries[k] = new
    # strings written in place inside archive entries (code overlays, pointer-indexed text)
    cdir = os.path.join(textdir, 'code')
    if os.path.isdir(cdir):
        import code_text
        for name in sorted(os.listdir(cdir)):
            doc = json.load(open(os.path.join(cdir, name), encoding='utf-8'))
            if not doc.get('module', '').startswith('OUTPUT:'):
                continue
            k = int(doc['module'].split(':')[1])
            rows = [r for r in doc['rows'] if not r.get('skip') and r.get('en')]
            if rows:
                new = code_text.patch_module(entries[k], {'rows': rows}, ENCODER)
                if new != entries[k]:
                    changed += 1
                entries[k] = new
    # whole-entry replacements (e.g. redrawn graphics) from <textdir>/bin/NNNN.bin
    bdir = os.path.join(textdir, 'bin')
    if os.path.isdir(bdir):
        for name in sorted(os.listdir(bdir)):
            if name.endswith('.bin') and name[:4].isdigit():
                k = int(name[:4])
                new = open(os.path.join(bdir, name), 'rb').read()
                if new.rstrip(b'\0') != entries[k].rstrip(b'\0'):
                    changed += 1
                entries[k] = new
    arc = pack_archive_like(entries, first, orig_counts)
    open(out_path, 'wb').write(arc)
    return changed


def pack_archive_like(entries, table_secs, orig_counts=None):
    """Same as pack_archive but keeps the original table size and allocations."""
    n = len(entries)
    table = bytearray(table_secs * 2048)
    data = bytearray()
    sec = table_secs
    for i, e in enumerate(entries):
        cnt = (len(e) + 2047) // 2048
        if orig_counts is not None and i < len(orig_counts):
            cnt = max(cnt, orig_counts[i])        # never shrink an original allocation
        struct.pack_into('<II', table, i * 8, sec, cnt)
        data += e + b'\0' * (cnt * 2048 - len(e))
        sec += cnt
    return bytes(table + data)


if __name__ == '__main__':
    n = build(sys.argv[1], sys.argv[2], sys.argv[3])
    print('entries changed:', n)
