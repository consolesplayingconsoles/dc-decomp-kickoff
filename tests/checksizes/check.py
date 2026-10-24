#!/usr/bin/env python3
"""checksizes.py --extend --write fixes a size that ends where a literal pool sits mid-body (scripts/tools/1-2-baseline/checksizes.py).
Ghidra ends a function at a pool in the middle of its body, so functions.txt lists it shorter than its code: the simulator never
sees it return and every drawn case runs to the step cap (Virtua Tennis: 49 of 117 generator timeouts, cpuPointBehind listed at
198 bytes for 222). No game data, no compiler. Stdlib only.

    check.py      a temp repo with three functions:
                    pool       f1: a pool in the middle, the code after it reached by a bra; listed up to the pool: extended to
                               the end of its rts and delay slot (18 bytes)
                    next       f3: a bra into the next entry (a tail into another function): not extended
                    own        f2: already right: unchanged
"""
import os
import shutil
import struct
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
SKILL = os.path.dirname(os.path.dirname(HERE))
BASE = 0x8C010000
W = lambda *h: struct.pack('<%dH' % len(h), *h)

CODE = (W(0x4F22, 0xD101, 0xA002, 0x0009) + struct.pack('<I', 0x12345678) +   # f1: sts.l pr / mov.l @(pool),r1 / bra +2 / nop / pool
        W(0x4F26, 0x000B, 0x0009, 0x0009) +                                    # 12: lds.l @r15+,pr / rts / nop (end 18) / pad
        W(0x000B, 0x0009) +                                                    # 20: f2: rts / nop
        W(0xA003, 0x0009, 0x0009, 0x0009) +                                    # 24: f3: bra 36 (into f4) / nop / pad
        W(0x0009, 0x0009, 0x000B, 0x0009))                                     # 32: f4: nop / nop / rts / nop
FUNCS = 'F 8c010000 8 f1\nF 8c010014 4 f2\nF 8c010018 4 f3\nF 8c010020 8 f4\n'


def main():
    bad = []
    tmp = tempfile.mkdtemp()
    try:
        shutil.copytree(os.path.join(SKILL, 'scripts', 'tools'), os.path.join(tmp, 'tools'), ignore=shutil.ignore_patterns('__pycache__'))
        open(os.path.join(tmp, '1ST_READ.BIN'), 'wb').write(CODE)
        open(os.path.join(tmp, 'BASE'), 'w').write('%08X\n' % BASE)
        open(os.path.join(tmp, 'functions.txt'), 'w').write(FUNCS)
        r = subprocess.run([sys.executable, 'tools/1-2-baseline/checksizes.py', '--extend', '--write'], cwd=tmp,
                           capture_output=True, text=True)
        sizes = {l.split()[3]: int(l.split()[2]) for l in open(os.path.join(tmp, 'functions.txt')) if l.startswith('F ')}
        if sizes.get('f1') != 18:
            bad.append('pool: f1 is %r bytes, want 18 (%s)' % (sizes.get('f1'), (r.stdout + r.stderr).strip()[-200:]))
        if sizes.get('f3') != 4:
            bad.append('next: f3 is %r bytes, want 4 (a branch into f4 is a tail, not its own code)' % sizes.get('f3'))
        if sizes.get('f2') != 4:
            bad.append('own: f2 is %r bytes, want 4' % sizes.get('f2'))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    for b in bad:
        print('FAIL', b)
    print('checksizes: %s' % ('OK' if not bad else '%d failures' % len(bad)))
    sys.exit(1 if bad else 0)


if __name__ == '__main__':
    main()
