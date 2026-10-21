"""Files whose messages are reached through a pointer table (mail 834-843, conversations 930-977).

Layout (loaded at 0x80160000): u32 header, then messages, each NUL-terminated and
padded with zeros so the next one starts on a 4-byte boundary, then a table of
u32 RAM pointers to message starts. GAME.BIN holds the RAM address of every
table (lists at 0x39C5C for 930-977 and 0x326EC/0x32714 for 834-843), so after
the text changes length the table moves and those addresses are rewritten.
"""
import re, struct

BASE = 0x80160000
MOVES = {}          # entry -> (old_table_off, new_table_off), filled by rebuild()


def table_start(o):
    n = len(o) // 4 * 4
    t = n
    while t - 4 >= 4:
        w, = struct.unpack_from('<I', o, t - 4)
        if w == 0 or BASE <= w < BASE + len(o):
            t -= 4
        else:
            break
    end = 4 + len(o[4:t].rstrip(b'\0'))
    return (end + 1 + 3) & ~3


def messages(region, start):
    """[(offset, bytes)] for NUL-separated messages in region (region begins at file offset start)."""
    out = []
    for m in re.finditer(rb'[^\x00]+', region):
        out.append((start + m.start(), m.group()))
    return out


def rebuild(entry, orig, header, new_text_body):
    o = orig.rstrip(b'\0')
    t_old = table_start(o)
    old = messages(o[4:t_old], 4)
    new = messages(new_text_body, 4)
    if len(old) != len(new):
        raise ValueError(f'{entry}: {len(old)} messages in the original, {len(new)} in the rebuild')
    out = bytearray(struct.pack('<I', header))
    remap = {}
    for (ooff, _), (_, data) in zip(old, new):
        remap[ooff] = len(out)
        out += data + b'\0'
        out += b'\0' * (-len(out) % 4)
    if len(out) <= t_old:
        out += b'\0' * (t_old - len(out))     # keep the table where the game expects it
    t_new = len(out)
    table = o[t_old:]
    for i in range(0, len(table) - 3, 4):
        w, = struct.unpack_from('<I', table, i)
        if w:
            off = w - BASE
            if off not in remap:
                raise ValueError(f'{entry}: table entry {hex(w)} is not a message start')
            w = BASE + remap[off]
        out += struct.pack('<I', w)
    out += table[len(table) // 4 * 4:]
    if t_new != t_old:
        MOVES[entry] = (t_old, t_new)
    return bytes(out)


# where GAME.BIN keeps the table addresses
MK_LIST = (0x39C5C, 48)
REC_LIST = (0x326EC, 10)
REC_LIST2 = (0x32714, 8)      # second halves; same order as the first 8 of REC_LIST


def patch_game_bin(game, orig_tables):
    """orig_tables: entry -> original table offset. Rewrites the address lists in GAME.BIN."""
    g = bytearray(game)
    by_addr = {BASE + t: k for k, t in orig_tables.items()}
    n = 0
    owners = []
    for start, count in (MK_LIST, REC_LIST):
        for i in range(count):
            o = start + i * 4
            a, = struct.unpack_from('<I', g, o)
            k = by_addr.get(a)
            owners.append(k)
            if k in MOVES:
                struct.pack_into('<I', g, o, BASE + MOVES[k][1])
                n += 1
    rec_owners = owners[MK_LIST[1]:]
    for i in range(REC_LIST2[1]):
        o = REC_LIST2[0] + i * 4
        a, = struct.unpack_from('<I', g, o)
        k = rec_owners[i]
        if k in MOVES:
            t_old, t_new = MOVES[k]
            struct.pack_into('<I', g, o, BASE + t_new + (a - BASE - t_old))
            n += 1
    return bytes(g), n


def verify(game, entries):
    """Check every GAME.BIN table address against the rebuilt files. Returns a list of problems."""
    probs = []
    lists = [(MK_LIST, list(range(930, 978))), (REC_LIST, None)]
    words = []
    for (start, count), _ in lists:
        words += [struct.unpack_from('<I', game, start + i * 4)[0] for i in range(count)]
    words += [struct.unpack_from('<I', game, REC_LIST2[0] + i * 4)[0] for i in range(REC_LIST2[1])]
    for k in list(range(834, 844)) + list(range(930, 978)):
        o = entries[k].rstrip(b'\0')
        starts = {m.start() + 4 for m in re.finditer(rb'(?:(?<=\x00)|^)[^\x00]', o[4:])}
        t = table_start(o)
        here = [w for w in words if BASE + t <= w < BASE + len(o) + 4]
        if not here and k != 842:
            probs.append(f'{k}: no GAME.BIN address points at its table')
        for w in here:
            off = w - BASE
            for i in range(off, len(o) - 3, 4):
                p, = struct.unpack_from('<I', o, i)
                if p and (p - BASE) not in starts:
                    probs.append(f'{k}: table word at {i} -> {hex(p)} is not a message start')
                    break
    return probs
