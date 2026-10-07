#!/usr/bin/env python3
"""Function starts the analysis never reached, as seeds for ghidra/SeedFuncs.java. Stdlib only.

    seed_funcs.py <executable> <base hex> <report.txt> > seeds.txt

Looks only in stretches no analysed function covers (missed_funcs.py covers the small gaps after
functions). A seed is an address right after something that ends a function (rts + its delay slot,
or nop / 0xEEEE padding) whose first instruction starts a function: saving pr or r8-r14, or making
stack room. Prints one hex address per line, with the region and the reason as a comment.
"""
import struct
import sys

if len(sys.argv) != 4:
    sys.exit(__doc__)
exe = open(sys.argv[1], 'rb').read()
base = int(sys.argv[2], 16)
funcs = sorted((int(l.split()[1], 16), int(l.split()[2])) for l in open(sys.argv[3]) if l.startswith('F '))
covered = bytearray(len(exe))
for a, s in funcs:
    covered[max(0, a - base):max(0, a - base + s)] = b'\1' * max(0, min(s, len(exe) - (a - base)))


def hw(o):
    return struct.unpack_from('<H', exe, o)[0]


PUSH = {0x4f22} | {0x2f06 | (r << 4) for r in range(8, 15)}
n = 0
for o in range(4, len(exe) - 2, 2):
    if covered[o]:
        continue
    w = hw(o)
    starts = w in PUSH or (w >> 8 == 0x7f and w & 0x80)
    after_end = hw(o - 4) == 0x000b or hw(o - 2) in (0x0009, 0xeeee)
    if starts and after_end and not (w in PUSH and hw(o - 2) in PUSH):
        print('%08x  # %s' % (base + o, 'after rts' if hw(o - 4) == 0x000b else 'after padding'))
        n += 1
print('%d seeds' % n, file=sys.stderr)
