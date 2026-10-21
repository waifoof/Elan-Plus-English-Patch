"""Minimal MIPS R3000A (PS1) disassembler, plus PS-X EXE loader.

Usage: python3 mipsdis.py SLPS_027.59 [start_addr] [count]
Also importable: dis(word, pc) -> str, load_psexe(path) -> (base, entry, bytes)
"""
import struct, sys

R = ['zero','at','v0','v1','a0','a1','a2','a3','t0','t1','t2','t3','t4','t5','t6','t7',
     's0','s1','s2','s3','s4','s5','s6','s7','t8','t9','k0','k1','gp','sp','fp','ra']


def _s16(v):
    return v - 0x10000 if v & 0x8000 else v


def dis(w, pc=0):
    op = w >> 26
    rs, rt, rd = (w >> 21) & 31, (w >> 16) & 31, (w >> 11) & 31
    sh, fn = (w >> 6) & 31, w & 63
    imm = w & 0xFFFF
    si = _s16(imm)
    tgt = ((pc + 4) & 0xF0000000) | ((w & 0x3FFFFFF) << 2)
    br = (pc + 4 + (si << 2)) & 0xFFFFFFFF
    if w == 0:
        return 'nop'
    if op == 0:
        n = {0:'sll',2:'srl',3:'sra'}.get(fn)
        if n: return f'{n} ${R[rd]}, ${R[rt]}, {sh}'
        n = {4:'sllv',6:'srlv',7:'srav'}.get(fn)
        if n: return f'{n} ${R[rd]}, ${R[rt]}, ${R[rs]}'
        if fn == 8: return f'jr ${R[rs]}'
        if fn == 9: return f'jalr ${R[rd]}, ${R[rs]}'
        if fn == 12: return 'syscall'
        if fn == 13: return 'break'
        n = {16:'mfhi',18:'mflo'}.get(fn)
        if n: return f'{n} ${R[rd]}'
        n = {17:'mthi',19:'mtlo'}.get(fn)
        if n: return f'{n} ${R[rs]}'
        n = {24:'mult',25:'multu',26:'div',27:'divu'}.get(fn)
        if n: return f'{n} ${R[rs]}, ${R[rt]}'
        n = {32:'add',33:'addu',34:'sub',35:'subu',36:'and',37:'or',38:'xor',39:'nor',
             42:'slt',43:'sltu'}.get(fn)
        if n: return f'{n} ${R[rd]}, ${R[rs]}, ${R[rt]}'
    elif op == 1:
        n = {0:'bltz',1:'bgez',16:'bltzal',17:'bgezal'}.get(rt)
        if n: return f'{n} ${R[rs]}, 0x{br:08X}'
    elif op == 2: return f'j 0x{tgt:08X}'
    elif op == 3: return f'jal 0x{tgt:08X}'
    elif op in (4, 5):
        return f"{'beq' if op==4 else 'bne'} ${R[rs]}, ${R[rt]}, 0x{br:08X}"
    elif op in (6, 7):
        return f"{'blez' if op==6 else 'bgtz'} ${R[rs]}, 0x{br:08X}"
    elif op in (8, 9, 10, 11):
        n = ['addi','addiu','slti','sltiu'][op-8]
        return f'{n} ${R[rt]}, ${R[rs]}, {si}'
    elif op in (12, 13, 14):
        n = ['andi','ori','xori'][op-12]
        return f'{n} ${R[rt]}, ${R[rs]}, 0x{imm:X}'
    elif op == 15: return f'lui ${R[rt]}, 0x{imm:X}'
    elif op in (16, 18):
        c = op - 16
        if rs == 0: return f'mfc{c} ${R[rt]}, ${rd}'
        if rs == 2: return f'cfc{c} ${R[rt]}, ${rd}'
        if rs == 4: return f'mtc{c} ${R[rt]}, ${rd}'
        if rs == 6: return f'ctc{c} ${R[rt]}, ${rd}'
        if c == 0 and fn == 16: return 'rfe'
        if c == 2 and rs & 16: return f'cop2 0x{w & 0x1FFFFFF:X}'
    else:
        n = {32:'lb',33:'lh',34:'lwl',35:'lw',36:'lbu',37:'lhu',38:'lwr',
             40:'sb',41:'sh',42:'swl',43:'sw',46:'swr',50:'lwc2',58:'swc2'}.get(op)
        if n:
            reg = f'${rt}' if op in (50, 58) else f'${R[rt]}'
            return f'{n} {reg}, {si}(${R[rs]})'
    return f'.word 0x{w:08X}'


def load_psexe(path):
    d = open(path, 'rb').read()
    if d[:8] != b'PS-X EXE':
        raise ValueError('not a PS-X EXE')
    entry, = struct.unpack_from('<I', d, 0x10)
    base, size = struct.unpack_from('<II', d, 0x18)
    return base, entry, d[0x800:0x800 + size]


if __name__ == '__main__':
    base, entry, code = load_psexe(sys.argv[1])
    start = int(sys.argv[2], 16) if len(sys.argv) > 2 else entry
    count = int(sys.argv[3]) if len(sys.argv) > 3 else 64
    print(f'; base 0x{base:08X} entry 0x{entry:08X} size 0x{len(code):X}')
    for i in range(count):
        pc = start + i * 4
        o = pc - base
        if not 0 <= o < len(code) - 3:
            break
        w, = struct.unpack_from('<I', code, o)
        print(f'{pc:08X}: {w:08X}  {dis(w, pc)}')
