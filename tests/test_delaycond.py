#!/usr/bin/env python3
"""A delayed branch (bt/s, bf/s) decides on the T flag as it was before its delay slot, whatever the slot does to T or to the variables the
condition names (scripts/tools/5-generated/gen_equiv/gen_core.py). No game data, no compiler. Stdlib only.

The generator read T after stepping the delay slot. With `dt r7; bf/s L; shlr r6` (the LZ decompressor Zombie Revenge FUN_0c0c4ff0) the
branch tested the bit shlr shifted out where the original tested the dt, and the C never ended.

    check.py      `dt r4; bf/s L; shlr r5; mov #1,r0; rts; nop; L: mov #2,r0; rts; nop`:
                    before    the condition is the dt result (it names a4), not the bit shifted out of a5
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

FN = [0x4410, 0x8F03, 0x4501,                        # dt r4 / bf/s L / shlr r5 (the delay slot)
      0xE001, 0x000B, 0x0009,                        # mov #1,r0 / rts / nop
      0xE002, 0x000B, 0x0009]                        # L: mov #2,r0 / rts / nop


def build(tmp, fn):
    code = W(fn)
    open(os.path.join(tmp, '1ST_READ.BIN'), 'wb').write(code)
    open(os.path.join(tmp, 'BASE'), 'w').write('%08X\n' % BASE)
    open(os.path.join(tmp, 'functions.txt'), 'w').write('F %08x %d xform\n' % (BASE, len(code)))
    os.makedirs(os.path.join(tmp, 'src'), exist_ok=True)
    script = ("import sys; sys.path.insert(0, 'tools'); import toolpath, gen_core, gen_drv\n"
              "try:\n"
              "    print(gen_drv.build('xform', 'r0', False)[0])\n"
              "except gen_core.Skip as e:\n"
              "    print('SKIPPED ' + str(e))\n")
    return subprocess.run([sys.executable, '-c', script], cwd=tmp, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, universal_newlines=True).stdout


class TestDelaycond(unittest.TestCase):
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

    def test_delaycond(self):
        bad = []
        tmp = tempfile.mkdtemp()
        try:
            shutil.copytree(os.path.join(SKILL, 'scripts', 'tools'), os.path.join(tmp, 'tools'), ignore=shutil.ignore_patterns('__pycache__'))
            out = build(tmp, FN)
            if 'SKIPPED' in out or 'xform' not in out:
                bad.append('written: the generator did not write it:\n%s' % out)
            else:
                conds = re.findall(r'\bif \((.*)\) \{', out)
                if not conds or not any('a4' in c for c in conds):
                    bad.append('before: no condition names a4 (the dt), the branch used the bit the delay slot shifted out:\n%s' % out)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
        if bad:
            self.fail('[ERROR] delaycond check failed:\n' + '\n'.join(bad))


if __name__ == '__main__':
    unittest.main()
