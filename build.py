#!/usr/bin/env python3
"""Build the Élan Plus English patch from your own copy of the Japanese disc.

    python3 build.py --disc "Elan Plus (Japan).bin"            full build -> out/ElanPlus_EN.bin/.cue/.xdelta
    python3 build.py --disc "Elan Plus (Japan).bin" prepare    only steps 1-3 (full text with the Japanese, for editing)
    python3 build.py export                                     after editing work/text: write the English back to translation/

Steps (each one's results go under work/, which is never committed):
  1. dump      dumpsxiso: the disc's files -> work/disc, work/disc.xml
  2. unpack    GAME/OUTPUT.BIN -> work/arc/OUTPUT/NNNN.bin
  3. text      translation/*.json + the Japanese read back from the disc -> work/text/<kind>/*.json
  4. graphics  redraw the English labels, Talk help, extras, staff roll -> work/text/bin, elanplus, tables
  5. movies    prologue captions and exam title cards (needs Java + jPSXdec) -> work/text/movie
  6. check     validate every translated row against the original's markup and box limits
  7. patch     build the English disc and the xdelta patch -> out/

External programs (see docs/BUILDING.md; scripts/setup_deps.sh builds them into tools/deps/):
  dumpsxiso / mkpsxiso, xdelta3, java + jpsxdec.jar.
Override any of them with $DUMPSXISO, $MKPSXISO, $XDELTA3, $JPSXDEC (path to the jar), $JAVA.
"""
import argparse, hashlib, os, shutil, subprocess, sys, zlib

ROOT = os.path.dirname(os.path.abspath(__file__))
TOOLS = os.path.join(ROOT, 'tools')
DEPS = os.path.join(TOOLS, 'deps', 'bin')
sys.path.insert(0, TOOLS)

# The original disc this patch is made for (single-track MODE2/2352 dump of SLPS-02759).
ORIG_SIZE = 581_621_376
ORIG_MD5 = '743a8dfa46d8d8f8b9aa49abbaf1b4ec'
STEPS = ['dump', 'unpack', 'text', 'graphics', 'movies', 'check', 'patch']


def tool(env, name):
    if os.environ.get(env):
        return os.environ[env]
    p = os.path.join(DEPS, name)
    if os.path.exists(p):
        return p
    found = shutil.which(name)
    if not found:
        sys.exit(f'{name} not found: run scripts/setup_deps.sh, put it on the PATH, or set ${env}')
    return found


def jpsxdec_jar():
    jar = os.environ.get('JPSXDEC') or os.path.join(DEPS, 'jpsxdec.jar')
    if not os.path.exists(jar):
        sys.exit('jpsxdec.jar not found: run scripts/setup_deps.sh or set $JPSXDEC')
    return jar


def say(step, msg=''):
    print(f'== {step}: {msg}', flush=True)


def check_disc(path):
    size = os.path.getsize(path)
    if size != ORIG_SIZE:
        sys.exit(f'{path}: {size:,} bytes, expected {ORIG_SIZE:,} (single .bin, MODE2/2352). See docs/BUILDING.md.')
    md5, crc = hashlib.md5(), 0
    with open(path, 'rb') as f:
        while b := f.read(1 << 24):
            md5.update(b)
            crc = zlib.crc32(b, crc)
    if md5.hexdigest() != ORIG_MD5:
        sys.exit(f'{path}: MD5 {md5.hexdigest()} (CRC32 {crc:08X}) does not match the known good dump {ORIG_MD5}.')


def step_dump(disc, work):
    if os.path.exists(os.path.join(work, 'disc.xml')):
        return say('dump', 'already done (delete work/ to redo)')
    say('dump', 'extracting the disc')
    os.makedirs(work, exist_ok=True)
    subprocess.run([tool('DUMPSXISO', 'dumpsxiso'), '-x', 'disc', '-s', 'disc.xml', os.path.abspath(disc)],
                   cwd=work, check=True, stdout=subprocess.DEVNULL)


def step_unpack(work):
    import insert_script as ins
    arc = os.path.join(work, 'arc', 'OUTPUT')
    if os.path.isdir(arc) and len(os.listdir(arc)) > 1000:
        return say('unpack', 'already done')
    say('unpack', 'GAME/OUTPUT.BIN')
    os.makedirs(arc, exist_ok=True)
    ents, _ = ins.unpack_archive(open(os.path.join(work, 'disc', 'GAME', 'OUTPUT.BIN'), 'rb').read())
    for k, e in enumerate(ents):
        open(os.path.join(arc, f'{k:04d}.bin'), 'wb').write(e)


def step_text(work):
    import jptext
    text = os.path.join(work, 'text')
    for kind in ('event', 'mk', 'rec', 'code'):
        shutil.rmtree(os.path.join(text, kind), ignore_errors=True)
    n = jptext.fill_dir(os.path.join(ROOT, 'translation'), os.path.join(work, 'disc'),
                        os.path.join(work, 'arc', 'OUTPUT'), text)
    say('text', f'{n} files')


def py(script, *args):
    subprocess.run([sys.executable, os.path.join(TOOLS, script), *args], check=True, stdout=subprocess.DEVNULL)


def step_graphics(work):
    say('graphics', 'labels, prompts, Talk help, extras, staff roll')
    arc, text, disc = os.path.join(work, 'arc', 'OUTPUT'), os.path.join(work, 'text'), os.path.join(work, 'disc')
    out = os.path.join(text, 'bin')
    os.makedirs(out, exist_ok=True)
    py('labels.py', arc, out)
    py('tim_labels.py', arc, out)
    py('extras_labels.py', arc, out, '-', os.path.join(disc, 'GAME', 'ELANPLUS.BIN'),
       os.path.join(text, 'elanplus', 'ELANPLUS.BIN'))
    os.makedirs(os.path.join(text, 'tables'), exist_ok=True)
    py('credits_labels.py', arc, out, '-', os.path.join(disc, 'GAME', 'SIKEN.BIN'),
       os.path.join(text, 'tables', 'SIKEN_BIN_credits.json'))
    # after labels.py: redraws the Talk screen's R2 help labels in the 0514 menu atlas that labels.py wrote
    py('help_labels.py', arc, out, '-', os.path.join(disc, 'GAME', 'GAME.BIN'),
       os.path.join(text, 'tables', 'GAME_BIN_help.json'))


def step_movies(work):
    out = os.path.join(work, 'text', 'movie')
    names = ['PR.STR'] + [f'TEST{i:02d}.STR' for i in range(1, 10)]
    if all(os.path.exists(os.path.join(out, n)) for n in names):
        return say('movies', 'already done')
    say('movies', 're-encoding the prologue and the nine exam title cards (takes a while)')
    env = dict(os.environ)
    if os.environ.get('JAVA'):
        env['JAVA'] = os.environ['JAVA']
    subprocess.run([sys.executable, os.path.join(TOOLS, 'movies.py'), os.path.join(work, 'disc', 'MOVIE'),
                    jpsxdec_jar(), os.path.join(work, 'movie_tmp'), out], check=True, env=env)


def step_check(work):
    import glob
    files = [p for k in ('event', 'mk', 'rec', 'code') for p in sorted(glob.glob(os.path.join(work, 'text', k, '*.json')))]
    r = subprocess.run([sys.executable, os.path.join(TOOLS, 'validate.py'), *files], capture_output=True, text=True)
    bad = [l for l in r.stdout.splitlines() if l.endswith('rows') and ' 0 problems, 0 untranslated' not in l]
    if r.returncode or bad:
        print(r.stdout[-4000:])
        sys.exit('validation failed (see above)')
    say('check', f'{len(files)} files, 0 problems')


def step_patch(disc, work, out):
    say('patch', 'building the disc and the xdelta')
    env = dict(os.environ, MKPSXISO=tool('MKPSXISO', 'mkpsxiso'), XDELTA3=tool('XDELTA3', 'xdelta3'))
    subprocess.run([sys.executable, os.path.join(TOOLS, 'build_patch.py'), work, os.path.join(work, 'text'),
                    os.path.abspath(disc), out], check=True, env=env)
    say('patch', f'done: {out}')


def step_export(work):
    import jptext
    n = 0
    for kind in ('event', 'mk', 'rec', 'code'):
        src = os.path.join(work, 'text', kind)
        if not os.path.isdir(src):
            sys.exit(f'{src} not found: run "build.py --disc ... prepare" first')
        for name in sorted(os.listdir(src)):
            if name.endswith('.json'):
                import json
                doc = json.load(open(os.path.join(src, name), encoding='utf-8'))
                jptext._dump(jptext.strip_doc(doc), os.path.join(ROOT, 'translation', kind, name))
                n += 1
    say('export', f'{n} files written to translation/ (English only)')


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--disc', help='your original "Elan Plus (Japan).bin"')
    ap.add_argument('--work', default=os.path.join(ROOT, 'work'))
    ap.add_argument('--out', default=os.path.join(ROOT, 'out'))
    ap.add_argument('--no-disc-check', action='store_true', help='skip the size/MD5 check of the original')
    ap.add_argument('target', nargs='?', default='all', choices=['all', 'prepare', 'export', *STEPS])
    a = ap.parse_args()
    if a.target == 'export':
        return step_export(a.work)
    if not a.disc:
        ap.error('--disc is required for this step')
    if not a.no_disc_check:
        check_disc(a.disc)
    todo = {'all': STEPS, 'prepare': STEPS[:3]}.get(a.target, [a.target])
    for s in todo:
        if s == 'dump':
            step_dump(a.disc, a.work)
        elif s == 'unpack':
            step_unpack(a.work)
        elif s == 'text':
            step_text(a.work)
        elif s == 'graphics':
            step_graphics(a.work)
        elif s == 'movies':
            step_movies(a.work)
        elif s == 'check':
            step_check(a.work)
        elif s == 'patch':
            step_patch(a.disc, a.work, a.out)


if __name__ == '__main__':
    main()
