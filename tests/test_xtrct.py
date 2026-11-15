#!/usr/bin/env python3
"""xtrct is written: Rn = (Rm << 16) | (Rn >> 16), the middle of a register pair
(scripts/tools/5-generated/gen_equiv/gen_core.py). No game data, no compiler. Stdlib only.

The generator stopped on xtrct ("cannot read: xtrct r5,r0", Zombie Revenge FUN_0c9dfce0).

    check.py      a function `swap.w r5,r0; xtrct r5,r0; rts; nop`:
                    written   the generator writes it
                    shifts    the C shifts r5 left and r0 right by 16
"""
import unittest
from unittest import mock
import os
import shutil
import struct
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
SKILL = os.path.dirname(HERE)
BASE = 0x0C010000
W = lambda ws: b''.join(struct.pack('<H', w) for w in ws)

FN = [0x6059,                       # swap.w r5,r0
      0x205D,                       # xtrct r5,r0
      0x000B, 0x0009]               # rts / nop


class TestXtrct(unittest.TestCase):
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

    def test_xtrct(self):
        bad = []
        tmp = tempfile.mkdtemp()
        try:
            shutil.copytree(os.path.join(SKILL, 'scripts', 'tools'), os.path.join(tmp, 'tools'), ignore=shutil.ignore_patterns('__pycache__'))
            code = W(FN) + (W([0x0009]) if len(FN) % 2 else b'')
            open(os.path.join(tmp, '1ST_READ.BIN'), 'wb').write(code)
            open(os.path.join(tmp, 'BASE'), 'w').write('%08X\n' % BASE)
            open(os.path.join(tmp, 'functions.txt'), 'w').write('F %08x %d xform\n' % (BASE, len(code)))
            os.makedirs(os.path.join(tmp, 'src'))
            script = ("import sys; sys.path.insert(0, 'tools'); import toolpath, gen_core, gen_drv\n"
                      "try:\n"
                      "    print(gen_drv.build('xform', 'r0', False)[0])\n"
                      "except gen_core.Skip as e:\n"
                      "    print('SKIPPED ' + str(e))\n")
            out = subprocess.run([sys.executable, '-c', script], cwd=tmp, stdout=subprocess.PIPE,
                                 stderr=subprocess.STDOUT, universal_newlines=True).stdout
            if 'SKIPPED' in out or 'xform' not in out:
                bad.append('written: the generator did not write it:\n%s' % out)
            elif '<< 16' not in out or '>> 16' not in out:
                bad.append('shifts: no << 16 / >> 16 in the C:\n%s' % out)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
        if bad:
            self.fail('[ERROR] xtrct check failed:\n' + '\n'.join(bad))


if __name__ == '__main__':
    unittest.main()
