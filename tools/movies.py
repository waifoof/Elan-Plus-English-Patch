"""Rebuild the English movies (MOVIE/PR.STR and MOVIE/TEST01..09.STR) from the original disc files.

  python3 movies.py <orig_movie_dir> <jpsxdec_jar> <work_dir> <out_dir> [--keep] [--only PR,TEST01,...]

  orig_movie_dir  the original disc's MOVIE folder (PR.STR, TEST01.STR ... TEST09.STR are read, never written)
  jpsxdec_jar     jPSXdec v2.1 jar (built from github.com/m35/jpsxdec, see docs/BUILDING.md)
  work_dir        scratch folder (created; deleted at the end unless --keep)
  out_dir         gets PR.STR and TEST01..09.STR (same sizes as the originals)

Per movie: index the original with jPSXdec, decode only the frames the tool reads (png, jPSXdec's default
high quality / bicubic), run str_captions.main() or exam_cards.main() on them, copy the original to
out_dir, index the copy and run jPSXdec -replaceframes with the tool's replace.xml (from the folder that
holds the replacement pngs). Fonts come from fontpath.FONTS (env ELAN_FONTS, else the repo's fonts/).
Needs java (8+) on PATH, python3 with numpy, Pillow and scipy.
"""
import argparse, os, shutil, subprocess, sys, time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import exam_cards, str_captions

TESTS = range(1, 10)


def ranges(frames):
    """[n, n+1, ...] -> [(start, end)] runs"""
    out = []
    for f in frames:
        if out and f == out[-1][1] + 1:
            out[-1][1] = f
        else:
            out.append([f, f])
    return [tuple(r) for r in out]


class Jpsxdec:
    def __init__(self, jar, log, cwd):
        self.jar, self.log, self.cwd = os.path.abspath(jar), log, cwd

    def run(self, args, cwd=None):
        cwd = cwd or self.cwd                   # jPSXdec writes index.log/save.log/debug00.log into its cwd
        cmd = [os.environ.get('JAVA', 'java'), '-jar', self.jar] + args
        self.log.write(f'$ (cd {cwd}) ' + ' '.join(cmd) + '\n')
        self.log.flush()
        r = subprocess.run(cmd, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        self.log.write(r.stdout)
        if r.returncode != 0:
            sys.exit(f'jPSXdec failed ({r.returncode}): {" ".join(cmd)}\n{r.stdout[-2000:]}')
        return r.stdout

    def index(self, str_path, idx_path):
        # absolute paths: the index stores the source file name as given
        self.run(['-f', os.path.abspath(str_path), '-x', os.path.abspath(idx_path)])

    def decode(self, idx_path, out_dir, start, end):
        os.makedirs(out_dir, exist_ok=True)
        self.run(['-x', os.path.abspath(idx_path), '-i', '0', '-vf', 'png', '-dir', os.path.abspath(out_dir),
                  '-start', str(start), '-end', str(end)])

    def replace(self, idx_path, xml_dir):
        self.run(['-x', os.path.abspath(idx_path), '-i', '0', '-replaceframes', 'replace.xml'], cwd=xml_dir)


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('orig_movie_dir')
    ap.add_argument('jpsxdec_jar')
    ap.add_argument('work_dir')
    ap.add_argument('out_dir')
    ap.add_argument('--keep', action='store_true', help='keep work_dir (decoded frames, replacement pngs, logs)')
    ap.add_argument('--only', default='', help='comma list of movies to build, e.g. PR,TEST09 (default all)')
    a = ap.parse_args()
    only = {s.strip().upper().removesuffix('.STR') for s in a.only.split(',') if s.strip()}
    want = lambda n: not only or n in only
    t0 = time.time()
    work, out = os.path.abspath(a.work_dir), os.path.abspath(a.out_dir)
    os.makedirs(work, exist_ok=True)
    os.makedirs(out, exist_ok=True)
    log = open(os.path.join(work, 'jpsxdec.log'), 'w')
    jp = Jpsxdec(a.jpsxdec_jar, log, work)

    def apply(name, rep_dir):
        dst = os.path.join(out, name + '.STR')
        shutil.copyfile(os.path.join(a.orig_movie_dir, name + '.STR'), dst)
        idx = os.path.join(work, name + '_en.idx')
        jp.index(dst, idx)
        jp.replace(idx, rep_dir)
        n = sum(1 for l in open(os.path.join(rep_dir, 'replace.xml')) if '<partial-replace' in l)
        print(f'{name}.STR: {n} frames replaced ({time.time() - t0:.0f}s)', flush=True)

    # ---- PR.STR: prologue captions ----
    if want('PR'):
        w = os.path.join(work, 'PR')
        frames, rep = os.path.join(w, 'frames'), os.path.join(w, 'rep')
        os.makedirs(w, exist_ok=True)
        idx = os.path.join(w, 'orig.idx')
        jp.index(os.path.join(a.orig_movie_dir, 'PR.STR'), idx)
        for s, e in ranges(str_captions.needed_frames()):
            jp.decode(idx, frames, s, e)
        report = str_captions.main(frames, rep)
        if report:
            print('\n'.join('  ' + l for l in report))
        apply('PR', rep)
        if not a.keep:
            shutil.rmtree(frames)

    # ---- TEST01..09.STR: exam title cards ----
    tests = [n for n in TESTS if want(f'TEST{n:02d}')]
    if tests:
        w = os.path.join(work, 'TEST')
        for n in tests:
            idx = os.path.join(w, f't{n}.idx')
            os.makedirs(w, exist_ok=True)
            jp.index(os.path.join(a.orig_movie_dir, f'TEST{n:02d}.STR'), idx)
            jp.decode(idx, os.path.join(w, 'frames', f'f{n}'), exam_cards.FIRST, exam_cards.LAST)
        exam_cards.main(os.path.join(w, 'frames'), os.path.join(w, 'rep'), tests)
        for n in tests:
            apply(f'TEST{n:02d}', os.path.join(w, 'rep', str(n)))

    log.close()
    if not a.keep:
        shutil.rmtree(work)
    print(f'done in {time.time() - t0:.0f}s -> {out}')


if __name__ == '__main__':
    main()
