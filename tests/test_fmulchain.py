#!/usr/bin/env python3
"""The pass that folds a temporary used once back into its use (scripts/tools/5-generated/gen_equiv/gen_drv.py inline_single), on
the statements the reader writes. No game data, no compiler. Stdlib only.

SHC reassociates a chain of float multiplies written in one expression: (a * b) * c becomes (c * a) * b or a * (b * c), which rounds
differently once the values pass 2^24. The reader writes the first product as a statement of its own to keep its order; this pass folded
it back (Virtua Tennis circuitStatsCalc: `(int)((((float)A * u53)) * (float)B)`, two words differing by 64 units of the last place).

    check.py      product   a float product used in another product stays a statement of its own
                  sum       a float sum used in a product is folded as before
                  use       a float product used in a sum is folded as before
                  int       an integer product used in a product is folded as before
"""
import unittest
from unittest import mock
import os
import shutil
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
TOOLS = os.path.join(os.path.dirname(HERE), 'scripts', 'tools')


class TestFmulchain(unittest.TestCase):
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
        open('functions.txt', 'w').write('F 8c020000 64 fn\n')
        open('BASE', 'w').write('8C020000\n')
        open('1ST_READ.BIN', 'wb').write(b'\x00\x09' * 32)
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

    def test_fmulchain(self):
        bad = []
        for name, body, decls, kept in (
                ('product', ['u1 = ((float)a4 * f4);', 'return (u1 * (float)a5);'], ['float u1;'], True),
                ('sum', ['u1 = ((float)a4 + f4);', 'return (u1 * (float)a5);'], ['float u1;'], False),
                ('use', ['u1 = ((float)a4 * f4);', 'return (u1 + (float)a5);'], ['float u1;'], False),
                ('int', ['t1 = (a4 * a5);', 'return (t1 * a6);'], ['int t1;'], False)):
            got = gen_drv.inline_single(list(body), list(decls))
            if (len(got) == 2) != kept:
                bad.append('%s: %s' % (name, got))
        if bad:
            self.fail('[ERROR] fmulchain check failed:\n' + '\n'.join(bad))


if __name__ == '__main__':
    unittest.main()
