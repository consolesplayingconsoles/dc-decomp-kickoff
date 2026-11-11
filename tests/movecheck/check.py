#!/usr/bin/env python3
"""Which pieces move together, and where an address lands once they move apart (scripts/tools/1-2-baseline/movecheck.py groups()
and mapper()). No game data, no compiler. Stdlib only.

movecheck.py links the split with a pad between groups and runs it against the original. A group is what must not be separated:
pieces that share a pool, a bsr near its reach and its target, and data with both neighbours (Virtua Tennis's SDK start-up code,
unlisted, sat at the end of a data piece and loaded its pool from the next one: a pad between them made it load garbage).

    check.py      six pieces at 0C010000:
                    pool      f1 (+00) loads from a pool in f2 (+10): one group
                    branch    f3 (+20) bsr's to f4 (+30) nearby: a name, no tie: f4 starts a group
                    data      d5 (+40, not a listed function) is kept with f4 before it and f6 after it
                    reach     a bsr more than 3 KB from its target ties the two
                    bsr_ties  with bsr_ties=False (a running copy: a far bsr goes through a veneer) that bsr ties nothing, pools and
                              data still do; the default is the old behaviour
                    bsrf      a bsrf whose register is a pool distance ties its piece to the one it reaches (Crazy Taxi strcmp)
                    stay      with the game starting at +30, the pieces before it (boot code, entry stub) are one group with +00
                    flash     the BIOS stubs: the flash-ROM vector (B8) answers a failed read (r0 = -1), the others success (r0 = 0)
                    objects   a piece with no build/obj object (a function split after the last build.sh: Zombie Revenge
                              FUN_0c017ad0 and FUN_0c031014 stopped the build) or an older one is assembled by movecheck, not an
                              error; a piece with a current build/obj object links it; a piece symbolize.py changed is assembled
                    map       with a pad of 32 before each later group, an address in group n and an address value pointing there are
                              n * 32 higher; one in the first group, or past the fixed line, is not; BSS moves by all the pads
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SKILL = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(SKILL, 'scripts', 'tools', '1-2-baseline'))
sys.path.insert(0, os.path.join(SKILL, 'scripts', 'tools'))
B0 = 0x0C010000


def main():
    os.chdir(os.path.join(SKILL, 'tests', 'movecheck'))          # layout.py reads layout.txt from the working directory: none here
    import movecheck as M
    bad = []
    mem = {}
    mem[B0 + 0x00] = 0xD103                                       # f1: mov.l @(+0x0C+4 -> 0x10),r1: into f2
    mem[B0 + 0x20] = 0xB006                                       # f3: bsr +0x30 (f4)
    starts = [B0 + o for o in (0x00, 0x10, 0x20, 0x30, 0x40, 0x50)]
    listed = {B0, B0 + 0x10, B0 + 0x20, B0 + 0x30, B0 + 0x50}      # +40 is data
    code = [(B0 + o, 0x10) for o in (0x00, 0x10, 0x20, 0x30, 0x50)]
    end = B0 + 0x60
    g = M.groups(starts, listed, code, lambda a: mem.get(a, 0x0009), set(), end)
    if g != [0, 2, 3]:
        bad.append('groups: %r, want [0, 2, 3]: f1+f2 share a pool, f3 alone, f4+d5+f6 with the data' % g)
    # a far bsr: f1 to f6, 3.5 KB away
    far = {B0: 0xB000 | 0x6F0}                                    # bsr +4+2*0x6F0 = +0xDE4
    starts2 = [B0, B0 + 0x10, B0 + 0x800, B0 + 0xDE4]
    g2 = M.groups(starts2, set(starts2), [(s, 0x10) for s in starts2], lambda a: far.get(a, 0x0009), set(), B0 + 0xE00)
    if g2 != [0]:
        bad.append('reach: %r, want [0]: a bsr 3.5 KB from its target ties everything between' % g2)
    g2b = M.groups(starts2, set(starts2), [(s, 0x10) for s in starts2], lambda a: far.get(a, 0x0009), set(), B0 + 0xE00, bsr_ties=False)
    if g2b != [0, 1, 2, 3]:
        bad.append('bsr_ties: %r, want [0, 1, 2, 3]: a running copy sends a far bsr through a veneer, so it does not tie' % g2b)
    gp = M.groups(starts, listed, code, lambda a: mem.get(a, 0x0009), set(), end, bsr_ties=False)
    if gp != g:
        bad.append('bsr_ties: pools and data still tie without bsr ties: %r, want %r' % (gp, g))
    g3 = M.groups(starts, listed, code, lambda a: mem.get(a, 0x0009), set(), end, stay=B0 + 0x30)
    if g3 != [0, 3]:
        bad.append('stay: %r, want [0, 3]: pieces before layout.txt\'s game start stay with the first one' % g3)
    dm = {B0: 0xD301, B0 + 2: 0x0303}                                  # mov.l @(1,pc),r3 / bsrf r3: the pool word at +08 holds 0x2A
    st4 = [B0, B0 + 0x10, B0 + 0x20, B0 + 0x30]
    args = (st4, set(st4), [(s_, 0x10) for s_ in st4], lambda a: dm.get(a, 0x0009), {B0 + 8}, B0 + 0x40)
    g4 = M.groups(*args, pool32=lambda a: 0x2A if a == B0 + 8 else 0)
    if g4 != [0]:
        bad.append('bsrf: a distance branch from +00 to +30 (pool word 0x2A) must tie the pieces: %r, want [0]' % g4)
    g5 = M.groups(*args)
    if g5 != [0, 1, 2, 3]:
        bad.append('bsrf: without a pool reader nothing is tied (the control): %r' % g5)
    new = M.mapper([B0, B0 + 0x20, B0 + 0x30], 32, end, B0, 0x0C500000)
    for v, want in ((0x0C010004, 0x0C010004), (0x8C010024, 0x8C010044), (0x0C010034, 0x0C010074), (0x0C100000, 0x0C100040),
                    (0x0C600000, 0x0C600000), (0x12345678, 0x12345678)):
        if new(v) != want:
            bad.append('map: %08X -> %08X, want %08X' % (v, new(v), want))
    import struct
    pk = M.bios_pokes()
    stub = lambda v: bytes.fromhex(pk['%08X' % (struct.unpack('<I', bytes.fromhex(pk[v]))[0])])
    if stub('8C0000B8') != bytes.fromhex('0b00ffe0') or stub('8C0000B0') != bytes.fromhex('0b0000e0'):
        bad.append('flash: the flash-ROM vector does not answer a failed read, or another vector not success')
    import tempfile
    import shutil
    import time
    tmp = tempfile.mkdtemp()
    here = os.getcwd()
    try:
        os.chdir(tmp)
        for p in ('asm', 'build/obj', 'build/sym/asm', 'build/sym/obj'):
            os.makedirs(p)
        src = {'a.src': 'same\n', 'b.src': 'same\n', 'c.src': 'same\n', 'd.src': 'orig\n'}
        for f, t in src.items():
            open(os.path.join('asm', f), 'w').write(t)
            open(os.path.join('build/sym/asm', f), 'w').write(t if f != 'd.src' else 'named\n')
        open('build/obj/a.obj', 'w').write('x')                              # a: assembled by build.sh, current
        open('build/obj/c.obj', 'w').write('x')                              # c: older than its source
        old = time.time() - 100
        os.utime('build/obj/c.obj', (old, old))
        changed, stale, missing = M.to_assemble('build/sym', ['a.src', 'b.src', 'c.src', 'd.src'])
        if sorted(missing) != ['b.src', 'c.src'] or sorted(changed) != ['b.src', 'c.src', 'd.src'] or sorted(stale) != ['b.src', 'c.src', 'd.src']:
            bad.append('objects: changed %r stale %r missing %r, want b and c (no object, an older one) assembled here with d, a linked'
                       % (changed, stale, missing))
    finally:
        os.chdir(here)
        shutil.rmtree(tmp, ignore_errors=True)
    if bad:
        sys.exit('[ERROR] movecheck check failed:\n' + '\n'.join(bad))
    print('[movecheck] ok: shared pools, far branches and data keep pieces together; addresses map to their group\'s new place')


if __name__ == '__main__':
    main()
