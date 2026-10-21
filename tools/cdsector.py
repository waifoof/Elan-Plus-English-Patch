"""PS1 Mode 2 raw-sector helpers: read user data, rebuild EDC/ECC.

Sector layout (2352 bytes, Mode 2 XA):
  0x000 sync (12)  0x00C header (4: min sec frame mode)
  0x010 subheader (8: file chan submode coding, repeated)
  Form 1: 0x018 data(2048) 0x818 EDC(4) 0x81C ECC P(172) Q(104)
  Form 2: 0x018 data(2324) 0x92C EDC(4, may be 0)
"""
import struct

SECTOR = 2352
SYNC = bytes([0] + [0xFF] * 10 + [0])

# ---- EDC (CRC32 variant, poly 0xD8018001 reflected) ----
_EDC = []
for i in range(256):
    e = i
    for _ in range(8):
        e = (e >> 1) ^ (0xD8018001 if e & 1 else 0)
    _EDC.append(e)


def edc(data: bytes) -> int:
    e = 0
    for b in data:
        e = (e >> 8) ^ _EDC[(e ^ b) & 0xFF]
    return e


# ---- ECC (Reed-Solomon over GF(2^8)) ----
_F = [0] * 256
_B = [0] * 256
for i in range(256):
    j = (i << 1) ^ (0x11D if i & 0x80 else 0)
    _F[i] = j & 0xFF
    _B[i ^ j] = i


def _ecc_part(sec: bytearray, major: int, minor: int, mmul: int, minc: int, out: int):
    size = major * minor
    for m in range(major):
        idx = (m >> 1) * mmul + (m & 1)
        a = b = 0
        for _ in range(minor):
            t = sec[0xC + idx]
            idx += minc
            if idx >= size:
                idx -= size
            a ^= t
            b ^= t
            a = _F[a]
        a = _B[_F[a] ^ b]
        sec[out + m] = a
        sec[out + m + major] = a ^ b


def fix_sector(sec: bytearray, lba: int | None = None) -> bytearray:
    """Recompute EDC/ECC for a Mode 2 sector in place (form from subheader)."""
    if lba is not None:
        lba += 150
        m, s, f = lba // 4500, (lba // 75) % 60, lba % 75
        bcd = lambda v: (v // 10) << 4 | v % 10
        sec[0:12] = SYNC
        sec[12:16] = bytes([bcd(m), bcd(s), bcd(f), 2])
    form2 = bool(sec[0x12] & 0x20)
    if form2:
        e = edc(sec[0x10:0x92C])
        struct.pack_into('<I', sec, 0x92C, e)
    else:
        struct.pack_into('<I', sec, 0x818, edc(sec[0x10:0x818]))
        hdr = bytes(sec[12:16])
        sec[12:16] = b'\0\0\0\0'          # header zeroed for Mode 2 ECC
        _ecc_part(sec, 86, 24, 2, 86, 0x81C)
        _ecc_part(sec, 52, 43, 86, 88, 0x8C8)
        sec[12:16] = hdr
    return sec


def user_data(sec: bytes) -> bytes:
    return sec[0x18:0x92C] if sec[0x12] & 0x20 else sec[0x18:0x818]


class Disc:
    """Random access to a raw .bin (or list of split parts) by LBA."""

    def __init__(self, paths):
        if isinstance(paths, str):
            paths = [paths]
        self.parts = []
        pos = 0
        for p in paths:
            f = open(p, 'rb')
            f.seek(0, 2)
            n = f.tell()
            self.parts.append((pos, n, f))
            pos += n
        self.size = pos
        self.sectors = pos // SECTOR

    def _read(self, off, n):
        out = bytearray()
        for start, ln, f in self.parts:
            if off < start + ln and off + n > start:
                a = max(off, start)
                b = min(off + n, start + ln)
                f.seek(a - start)
                out += f.read(b - a)
        return bytes(out)

    def sector(self, lba):
        return self._read(lba * SECTOR, SECTOR)

    def data(self, lba, count=1):
        return b''.join(user_data(self.sector(l)) for l in range(lba, lba + count))

    def file_bytes(self, lba, size):
        n = (size + 2047) // 2048
        return self.data(lba, n)[:size]


if __name__ == '__main__':
    # self-test: rebuilt EDC/ECC must match an existing sector byte for byte
    import sys
    d = Disc(sys.argv[1:])
    ok = bad = 0
    for lba in range(0, d.sectors, max(1, d.sectors // 500)):
        s = d.sector(lba)
        if len(s) < SECTOR or s[:12] != SYNC:
            continue
        t = fix_sector(bytearray(s))
        if bytes(t) == s:
            ok += 1
        elif s[0x12] & 0x20 and s[0x92C:0x930] == b'\0\0\0\0':
            ok += 1  # Form 2 with EDC left blank is legal
        else:
            bad += 1
    print('EDC/ECC self-test: match', ok, 'mismatch', bad)
