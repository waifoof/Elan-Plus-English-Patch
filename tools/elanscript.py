"""Élan Plus script bytecode parser (OUTPUT.BIN script entries).

Interpreter: SLPS_027.59 @ 0x8001754C, opcode table @ 0x80010304 (ops 0x01-0x38).
Text op 0x16: 16 <2-byte SJIS chars ...> (81 84 | 81 90) <1 byte>
Jumps (relative, signed 16-bit little-endian):
  0x1F  goto        target = op_addr + 3 + off
  0x38  if-eq goto  target = op_addr + off   (len 4)
  0x25/0x26  conditional goto (0x25: player is female)  target = op_addr + 5 + s16 at +3  (len 5)
"""
import struct

TEXT_END = (0x8184, 0x8190)

# fixed opcode lengths (bytes including the opcode); None = special/unknown
LEN = {
    0x01: 3, 0x02: 3, 0x03: 3, 0x04: 3, 0x05: 3, 0x06: 3,
    0x07: 2, 0x08: 2, 0x09: 2, 0x0A: 2, 0x0B: 2, 0x0C: 2,
    0x0D: 1, 0x0E: 1, 0x0F: 1, 0x10: 1, 0x11: 1, 0x12: 1,
    0x13: 3, 0x14: 3, 0x15: 2, 0x17: 1, 0x18: 2, 0x19: 2,
    0x1A: 2, 0x1B: 1, 0x1C: 1, 0x1D: 1, 0x1E: 1, 0x1F: 3,
    0x20: 1, 0x21: 2, 0x22: 2, 0x23: 3, 0x24: 3, 0x25: 5,
    0x26: 5, 0x27: 2, 0x28: 2, 0x29: 2, 0x2A: 2, 0x2B: 2,
    0x2C: 2, 0x2D: 2, 0x2E: 4, 0x2F: 3, 0x30: 1, 0x31: 2,
    0x32: 2, 0x33: 1, 0x34: 1, 0x35: 1, 0x36: 1, 0x37: 2,
    0x38: 4,
}


class ParseError(Exception):
    pass


def parse(data, lens=LEN, stop_at_padding=True):
    """Return list of ops: (offset, opcode, raw_bytes, info)."""
    ops = []
    i = 0
    n = len(data)
    while i < n:
        op = data[i]
        if op == 0 and stop_at_padding and not any(data[i:i + 16]):
            break
        if op == 0x16:
            j = i + 1
            while True:
                if j + 1 >= n:
                    raise ParseError(f'unterminated text at 0x{i:X}')
                c = data[j] << 8 | data[j + 1]
                j += 2
                if c in TEXT_END:
                    j += 1
                    break
            ops.append((i, op, data[i:j], {'text': data[i + 1:j - 3], 'end': data[j - 3:j]}))
            i = j
            continue
        if op == 0x20:
            # two-option choice menu: 20 { u16 off, SJIS text, 00 } x2
            # target = (address right after the u16) + off
            j = i + 1
            opts = []
            for _ in range(2):
                if j + 2 > n:
                    raise ParseError(f'truncated menu at 0x{i:X}')
                off, = struct.unpack_from('<h', data, j)
                t0 = j + 2
                k = data.index(0, t0)
                opts.append({'target': t0 + off, 'text': data[t0:k], 'field': j})
                j = k + 1
            ops.append((i, op, data[i:j], {'options': opts}))
            i = j
            continue
        ln = lens.get(op)
        if ln is None:
            raise ParseError(f'unknown opcode 0x{op:02X} at 0x{i:X}')
        if i + ln > n:
            raise ParseError(f'op 0x{op:02X} runs past end at 0x{i:X}')
        info = {}
        if op == 0x1F:
            off, = struct.unpack_from('<h', data, i + 1)
            info['target'] = i + 3 + off
        elif op == 0x38:
            off, = struct.unpack_from('<h', data, i + 2)
            info['target'] = i + off
        elif op in (0x25, 0x26):            # conditional jumps (0x25 = player is female): target = op + 5 + s16@3
            off, = struct.unpack_from('<h', data, i + 3)
            info['target'] = i + 5 + off
        ops.append((i, op, data[i:i + ln], info))
        i += ln
    return ops


def validate(data, lens=LEN):
    ops = parse(data, lens)
    starts = {o[0] for o in ops}
    bad = [o for o in ops if 'target' in o[3] and o[3]['target'] not in starts]
    bad += [o for o in ops if 'options' in o[3]
            and any(x['target'] not in starts for x in o[3]['options'])]
    end = ops[-1][0] + len(ops[-1][2]) if ops else 0
    return ops, bad, end
