#!/usr/bin/env python3
"""A constant negated by fneg is still a constant, so a product with it keeps the negative literal (scripts/tools/5-generated/gen_equiv/gen_core.py).
No game data, no compiler. Stdlib only.

`fldi1 fr4; fneg fr4; fmul fr4,fr5` multiplies by -1.0. The generator kept `(-1.0f)` as an expression, so the product was written
`f5 * (-1.0f)` and SHC compiled it as -(f5 * 1.0), which flips the sign of a NaN where the original's fmul does not (Zombie Revenge
FUN_0c06ca54). With the negated constant as a constant, the existing compound form `t *= -1.0f` is used.

    check.py      the function above:
                    kept      the C multiplies by -1.0f with a compound assignment
"""
import unittest
from unittest import mock
import os
import re
import shutil
import struct
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
SKILL = os.path.dirname(HERE)
BASE = 0x0C010000
W = lambda ws: b''.join(struct.pack('<H', w) for w in ws)

FN = [0xF49D,                         # fldi1 fr4
      0xF44D,                         # fneg fr4
      0xF542,                         # fmul fr4,fr5
      0xF05C,                         # fmov fr5,fr0
      0x000B, 0x0009]                 # rts / nop


def build(tmp, fn):
    code = W(fn)
    open(os.path.join(tmp, '1ST_READ.BIN'), 'wb').write(code)
    open(os.path.join(tmp, 'BASE'), 'w').write('%08X\n' % BASE)
    open(os.path.join(tmp, 'functions.txt'), 'w').write('F %08x %d xform\n' % (BASE, len(code)))
    os.makedirs(os.path.join(tmp, 'src'), exist_ok=True)
    script = ("import sys; sys.path.insert(0, 'tools'); import toolpath, gen_core, gen_drv\n"
              "try:\n"
              "    print(gen_drv.build('xform', 'fr0', False)[0])\n"
              "except gen_core.Skip as e:\n"
              "    print('SKIPPED ' + str(e))\n")
    return subprocess.run([sys.executable, '-c', script], cwd=tmp, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, universal_newlines=True).stdout


class TestFnegconst(unittest.TestCase):
    def setUp(self):
        self.addCleanup(os.chdir, os.getcwd())
        saved_path = list(sys.path)
        self.addCleanup(sys.path.__setitem__, slice(None), saved_path)
        environ = mock.patch.dict(os.environ)
        environ.start()
        self.addCleanup(environ.stop)
        snapshot = self._snapshot_modules()
        self.addCleanup(self._restore_modules, snapshot)

    @staticmethod
    def _snapshot_modules():
        tools = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'scripts')
        modules = dict(sys.modules)
        state = {}
        for name, mod in modules.items():
            if (getattr(mod, '__file__', None) or '').startswith(tools):
                state[name] = dict(vars(mod))
        return modules, state

    @staticmethod
    def _restore_modules(snapshot):
        modules, state = snapshot
        for name in list(sys.modules):
            if name not in modules:
                del sys.modules[name]
        sys.modules.update(modules)
        for name, saved in state.items():
            vars(modules[name]).clear()
            vars(modules[name]).update(saved)

    def test_fnegconst(self):
        bad = []
        tmp = tempfile.mkdtemp()
        try:
            shutil.copytree(os.path.join(SKILL, 'scripts', 'tools'), os.path.join(tmp, 'tools'), ignore=shutil.ignore_patterns('__pycache__'))
            out = build(tmp, FN)
            if 'SKIPPED' in out or 'xform' not in out:
                bad.append('written: the generator did not write it:\n%s' % out)
            elif not re.search(r'\*= -1\.0f', out):
                bad.append('kept: no compound multiply by -1.0f:\n%s' % out)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
        if bad:
            self.fail('[ERROR] fnegconst check failed:\n' + '\n'.join(bad))


if __name__ == '__main__':
    unittest.main()
