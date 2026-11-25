#!/usr/bin/env python3
"""A register combined with itself is read by the generator as a value of its own (scripts/tools/5-generated/gen_equiv/gen_core.py).
No game data, no compiler. Stdlib only.

`xor rN,rN` and `sub rN,rN` give 0, and `subc rN,rN` gives -T, whatever rN held: SHC turns a comparison into a value with
`subc r0,r0; add #1,r0` (1 - T). The generator read the register first and stopped, "read r0", on every function that ends that way
(six of one game's functions: a point-in-box test, float compares). The arity scan already knew (tests/test_arity zero).

    check.py      a temp repo, each function written by gen_drv.build:
                    subc   `cmp/gt r4,r5; subc r0,r0; rts; add #1,r0`: written, its value 1 - (r5 > r4), no "read r0"
                    xor    `xor r0,r0; rts; add #5,r0`: written, returns 5
                    sub    `sub r3,r3; mov r3,r0; rts; nop`: written, returns 0
"""
import unittest
import os
import shutil
import struct
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
SKILL = os.path.dirname(HERE)
BASE = 0x0C010000
FUNCS = {'fsubc': [0x3547, 0x300A, 0x000B, 0x7001],      # cmp/gt r4,r5; subc r0,r0; rts; add #1,r0
         'fxor': [0x200A, 0x000B, 0x7005, 0x0009],       # xor r0,r0; rts; add #5,r0
         'fsub': [0x3338, 0x6033, 0x000B, 0x0009]}       # sub r3,r3; mov r3,r0; rts; nop


class TestGenSelfClear(unittest.TestCase):
    def test_gen_selfclear(self):
        tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, tmp, True)
        shutil.copytree(os.path.join(SKILL, 'scripts', 'tools'), os.path.join(tmp, 'tools'), ignore=shutil.ignore_patterns('__pycache__'))
        code, lines, a = b'', [], BASE
        for n, ws in FUNCS.items():
            code += b''.join(struct.pack('<H', w) for w in ws)
            lines.append('F %08x %d %s' % (a, 2 * len(ws), n))
            a += 2 * len(ws)
        open(os.path.join(tmp, '1ST_READ.BIN'), 'wb').write(code)
        open(os.path.join(tmp, 'BASE'), 'w').write('%08X\n' % BASE)
        open(os.path.join(tmp, 'functions.txt'), 'w').write('\n'.join(lines) + '\n')
        os.makedirs(os.path.join(tmp, 'src'))
        script = ("import sys; sys.path.insert(0, 'tools'); sys.path.insert(0, 'tools/5-generated/gen_equiv')\n"
                  "import toolpath, gen_core, gen_drv\n"
                  "for n in ('fsubc', 'fxor', 'fsub'):\n"
                  "    try:\n"
                  "        src, c = gen_drv.build(n, 'r0', False)\n"
                  "        print('OUT', n, ' '.join(src.split()))\n"
                  "    except gen_core.Skip as e:\n"
                  "        print('OUT', n, 'SKIPPED', e)\n")
        out = subprocess.run([sys.executable, '-c', script], cwd=tmp, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                             universal_newlines=True).stdout
        got = {l.split()[1]: l.split(None, 2)[2] for l in out.splitlines() if l.startswith('OUT')}
        bad = [n + ': ' + got.get(n, out[-300:])[:200] for n in FUNCS if 'SKIPPED' in got.get(n, 'SKIPPED')]
        if 'fxor' in got and 'SKIPPED' not in got['fxor'] and '0x5' not in got['fxor'] and ' 5' not in got['fxor']:
            bad.append('xor: does not return 5: ' + got['fxor'][:200])
        if bad:
            self.fail('[ERROR] gen selfclear check failed:\n' + '\n'.join(bad))


if __name__ == '__main__':
    unittest.main()
