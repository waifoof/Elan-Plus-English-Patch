"""Separate the game's own Japanese text from the translation, and put it back from the user's disc.

The public repository keeps only the English (plus row ids and layout metadata). At build time the
Japanese source line of every row is re-read from the original game files:

  python3 jptext.py strip <full_dir> <en_dir>          full JSON (with jp) -> repository JSON (no jp)
  python3 jptext.py fill  <en_dir> <disc_dir> <arc_dir> <full_dir>
                                                       repository JSON + original files -> full JSON

disc_dir = dumpsxiso output of the original disc, arc_dir = OUTPUT.BIN unpacked to NNNN.bin.
Row kinds and where their Japanese comes from:
  event  op 0x16 text / op 0x20 choice options at the row's offset (extract_script.extract_event)
  rec    record n of the entry (extract_script.extract_rec); a "tail" (binary trailer kept as text) is
         stored as "tail_len" and re-taken from the end of the record
  mk     block n of the entry (extract_script.extract_mk)
  code   SJIS string of "max" bytes at the row's offset in the module (GAME/*.BIN, the EXE, or an
         OUTPUT.BIN entry for module "OUTPUT:NNNN")
"""
import json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import extract_script as ex

DROP = ('jp', 'tail')
MK_END = '＞{00}'


def strip_doc(doc):
    d = {k: v for k, v in doc.items() if k != 'rows'}
    rows = []
    for r in doc['rows']:
        n = {k: v for k, v in r.items() if k not in DROP}
        if 'tail' in r:
            n['tail_len'] = len(r['tail'])
        rows.append(n)
    if doc['kind'] == 'mk' and rows:
        # the last block ends with the file's binary pointer trailer (copied verbatim by the build):
        # keep the English up to the final ＞{00} and re-take the trailer from the disc
        last = rows[-1]
        i = last.get('en', '').rfind(MK_END)
        if i >= 0:
            last['en'] = last['en'][:i + len(MK_END)]
            last['trailer'] = True
    d['rows'] = rows
    return d


def _module_bytes(module, disc, arc):
    if module.startswith('OUTPUT:'):
        return open(os.path.join(arc, f'{int(module[7:]):04d}.bin'), 'rb').read()
    return open(os.path.join(disc, module), 'rb').read()


def _source_rows(doc, disc, arc):
    """id -> jp for the whole file."""
    kind = doc['kind']
    if kind == 'code':
        data = _module_bytes(doc['module'], disc, arc)
        out = {}
        for r in doc['rows']:
            o = int(r['id'].split(':')[1], 16)
            out[r['id']] = ex.dec(data[o:o + r['max']])
        return out
    b = open(os.path.join(arc, f"{doc['entry']:04d}.bin"), 'rb').read()
    if kind == 'event':
        rows = ex.extract_event(b, doc['entry'])
    elif kind == 'rec':
        rows, _ = ex.extract_rec(b, doc['entry'])
        if not {r['id'] for r in doc['rows']} <= {r['id'] for r in rows}:
            # single-message pointer-indexed file (0842): message, then its pointer table
            import re
            m = re.match(rb'([^\0]*)\0+(.*)', b[4:].rstrip(b'\0'), re.S)
            rows = [{'id': f"{doc['entry']:04d}:r000", 'jp': ex.dec(m.group(1))},
                    {'id': f"{doc['entry']:04d}:r001", 'jp': ex.dec(m.group(2))}]
    else:
        rows, _ = ex.extract_mk(b, doc['entry'])
    return {r['id']: r['jp'] for r in rows}


def fill_doc(doc, disc, arc):
    src = _source_rows(doc, disc, arc)
    d = {k: v for k, v in doc.items() if k != 'rows'}
    rows = []
    for r in doc['rows']:
        if r['id'] not in src:
            raise KeyError(f"{r['id']}: no such line on this disc (is it the right game/version?)")
        jp = src[r['id']]
        n = {}
        for k, v in r.items():          # keep the original key order: id, jp, ...
            if k == 'id':
                n['id'] = v
                n['jp'] = jp
            elif k == 'tail_len':
                n['tail'] = jp[len(jp) - v:]
            elif k == 'trailer':
                n['en'] = n['en'] + jp[jp.rfind(MK_END) + len(MK_END):]
            else:
                n[k] = v
        rows.append(n)
    d['rows'] = rows
    return d


def _walk(root):
    for kind in sorted(os.listdir(root)):
        kd = os.path.join(root, kind)
        if not os.path.isdir(kd):
            continue
        for name in sorted(os.listdir(kd)):
            if name.endswith('.json'):
                yield kind, name, os.path.join(kd, name)


def _dump(doc, path):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(doc, f, ensure_ascii=False, indent=1)
        f.write('\n')


def strip_dir(full, en):
    n = 0
    for kind, name, p in _walk(full):
        doc = json.load(open(p, encoding='utf-8'))
        _dump(strip_doc(doc) if 'rows' in doc else doc, os.path.join(en, kind, name))
        n += 1
    return n


def fill_dir(en, disc, arc, full):
    n = 0
    for kind, name, p in _walk(en):
        doc = json.load(open(p, encoding='utf-8'))
        _dump(fill_doc(doc, disc, arc) if 'rows' in doc else doc, os.path.join(full, kind, name))
        n += 1
    return n


if __name__ == '__main__':
    if sys.argv[1] == 'strip':
        print(strip_dir(sys.argv[2], sys.argv[3]), 'files')
    elif sys.argv[1] == 'fill':
        print(fill_dir(*sys.argv[2:6]), 'files')
    else:
        sys.exit(__doc__)
