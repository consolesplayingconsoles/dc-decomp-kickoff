#!/usr/bin/env python3
"""rte in the simulator (scripts/tools/sim/sh4sim.py): the instruction of an exception or interrupt handler. Stdlib only, no compiler, no game data.

rte returns to SPC and loads SR from SSR once its delay slot has run. The simulator has no exceptions: a run starts with SPC = the
return address and SSR = the entry SR, so a handler ends the run like rts and gives SR back. Virtua Tennis FUN_8c1fc7cc / 7d0 / 77c (the
handlers of the interrupt setup, `rte` after saving and restoring r0, r4, r5, pr) stopped with "unknown instruction 002B".

    check.py      f: stc sr,r3 / mov.l @(pool),r2 / or r2,r3 / ldc r3,sr / mov #7,r0 / rte / mov #9,r1 (delay slot)
                  runs without error, r0 = 7, r1 = 9 (the slot ran), SR is back at the entry value 0x40000000 (the BL set before the
                  rte is undone), and the run ended
"""
import unittest
from unittest import mock
import os
import shutil
import struct
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
SKILL = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(SKILL, "scripts", "tools"))
import toolpath  # noqa: E402,F401  (every tools folder on the import path: sim/, common/, the steps)
import sh4sim  # noqa: E402

BASE = 0x0C010000


class TestRte(unittest.TestCase):
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

    def test_rte(self):
        words = [0x0302, 0xD203, 0x232B, 0x430E, 0xE007, 0x002B, 0xE109, 0x0009]    # stc sr,r3 / mov.l @(12,pc),r2 / or r2,r3 / ldc r3,sr / mov #7,r0 / rte / mov #9,r1 / pad
        code = struct.pack('<8H', *words) + struct.pack('<I', 0x10000000)
        bad = []
        tmp = tempfile.mkdtemp()
        try:
            open(os.path.join(tmp, "1ST_READ.BIN"), "wb").write(code)
            case = {'exe': '1ST_READ.BIN', 'base': '%08X' % BASE, 'entry': '%08X' % BASE, 'end': '%08X' % (BASE + 16)}
            r = sh4sim.run(case, tmp)
            out = r.get('out') or {}
            if r.get('error'):
                bad.append('stopped: %s' % r['error'])
            else:
                if out.get('r0') != '00000007':
                    bad.append('r0 is %s, want 00000007' % out.get('r0'))
                if out.get('r1') != '00000009':
                    bad.append('r1 is %s, want 00000009 (the delay slot did not run)' % out.get('r1'))
                if r.get('sr') != '40000000':
                    bad.append('sr is %s, want 40000000 (rte did not give SR back)' % r.get('sr'))
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
        if not bad:
            print("[rte] ok: rte runs its delay slot, gives SR back and ends the run")
            return
        self.fail("[ERROR] rte check failed:\n" + "\n".join(bad))


if __name__ == '__main__':
    unittest.main()
