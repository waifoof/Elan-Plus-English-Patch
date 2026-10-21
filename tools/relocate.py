"""Replace one file inside a raw Mode 2 .bin without moving any other file.

If the new data fits the file's original sector allocation it is written in
place; otherwise it is appended after the last data sector (the trailing
150-sector postgap is re-added after it), and the file's ISO9660 directory
record (extent + size) and the PVD volume size are patched. Every rewritten
sector gets fresh EDC/ECC.
"""
import struct, sys, os
sys.path.insert(0, os.path.dirname(__file__))
from cdsector import SECTOR, fix_sector, user_data

POSTGAP = 150


def _both32(v):
    return struct.pack('<I', v) + struct.pack('>I', v)


def find_record(img, path):
    """Return (dir_lba, byte_offset_in_dir, extent, size) for e.g. 'GAME/OUTPUT.BIN'."""
    def sec(l):
        return user_data(img[l * SECTOR:(l + 1) * SECTOR])
    pvd = sec(16)
    root = pvd[156:190]
    lba, size = struct.unpack_from('<I', root, 2)[0], struct.unpack_from('<I', root, 10)[0]
    parts = path.upper().split('/')
    for depth, name in enumerate(parts):
        want = name.encode() + (b';1' if depth == len(parts) - 1 else b'')
        data = b''.join(sec(l) for l in range(lba, lba + (size + 2047) // 2048))
        i = 0
        hit = None
        while i < len(data):
            n = data[i]
            if n == 0:
                i = (i // 2048 + 1) * 2048
                continue
            r = data[i:i + n]
            if r[33:33 + r[32]] == want:
                hit = (lba, i, struct.unpack_from('<I', r, 2)[0], struct.unpack_from('<I', r, 10)[0])
                break
            i += n
        if not hit:
            raise KeyError(path)
        if depth < len(parts) - 1:
            lba, size = hit[2], hit[3]
    return hit


def write_file_sectors(buf, lba, data, sub_mid, sub_last):
    n = (len(data) + 2047) // 2048
    for k in range(n):
        s = bytearray(SECTOR)
        sub = sub_last if k == n - 1 else sub_mid
        s[0x10:0x14] = sub
        s[0x14:0x18] = sub
        chunk = data[k * 2048:(k + 1) * 2048]
        s[0x18:0x18 + len(chunk)] = chunk
        fix_sector(s, lba + k)
        o = (lba + k) * SECTOR
        if o >= len(buf):
            buf.extend(s)
        else:
            buf[o:o + SECTOR] = s


def patch_sector(buf, lba, off_in_data, new_bytes):
    o = lba * SECTOR
    s = bytearray(buf[o:o + SECTOR])
    s[0x18 + off_in_data:0x18 + off_in_data + len(new_bytes)] = new_bytes
    fix_sector(s)
    buf[o:o + SECTOR] = s


def replace_file(img_path, path, new_data, out_path):
    buf = bytearray(open(img_path, 'rb').read())
    dir_lba, rec_off, extent, size = find_record(buf, path)
    old_secs = (size + 2047) // 2048
    new_secs = (len(new_data) + 2047) // 2048
    first = buf[extent * SECTOR:(extent + 1) * SECTOR]
    last = buf[(extent + old_secs - 1) * SECTOR:(extent + old_secs) * SECTOR]
    sub_mid, sub_last = bytes(first[0x10:0x14]), bytes(last[0x10:0x14])
    if new_secs <= old_secs:
        target = extent
        # zero the rest of the old allocation so nothing stale is left
        write_file_sectors(buf, extent, new_data + b'\0' * ((old_secs - new_secs) * 2048), sub_mid, sub_mid)
        # put the EOF flag on the real last sector of the file
        o = (extent + new_secs - 1) * SECTOR
        s = bytearray(buf[o:o + SECTOR]); s[0x10:0x14] = sub_last; s[0x14:0x18] = sub_last
        fix_sector(s); buf[o:o + SECTOR] = s
        moved = False
    else:
        total = len(buf) // SECTOR
        tail = bytes(buf[(total - POSTGAP) * SECTOR:])          # keep postgap pattern
        del buf[(total - POSTGAP) * SECTOR:]
        target = total - POSTGAP
        write_file_sectors(buf, target, new_data, sub_mid, sub_last)
        end = len(buf) // SECTOR
        for k in range(POSTGAP):                                 # re-add postgap after the new data
            s = bytearray(tail[k * SECTOR:(k + 1) * SECTOR])
            fix_sector(s, end + k)
            buf.extend(s)
        total = len(buf) // SECTOR
        pvd_size = _both32(total)
        patch_sector(buf, 16, 80, pvd_size)
        moved = True
    # directory record: extent (offset 2) and data length (offset 10), both-endian
    sec_in_dir, off = divmod(rec_off, 2048)
    patch_sector(buf, dir_lba + sec_in_dir, off + 2, _both32(target))
    patch_sector(buf, dir_lba + sec_in_dir, off + 10, _both32(len(new_data)))
    open(out_path, 'wb').write(buf)
    return {'moved': moved, 'lba': target, 'sectors': new_secs, 'old_sectors': old_secs}
