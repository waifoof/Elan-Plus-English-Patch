#!/usr/bin/env bash
# Build the external programs the patch build needs into tools/deps/bin/.
#   mkpsxiso + dumpsxiso   (Lameguy64/mkpsxiso, GPL-2.0)   disc extract / rebuild
#   xdelta3                (jmacd/xdelta, Apache-2.0)        patch file
#   jpsxdec.jar            (m35/jpsxdec, see its licence)    movie re-encode (needs a JDK 17+ and Apache Ant 1.10)
#                          (the release was built with OpenJDK 21 and Ant 1.10.17)
# Requires: git, cmake, a C/C++ compiler, a JDK and ant. On Debian/Ubuntu:
#   sudo apt install git cmake build-essential default-jdk ant
# The exact commits below are the ones the release was built with; other versions of jPSXdec may
# re-encode the movies differently (the game still works, but the patch won't be byte-identical).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DEPS="$ROOT/tools/deps"
SRC="$DEPS/src"
BIN="$DEPS/bin"
mkdir -p "$SRC" "$BIN"

MKPSXISO_COMMIT=a6b11ea
XDELTA_COMMIT=5d936d2
JPSXDEC_COMMIT=fd54036

fetch() {  # fetch <url> <dir> <commit>
  if [ ! -d "$2/.git" ]; then git clone --recursive "$1" "$2"; fi
  git -C "$2" fetch --quiet origin || true
  git -C "$2" checkout --quiet "$3"
  git -C "$2" submodule update --init --recursive --quiet
}

echo "== mkpsxiso / dumpsxiso"
fetch https://github.com/Lameguy64/mkpsxiso.git "$SRC/mkpsxiso" "$MKPSXISO_COMMIT"
cmake -S "$SRC/mkpsxiso" -B "$SRC/mkpsxiso/build" -DCMAKE_BUILD_TYPE=Release >/dev/null
cmake --build "$SRC/mkpsxiso/build" --config Release -j >/dev/null
find "$SRC/mkpsxiso/build" -type f \( -name mkpsxiso -o -name dumpsxiso -o -name mkpsxiso.exe -o -name dumpsxiso.exe \) \
  -exec cp {} "$BIN/" \;

echo "== xdelta3"
fetch https://github.com/jmacd/xdelta.git "$SRC/xdelta" "$XDELTA_COMMIT"
cmake -S "$SRC/xdelta/xdelta3" -B "$SRC/xdelta/build" -DCMAKE_BUILD_TYPE=Release >/dev/null
cmake --build "$SRC/xdelta/build" --config Release -j >/dev/null
find "$SRC/xdelta/build" -type f \( -name xdelta3 -o -name xdelta3.exe \) -exec cp {} "$BIN/" \;

echo "== jPSXdec"
fetch https://github.com/m35/jpsxdec.git "$SRC/jpsxdec" "$JPSXDEC_COMMIT"
# newer JDKs warn on this tree; the upstream build treats warnings as errors
sed -i 's|<compilerarg value="-Werror"/>||' "$SRC/jpsxdec/jpsxdec/build.xml"
(cd "$SRC/jpsxdec/jpsxdec" && ant -q release >/dev/null)
cp "$SRC/jpsxdec/jpsxdec/_ant/release/jpsxdec.jar" "$SRC/jpsxdec/jpsxdec/_ant/release/jpsxdec-lib.jar" "$BIN/"

echo "== done: $(ls "$BIN" | tr '\n' ' ')"
