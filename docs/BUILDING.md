# Building the patch from source

`build.py` turns this repository plus your own copy of the Japanese disc into the English disc image
and the xdelta patch. The repository holds only the English text and the tools; everything taken
from the game is read from your disc at build time and stays in `work/` and `out/`, which are never
committed.

## Requirements

- **Linux** (or WSL on Windows, see below).
- **Python 3.10+** with Pillow, numpy and scipy:

  ```sh
  pip install -r requirements.txt
  ```

- To build the external programs: **git**, **cmake**, a **C/C++ compiler**, a **JDK 17+** and
  **Apache Ant 1.10**. On Debian/Ubuntu:

  ```sh
  sudo apt install git cmake build-essential default-jdk ant
  ```

  The release was built with OpenJDK 21 and Ant 1.10.17. `java` must be on the `PATH` for the
  movie step (or set `$JAVA`).

### External programs: `scripts/setup_deps.sh`

```sh
scripts/setup_deps.sh
```

This clones and builds three programs into `tools/deps/` (sources in `tools/deps/src/`, binaries in
`tools/deps/bin/`), each pinned to the exact commit the release was built with:

| Program | Used for | Source | Commit |
|---|---|---|---|
| `dumpsxiso`, `mkpsxiso` | extracting and rebuilding the disc | [Lameguy64/mkpsxiso](https://github.com/Lameguy64/mkpsxiso) (GPL-2.0) | `a6b11ea` |
| `xdelta3` | making the patch | [jmacd/xdelta](https://github.com/jmacd/xdelta) (Apache-2.0) | `5d936d2` |
| `jpsxdec.jar` + `jpsxdec-lib.jar` | re-encoding the movies (jPSXdec v2.1) | [m35/jpsxdec](https://github.com/m35/jpsxdec) | `fd54036` (`fd5403629ac81aaca0feff0dc89e6cadd6353b26`) |

`jpsxdec-lib.jar` must stay next to `jpsxdec.jar`. Running jPSXdec needs Java 8 or newer (tested
with OpenJDK 21); building it needs the JDK 17+ listed above.

jPSXdec's own build treats compiler warnings as errors, which newer JDKs trip over; the script
removes that flag before running `ant release`. Other jPSXdec versions may re-encode the movies
slightly differently: the game still works, but the result won't be byte-identical to the release.

`build.py` looks for each program in this order: the environment variable below, `tools/deps/bin/`,
then the `PATH`.

## Your disc

The build needs a dump of the original Japanese disc (SLPS-02759) as a **single-track MODE2/2352
`.bin`**:

| | |
|---|---|
| Size | 581,621,376 bytes |
| CRC32 | `91D628D6` |
| MD5 | `743a8dfa46d8d8f8b9aa49abbaf1b4ec` |
| SHA-1 | `947de2fba102fa48c63e39ce880eaddcec91b9b4` |

(Also in [CHECKSUMS.md](../CHECKSUMS.md).)

`build.py` checks the size and MD5 before it starts and stops if they don't match.
(`--no-disc-check` skips the check, but a different dump will not build a working image.)

## Build

```sh
python3 build.py --disc "Elan Plus (Japan).bin"
```

That runs every step and writes:

- `out/ElanPlus_EN.bin` and `out/ElanPlus_EN.cue`, the patched disc image;
- `out/ElanPlus_EN.xdelta`, the patch against your original `.bin`;
- `out/pairs.json`, the letter-pair table used for the font (useful for debugging).

**The build is deterministic:** with the pinned dependencies, `out/ElanPlus_EN.bin` should have
exactly the checksums listed for the patched result in [CHECKSUMS.md](../CHECKSUMS.md).

Patched result: see CHECKSUMS.md

### Steps

Each step writes under `work/` (change it with `--work`; the output folder with `--out`). Any step
can be run on its own, e.g. `python3 build.py --disc ... graphics`. `prepare` runs steps 1-3 only.

| # | Step | What it does | Writes |
|---|---|---|---|
| 1 | `dump` | Extracts the disc's files with dumpsxiso. Skipped if already done (delete `work/` to redo). | `work/disc/`, `work/disc.xml` |
| 2 | `unpack` | Splits the game's main archive `GAME/OUTPUT.BIN` into its entries. | `work/arc/OUTPUT/NNNN.bin` |
| 3 | `text` | Combines `translation/*/*.json` with the Japanese read back from the disc, so every row has its source line next to the English. | `work/text/{event,mk,rec,code}/*.json` |
| 4 | `graphics` | Redraws the English labels and prompts, the Talk screen help (R2), the Extras screens and the staff roll, using the fonts in `fonts/`. | `work/text/bin/`, `work/text/elanplus/ELANPLUS.BIN`, `work/text/tables/SIKEN_BIN_credits.json`, `work/text/tables/GAME_BIN_help.json` |
| 5 | `movies` | Runs `tools/movies.py`: re-encodes the prologue (`PR.STR`, English captions) and the nine exam title cards (`TEST01`-`TEST09.STR`) with jPSXdec. Needs Java; takes about 3 minutes and about 400 MB of temporary space (`work/movie_tmp/`, deleted afterwards). Skipped if already done. | `work/text/movie/*.STR` |
| 6 | `check` | Validates every translated row against the original's markup and the text-box limits. The build stops on any problem. | (nothing) |
| 7 | `patch` | Inserts the text and graphics, rebuilds the disc with mkpsxiso and makes the xdelta. | `out/` |

Steps 3, 4, 6 and 7 always run again; steps 1, 2 and 5 reuse their earlier results. Note that step 3
regenerates `work/text/` from `translation/`, so if you are editing text, run `build.py export`
first (see [TRANSLATING.md](TRANSLATING.md)).

## Environment overrides

| Variable | Meaning |
|---|---|
| `DUMPSXISO` | path to `dumpsxiso` |
| `MKPSXISO` | path to `mkpsxiso` |
| `XDELTA3` | path to `xdelta3` |
| `JAVA` | path to the `java` executable used for jPSXdec (default: `java` on the `PATH`) |
| `JPSXDEC` | path to `jpsxdec.jar` |
| `ELAN_FONTS` | folder with the fonts for the redrawn graphics, laid out like `fonts/` (`opentype/inter/...`, `truetype/crosextra/...`, `truetype/dejavu/...`). Default: the repository's `fonts/` folder. |

## Notes

- The movie step can also be run by hand, e.g. to redo only some movies:

  ```sh
  python3 tools/movies.py work/disc/MOVIE tools/deps/bin/jpsxdec.jar work/movie_tmp work/text/movie --only PR,TEST01
  ```

  (`--keep` keeps the temporary folder for inspection.)

- `xdelta3` with a 1 GB source window (`-B 1073741824`) needs a fair amount of memory. If it is
  killed during the patch step, run it on its own:

  ```sh
  xdelta3 -e -9 -S djw -B 1073741824 -s "Elan Plus (Japan).bin" out/ElanPlus_EN.bin out/ElanPlus_EN.xdelta
  ```

  and check it by applying it (`xdelta3 -d -B 1073741824 ...`) and comparing the result with `cmp`.
- The patched image is about 45 MB larger than the original: the rebuilt `OUTPUT.BIN` is moved to the
  end of the disc. See [ENGINE_NOTES.md](ENGINE_NOTES.md#disc) for details.

## Windows

Use **WSL** (Windows Subsystem for Linux) with Ubuntu: install the packages above inside WSL, clone
the repository there and run the same commands. Your disc image can stay on the Windows side, e.g.
`--disc "/mnt/c/Games/Elan Plus (Japan).bin"`, though building is faster with the repository in the
WSL file system.
