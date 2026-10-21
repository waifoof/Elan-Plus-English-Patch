"""Build a patched Élan Plus disc + xdelta from translation JSON.

  python3 build_patch.py <work_dir> <text_dir> <original.bin> <out_dir>

work_dir must contain disc/ (dumpsxiso output) and disc.xml.
Writes out_dir/ElanPlus_EN.bin/.cue, out_dir/ElanPlus_EN.xdelta, pairs.json
"""
import json, os, shutil, struct, subprocess, sys, glob
sys.path.insert(0, os.path.dirname(__file__))
import insert_script as ins
import relocate
import code_text
from pairfont import PairTable

TOOLS = os.path.dirname(os.path.abspath(__file__))


def _tool(env, name, local):
    """External program: $ENV, then tools/deps/<local>, then the PATH."""
    if os.environ.get(env):
        return os.environ[env]
    p = os.path.join(TOOLS, local)
    return p if os.path.exists(p) else (shutil.which(name) or name)


MKPSXISO = _tool('MKPSXISO', 'mkpsxiso', 'deps/bin/mkpsxiso')
XDELTA = _tool('XDELTA3', 'xdelta3', 'deps/bin/xdelta3')


def mirror_old_output(orig_img, img_path, new_output, orig_output):
    """Some loaders (e.g. the prologue overlay) read OUTPUT.BIN entries at their original
    LBAs. Write every changed entry that still fits its original allocation back into
    the old OUTPUT.BIN extent, sector by sector, keeping each sector's subheader."""
    from cdsector import fix_sector
    SECTOR = 2352
    _, _, extent, _ = relocate.find_record(bytearray(open(orig_img, 'rb').read(4000 * SECTOR)), 'GAME/OUTPUT.BIN')
    old = open(orig_output, 'rb').read()
    new = open(new_output, 'rb').read()
    old_ents, first = ins.unpack_archive(old)
    new_ents, _ = ins.unpack_archive(new)
    tab = [struct.unpack_from('<II', old, i * 8) for i in range(len(old_ents))]
    buf = bytearray(open(img_path, 'rb').read())
    n = 0
    for k, (o, nw) in enumerate(zip(old_ents, new_ents)):
        start, cnt = tab[k]
        body = nw.rstrip(b'\0')
        if body == o.rstrip(b'\0') or len(body) > cnt * 2048:
            continue
        data = body + b'\0' * (cnt * 2048 - len(body))
        for j in range(cnt):
            lba = extent + start + j
            sec = bytearray(buf[lba * SECTOR:(lba + 1) * SECTOR])
            sec[0x18:0x18 + 2048] = data[j * 2048:(j + 1) * 2048]
            fix_sector(sec, lba)
            buf[lba * SECTOR:(lba + 1) * SECTOR] = sec
        n += 1
    open(img_path, 'wb').write(buf)
    return n


def main(work, textdir, orig_bin, out):
    work, textdir, orig_bin, out = map(os.path.abspath, (work, textdir, orig_bin, out))
    os.makedirs(out, exist_ok=True)
    stage = os.path.join(out, 'stage')
    if os.path.exists(stage):
        shutil.rmtree(stage)
    shutil.copytree(os.path.join(work, 'disc'), os.path.join(stage, 'disc'))

    # 1. collect every English string, allocate letter pairs
    strings = []
    for p in sorted(glob.glob(os.path.join(textdir, '*', '*.json'))):   # sorted: same pair table on every machine
        doc = json.load(open(p, encoding='utf-8'))
        if 'rows' not in doc:
            continue                     # binary patch tables (e.g. tables/SIKEN_BIN_credits.json)
        rows = doc['rows']
        for i, r in enumerate(rows):
            if r.get('en') and not r.get('skip'):
                en = r['en']
                if doc.get('kind') == 'mk' and i == len(rows) - 1 and '＞{00}' in en:
                    en = en[:en.rfind('＞{00}') + len('＞{00}')]   # binary trailer: original bytes are reused
                strings.append(en)
    pt = PairTable()
    npairs = pt.collect(strings)
    pt.save(os.path.join(out, 'pairs.json'))
    ins.ENCODER = pt.encode
    print(f'{len(strings)} translated rows, {npairs} letter pairs')

    # 2. script archive (built to a side file; the disc is first mastered with the
    #    ORIGINAL OUTPUT.BIN so every file keeps its original LBA)
    new_output = os.path.join(out, 'OUTPUT.BIN.new')
    n = ins.build(os.path.join(work, 'disc/GAME/OUTPUT.BIN'), textdir, new_output)
    print('OUTPUT.BIN entries changed:', n)

    # 2b. interface strings inside the code modules (in place, sizes unchanged)
    cdir = os.path.join(textdir, 'code')
    if os.path.isdir(cdir):
        for name in sorted(os.listdir(cdir)):
            doc = json.load(open(os.path.join(cdir, name), encoding='utf-8'))
            if doc['module'].startswith('OUTPUT:'):
                continue
            if not any(r.get('en') and not r.get('skip') for r in doc['rows']):
                continue
            mp = os.path.join(stage, 'disc', doc['module'])
            orig = open(mp, 'rb').read()
            rows = [r for r in doc['rows'] if not r.get('skip')]
            new = code_text.patch_module(orig, {'rows': rows}, pt.encode)
            assert len(new) == len(orig)
            open(mp, 'wb').write(new)
            print(f"{doc['module']}: {sum(1 for r in rows if r.get('en'))} strings patched")

    # 2b''. staff-roll layout table in SIKEN.BIN (goes with the redrawn credits TIMs 0864-0868;
    #       see tools/credits_labels.py)
    import credits_labels
    sp = os.path.join(stage, 'disc', 'GAME/SIKEN.BIN')
    s0 = open(sp, 'rb').read()
    s1 = credits_labels.patch_siken(s0, os.path.join(textdir, 'tables', 'SIKEN_BIN_credits.json'))
    assert len(s1) == len(s0)
    open(sp, 'wb').write(s1)
    print('SIKEN.BIN: staff-roll sprite table patched')

    # 2b'. table addresses of the pointer-indexed files (mail, conversations) in GAME.BIN
    import indexed
    orig_ents, _ = ins.unpack_archive(open(os.path.join(work, 'disc/GAME/OUTPUT.BIN'), 'rb').read())
    orig_tables = {k: indexed.table_start(orig_ents[k].rstrip(b'\0')) for k in indexed.MOVES}
    gp = os.path.join(stage, 'disc', 'GAME/GAME.BIN')
    g, n = indexed.patch_game_bin(open(gp, 'rb').read(), orig_tables)
    open(gp, 'wb').write(g)
    print(f'GAME.BIN: {n} table addresses moved for {len(indexed.MOVES)} indexed files')
    new_ents, _ = ins.unpack_archive(open(new_output, 'rb').read())
    probs = indexed.verify(g, new_ents)
    if probs:
        raise SystemExit('pointer-table check failed:\n' + '\n'.join(probs[:20]))
    print('pointer tables verified')

    # 2c. re-encoded movies (same size as the originals; see tools/str_captions.py)
    mdir = os.path.join(textdir, 'movie')
    if os.path.isdir(mdir):
        for name in sorted(os.listdir(mdir)):
            dst = os.path.join(stage, 'disc', 'MOVIE', name)
            assert os.path.getsize(os.path.join(mdir, name)) == os.path.getsize(dst), name
            shutil.copyfile(os.path.join(mdir, name), dst)
            print('movie replaced:', name)

    # 2d. whole-file replacements for the other archive (same size; see tools/extras_labels.py:
    #     the Gallery page help graphic lives in GAME/ELANPLUS.BIN)
    edir = os.path.join(textdir, 'elanplus')
    if os.path.isdir(edir):
        for name in sorted(os.listdir(edir)):
            dst = os.path.join(stage, 'disc', 'GAME', name)
            assert os.path.getsize(os.path.join(edir, name)) == os.path.getsize(dst), name
            shutil.copyfile(os.path.join(edir, name), dst)
            print('GAME file replaced:', name)

    # 3. font
    fp = os.path.join(stage, 'disc/GAME/FONT.BIN')
    font = open(fp, 'rb').read()
    patched = pt.patch_font(font)
    assert len(patched) == len(font)
    open(fp, 'wb').write(patched)

    # 4. disc image
    xml = open(os.path.join(work, 'disc.xml')).read()
    open(os.path.join(stage, 'disc.xml'), 'w').write(xml)
    binp = os.path.join(out, 'ElanPlus_EN.bin')
    cuep = os.path.join(out, 'ElanPlus_EN.cue')
    tmp = binp + '.tmp'
    subprocess.run([MKPSXISO, '-y', '-q', '-o', tmp, '-c', cuep, 'disc.xml'], cwd=stage, check=True)
    info = relocate.replace_file(tmp, 'GAME/OUTPUT.BIN', open(new_output, 'rb').read(), binp)
    if info['moved']:
        n = mirror_old_output(orig_bin, binp, new_output, os.path.join(work, 'disc/GAME/OUTPUT.BIN'))
        print(f'{n} changed entries also written into the original OUTPUT.BIN location')
    os.remove(tmp)
    os.remove(new_output)
    print('OUTPUT.BIN', 'moved to end of disc' if info['moved'] else 'written in place',
          f"(LBA {info['lba']}, {info['sectors']} sectors, original {info['old_sectors']})")
    open(cuep, 'w').write('FILE "ElanPlus_EN.bin" BINARY\n  TRACK 01 MODE2/2352\n    INDEX 01 00:00:00\n')

    # 5. patch
    xd = os.path.join(out, 'ElanPlus_EN.xdelta')
    if os.path.exists(xd):
        os.remove(xd)
    subprocess.run([XDELTA, '-e', '-9', '-S', 'djw', '-B', str(1 << 30), '-s', orig_bin, binp, xd], check=True)
    print('disc', os.path.getsize(binp), 'patch', os.path.getsize(xd))
    shutil.rmtree(stage)


if __name__ == '__main__':
    main(*sys.argv[1:5])
