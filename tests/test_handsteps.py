#!/usr/bin/env python3
"""A case can raise the step limit the original is run under (scripts/tools/5-generated/gen_equiv/gen_drv.py original_runs). No game
data, no compiler. Stdlib only.

The original ran under max(100000, size * 60) steps whatever the case said, so a small function with a long loop could never finish
under the tool: Zombie Revenge nlObjPutInit (134 bytes, a 32 x 96 table fill) takes 347,422 steps with any input, and every case,
drawn or supplied by hand, was thrown out as "does not finish". A hand case's own "steps" (sh4sim.py takes it) is now the limit when
it is larger.

    check.py      `L: dt r4 / bf L / rts / nop` with r4 = 60,000 (120,000 steps, over the 100,000 default):
                    default   no "steps" in the case: the original hits the limit (the case is mended to a short one, or dropped)
                    raised    "steps": 1000000 in the case: it finishes, in about 120,000 steps
"""
import unittest
from unittest import mock
import os
import shutil
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
TOOLS = os.path.join(os.path.dirname(HERE), 'scripts', 'tools')


class TestHandsteps(unittest.TestCase):
    def setUp(self):
        self.addCleanup(os.chdir, os.getcwd())
        saved_path = list(sys.path)
        self.addCleanup(sys.path.__setitem__, slice(None), saved_path)
        environ = mock.patch.dict(os.environ)
        environ.start()
        self.addCleanup(environ.stop)
        snapshot = self._snapshot_modules()
        self.addCleanup(self._restore_modules, snapshot)
        global tmp, gen_drv
        tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, tmp, True)
        os.chdir(tmp)
        open('functions.txt', 'w').write('F 8c020000 8 fn\n')
        open('BASE', 'w').write('8C020000\n')
        open('1ST_READ.BIN', 'wb').write(bytes([0x10, 0x44, 0xFD, 0x8B, 0x0B, 0x00, 0x09, 0x00]))      # dt r4 / bf L / rts / nop
        sys.path.insert(0, os.path.join(TOOLS, '5-generated', 'gen_equiv'))
        sys.path.insert(0, TOOLS)
        import toolpath  # noqa: E402,F401
        for name in [m for m, v in sys.modules.items() if (getattr(v, '__file__', None) or '').startswith(os.path.join(os.path.dirname(HERE), 'scripts'))]:
            del sys.modules[name]
        import gen_drv  # noqa: E402

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

    def test_handsteps(self):
        bad = []
        base = {'about': 'long loop', 'regs': {'r4': '%08X' % 60000}}
        # raised first: a case that hits the default limit is mended, and the repair is remembered for the next run of the function
        n1 = gen_drv.original_runs('fn', dict(base, steps=1000000))[0]
        if n1 is None or not 110000 <= n1 <= 130000:
            bad.append('raised: with "steps": 1000000 the original took %s steps, expected about 120,000' % n1)
        n0 = gen_drv.original_runs('fn', dict(base))[0]
        if n0 is not None and n0 >= 110000:
            bad.append('default: the original finished the long loop in %s steps under the default limit' % n0)      # (a case that hits it is mended: its inputs shrink)
        if bad:
            self.fail('[ERROR] handsteps check failed:\n' + '\n'.join(bad))


if __name__ == '__main__':
    unittest.main()
