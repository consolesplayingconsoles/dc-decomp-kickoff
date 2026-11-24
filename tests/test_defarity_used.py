#!/usr/bin/env python3
"""A definition in src/ raises a callee's arity only by the parameters its body uses (scripts/tools/5-generated/gen_equiv/gen_core.py
def_arity, callee_arity). No game data, no compiler. Stdlib only.

The arity of a callee is the larger of the scan of its code and its definition in src/. A generated definition keeps placeholder
parameters the body never uses (`void lock(int a4, int a5)` with neither in its body, the original reading neither): the callee counted
two arguments, its callers passed two registers they never set, and those callers' callers in turn (the scan counts what is passed on).
The draw then threw out every case as depending on registers never set, "the original does not finish on the cases". A parameter
counts up to the last one the body uses, by position (a4 unused and a5 used is still two).

    check.py      a temp repo:
                    unused    callee `rts`, defined `void lock(int a4, int a5)` using neither: no arguments
                    caller    a function whose first act is to call it, no definition: no arguments either (nothing passed through)
                    used      `mov r5,r0; rts`, defined `int second(int a4, int a5) { return a5; }`: two
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
WORDS = [0x000B, 0x0009,                                   # 00 lock: rts; nop
         0x4F22, 0xBFFB, 0x0009, 0x4F26, 0x000B, 0x0009,   # 04 caller: sts.l pr; bsr lock; nop; lds.l pr; rts; nop
         0x6053, 0x000B, 0x0009, 0x0009]                   # 10 second: mov r5,r0; rts; nop
FUNCTIONS = 'F 0c010000 4 lock\nF 0c010004 12 caller\nF 0c010010 6 second\n'
SRC = ('void lock(int a4, int a5)\n{\n    *(int *)0x8C2AF7D8 = 1;\n}\n\n'
       'int second(int a4, int a5)\n{\n    return a5;\n}\n')


class TestDefArityUsed(unittest.TestCase):
    def test_defarity_used(self):
        tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, tmp, True)
        shutil.copytree(os.path.join(SKILL, 'scripts', 'tools'), os.path.join(tmp, 'tools'), ignore=shutil.ignore_patterns('__pycache__'))
        open(os.path.join(tmp, '1ST_READ.BIN'), 'wb').write(b''.join(struct.pack('<H', w) for w in WORDS))
        open(os.path.join(tmp, 'BASE'), 'w').write('%08X\n' % BASE)
        open(os.path.join(tmp, 'functions.txt'), 'w').write(FUNCTIONS)
        os.makedirs(os.path.join(tmp, 'src'))
        open(os.path.join(tmp, 'src', 'gen_a.c'), 'w').write(SRC)
        script = ("import sys; sys.path.insert(0, 'tools'); sys.path.insert(0, 'tools/5-generated/gen_equiv'); import toolpath, gen_core\n"
                  "for n in ('lock', 'caller', 'second'): print('ARITY', n, gen_core.callee_arity(n))\n")
        out = subprocess.run([sys.executable, '-c', script], cwd=tmp, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                             universal_newlines=True).stdout
        got = {l.split()[1]: l.split(None, 2)[2] for l in out.splitlines() if l.startswith('ARITY')}
        want = {'lock': '(0, 0)', 'caller': '(0, 0)', 'second': '(2, 0)'}
        if got != want:
            self.fail('[ERROR] defarity check failed: %r, expected %r\n%s' % (got, want, out[-600:]))


if __name__ == '__main__':
    unittest.main()
