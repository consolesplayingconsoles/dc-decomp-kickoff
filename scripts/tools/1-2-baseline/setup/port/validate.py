#!/usr/bin/env python3
"""Check function pairs against the port's signatures; write accepted.tsv. Stdlib only.

    validate.py [pairs.tsv]  ->  accepted.tsv

SH-4 passes the first four integer/pointer arguments in r4-r7. A Dreamcast function that reads
more of r4-r7 (before writing them, up to its first call or return) than the port's signature has
integer/pointer parameters is not that function: the pair is rejected. Reading fewer proves
nothing (arguments are often read after a call), so it is not a rejection. Only the port's original
game functions (not its own C++ classes) and plain C identifiers are accepted.

It also lists signature names that may have landed on game code: short functions (48 bytes or
less) named by an sdk.txt "func" line with no name of the same family (first two letters) within
8 functions either side (library functions are linked in families). A short game function can
hash like an unrelated library one, and such a name, used as a seed, pairs its whole neighbourhood wrong. Listed for review, never dropped: check each
against how its result is used (a value stored as an angle is not a sine).
"""
import os, re, struct, sys
from portcfg import DECOMP, SIGNATURE, ORIGINAL_NAMES

exe = open(os.path.join(DECOMP, '1ST_READ.BIN'), 'rb').read()
base = int(open(os.path.join(DECOMP, 'BASE')).read().strip(), 16)
size = {l.split()[1]: int(l.split()[2]) for l in open(os.path.join(DECOMP, 'functions.txt'))}

def int_params(sig):
    m = re.search(r'\((.*)\)', sig or '')
    if not m:
        return None
    ps = [p.strip() for p in m.group(1).split(',') if p.strip() and p.strip() != 'void']
    return min(4, sum(1 for p in ps if p not in ('float', 'double')))

def regs(w):
    """(read, written) general registers of one SH-4 instruction; None = stop (branch/return)."""
    t, n, m, lo = w >> 12, (w >> 8) & 15, (w >> 4) & 15, w & 15
    if w == 0x000b or w == 0x002b or t in (0xa, 0xb) or (t == 4 and (w & 0xff) in (0x0b, 0x2b)) \
            or (t == 0 and lo == 3 and m in (0, 2)):
        return None                                           # rts, rte, bra, bsr, jsr, jmp, bsrf, braf
    if t == 0x6:                                              # mov / loads / extends: m -> n
        return {m}, {n} | ({m} if lo in (4, 5, 6) else set())
    if t == 0x2:                                              # stores, and/or/xor/tst/cmp/mul
        return {m, n}, ({n} if lo in (4, 5, 6, 9, 10, 11) else set())
    if t == 0x3:                                              # cmp, add, sub, ...
        return {m, n}, ({n} if lo in (8, 10, 11, 12, 14, 15) else set())
    if t == 0x1:                                              # mov.l Rm,@(disp,Rn)
        return {m, n}, set()
    if t == 0x5:                                              # mov.l @(disp,Rm),Rn
        return {m}, {n}
    if t == 0x7:                                              # add #imm,Rn
        return {n}, {n}
    if t in (0xe, 0xd, 0x9):                                  # mov #imm / pc-relative loads
        return set(), {n}
    if t == 0x4:
        if (w & 0xff) in (0x22, 0x02, 0x12, 0x52, 0x62, 0x06, 0x16, 0x26, 0x56, 0x66):
            return {n}, {n}                                   # sts.l/stc.l x,@-Rn ; lds.l @Rn+,x
        return {n}, {n}                                       # shifts, cmp/pl, lds, ...
    if t == 0x0:
        if lo in (2, 0xa) or (w & 0xff) in (0x29, 0x1a, 0x0a, 0x5a, 0x6a):
            return set(), {n}                                 # stc/sts/movt Rn
        if lo in (4, 5, 6, 7, 0xc, 0xd, 0xe, 0xf):
            return {m, n, 0}, ({n} if lo >= 0xc else set())
        return set(), set()
    if t == 0x8:
        return ({m} if n in (4, 5) else {0, m} if n in (0, 1) else {0}), ({0} if n in (4, 5) else set())
    if t == 0xc:
        return {0}, {0}
    if t == 0xf:                                              # FPU: only the address registers
        if lo in (6, 8, 9):
            return {m} | ({0} if lo == 6 else set()), ({m} if lo == 9 else set())
        if lo in (7, 0xa, 0xb):
            return {n} | ({0} if lo == 7 else set()), ({n} if lo == 0xb else set())
        return set(), set()
    return set(), set()

def dc_params(addr):
    used, written = set(), set()
    x = int(addr, 16)
    for p in range(x, x + min(size.get(addr, 64), 160), 2):
        r = regs(struct.unpack_from('<H', exe, p - base)[0])
        if r is None:
            break
        for g in r[0]:
            if 4 <= g <= 7 and g not in written: used.add(g)
        written |= r[1]
    return len(used)

ok = bad = unk = 0
over = set()
lines = open(sys.argv[1] if len(sys.argv) > 1 else 'pairs.tsv').read().splitlines()
for l in lines:
    d, dname, sname, how = l.split('\t')
    n = int_params(SIGNATURE.get(sname))
    if n is None:
        unk += 1; continue
    k = dc_params(d)
    ok += k == n; bad += k != n
    if k > n: over.add(d)
with open('accepted.tsv', 'w') as o:
    for l in lines:
        d, dname, sname, how = l.split('\t')
        if d not in over and sname in ORIGINAL_NAMES and re.fullmatch(r'[A-Za-z_]\w*', sname):
            o.write(l + '\n')
print('parameter count agrees %d, differs %d, no signature %d; rejected (reads more than the '
      'signature): %d; accepted: %d' % (ok, bad, unk, len(over), sum(1 for _ in open('accepted.tsv'))))

sdk_txt = os.path.join(DECOMP, 'sdk.txt')
if os.path.exists(sdk_txt):
    ranges, sig = [], set()
    for l in open(sdk_txt):
        p = l.split()
        if p and p[0] == 'range':
            ranges.append((int(p[1], 16), int(p[2], 16)))
        elif p and p[0] == 'func':
            sig.add(int(p[1], 16))
    order = sorted((int(l.split()[1], 16), l.split()[3], int(l.split()[2])) for l in
                   open(os.path.join(DECOMP, 'functions.txt')) if l.startswith('F '))
    def fam(n):
        n = n.lstrip('_').lower()
        return n[:2]
    # Library functions come in families linked together (ADXSTM_* beside ADXSTM_*). A short
    # signature name with no same-prefix name within 8 functions either side is suspect: a hash
    # collision needs a short function.
    odd = []
    for i, (a, n, z) in enumerate(order):
        if a not in sig or z > 48 or n.startswith('FUN_'):
            continue
        near = order[max(0, i - 8):i] + order[i + 1:i + 9]
        if not any(fam(m) == fam(n) for _, m, _ in near if not m.startswith('FUN_')):
            odd.append((a, n))
    if odd:
        print('short signature names with no same-prefix name nearby, check before trusting them as '
              'seeds (%d):' % len(odd))
        for a, n in odd:
            print('  %08x %s' % (a, n))
