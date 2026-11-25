#!/usr/bin/env python3
"""boundaries.py --discover --values: routines the code hands on as values (scripts/tools/common/boundaries.py). No game data, no
compiler. Stdlib only.

--discover names what listed code jumps or calls to. A routine the game only hands on (a callback: its address loaded from a pool word
and passed to a call, or stored) is jumped to by nobody in the listed code, so nothing named it: on Jet Set Radio 830 such routines
(151 KB) stayed unlisted until the build from C refused to hand on their addresses. With --values, the address in a pool word that a
listed function loads and does not read through is a candidate too; boundaries.py's checks then decide each one (data is refused).

    check.py      a temp repo: c loads a pool word holding an unlisted routine's address into r4 and calls the listed f1; q loads a
                  pool word holding another routine's address and reads through it (mov.l @r1,r0):
                    plain    --discover alone: neither is a candidate (as before)
                    values   --discover --values: c's routine is a candidate; q's (read through) is not; the listed f1 is not
                    checked  the candidate, given to boundaries.py: "function"
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
BASE = 0x8C010000
NOP, RTS = 0x0009, 0x000B


def w(*ws):
    return b''.join(struct.pack('<H', x) for x in ws)


class TestBoundariesValues(unittest.TestCase):
    def test_boundaries_values(self):
        code, listed, at = b'', [], {}

        def put(name, data, is_listed, align=2):
            nonlocal code
            while (BASE + len(code)) % align:
                code += w(0)
            at[name] = BASE + len(code)
            code += data
            if is_listed:
                listed.append((name, at[name], len(data)))
        routine = w(0x4F22, 0x4F26, RTS, NOP)            # push pr, pop pr, return
        put('f1', w(RTS, NOP), True)
        put('g_cb', routine, False)
        put('g_data', routine, False)
        put('c', w(0xD402, 0xD103, 0x410B, NOP, RTS, NOP) + struct.pack('<II', at['g_cb'], at['f1']), True, align=4)
        put('q', w(0xD101, 0x6012, RTS, NOP) + struct.pack('<I', at['g_data']), True, align=4)
        tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, tmp, True)
        shutil.copytree(os.path.join(SKILL, 'scripts', 'tools'), os.path.join(tmp, 'tools'), ignore=shutil.ignore_patterns('__pycache__'))
        open(os.path.join(tmp, '1ST_READ.BIN'), 'wb').write(code)
        open(os.path.join(tmp, 'BASE'), 'w').write('%08X\n' % BASE)
        open(os.path.join(tmp, 'functions.txt'), 'w').write(''.join('F %08x %d %s\n' % (a, s, n) for n, a, s in listed))

        def found(*flags):
            r = subprocess.run([sys.executable, 'tools/common/boundaries.py', '--discover'] + list(flags), cwd=tmp,
                               capture_output=True, text=True, timeout=120)
            return {int(l.split()[0], 16) & 0x1FFFFFFF for l in r.stdout.splitlines() if l.split('#')[0].split()}, r.stdout + r.stderr
        bad = []
        plain, out = found()
        if at['g_cb'] & 0x1FFFFFFF in plain or at['g_data'] & 0x1FFFFFFF in plain:
            bad.append('plain: --discover alone names a value: %s' % out)
        vals, out = found('--values')
        if at['g_cb'] & 0x1FFFFFFF not in vals:
            bad.append('values: the routine c hands on is not a candidate: %s' % out)
        if at['g_data'] & 0x1FFFFFFF in vals or at['f1'] & 0x1FFFFFFF in vals:
            bad.append('values: a read-through address or a listed entry is a candidate: %s' % out)
        if not bad:
            open(os.path.join(tmp, 'cands.txt'), 'w').write('%08x\n' % at['g_cb'])
            r2 = subprocess.run([sys.executable, 'tools/common/boundaries.py', 'cands.txt'], cwd=tmp, capture_output=True, text=True, timeout=120)
            if not any(' function ' in l and 'not a function' not in l for l in r2.stdout.splitlines()):
                bad.append('checked: the candidate is not accepted as a function:\n%s' % r2.stdout)
        if bad:
            self.fail('[ERROR] boundaries values check failed:\n' + '\n'.join(bad))


if __name__ == '__main__':
    unittest.main()
