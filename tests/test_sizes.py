#!/usr/bin/env python3
"""How the shrink measures the current C (scripts/tools/sizes.py c_size_any), with no game data and no compiler. Stdlib only.

    check.py      c_size is replaced by a stand-in that fails for one set of prototypes, as the compiler does when a set written
                  for the new C declares a float where the current C uses an int ("Scalar required for !", Crazy Taxi camUpdate
                  measured against its `flat` form). The current C is measured against each set in turn, the first that compiles:
                    other    the first set fails, the second compiles: the size is the second's (not None, which the shrink would
                             log as "not smaller" and skip a function that is about 1,300 bytes smaller)
                    first    the first set compiles: the later sets are not tried
                    none     no set compiles: None
                  The current C is measured first under the declarations of its own unit (the ones it was proven against), then
                  the sets (Crazy Taxi Psg_Execute, pcarDrive: the new sets declare a callee as returning float and the proven C
                  tests it with !, which the compiler rejects; under its own declarations it compiles):
                    head     a head that compiles is used and no set is tried
                    headbad  a head that does not compile falls back to the sets
                    unit     unit_head takes everything above the first function definition, comments with braces in them included
"""
import unittest
from unittest import mock
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), 'scripts', 'tools'))
import toolpath  # noqa: E402,F401
import sizes  # noqa: E402


class TestSizes(unittest.TestCase):
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

    def test_sizes(self):
        tried = []

        def fake(name, src, protos, head=None):
            tried.append(head if head is not None else protos)
            return {'bad': None, 'good': 11640, 'other': 11700, 'own': 3380}[head if head is not None else protos]

        sizes.c_size = fake
        got = {}
        got['other'] = (sizes.c_size_any('f', 'int f(void){}', ['bad', 'good']), tried[:])
        del tried[:]
        got['first'] = (sizes.c_size_any('f', 'int f(void){}', ['good', 'other']), tried[:])
        del tried[:]
        got['none'] = (sizes.c_size_any('f', 'int f(void){}', ['bad', 'bad']), tried[:])
        del tried[:]
        got['head'] = (sizes.c_size_any('f', 'int f(void){}', ['bad'], 'own'), tried[:])
        del tried[:]
        got['headbad'] = (sizes.c_size_any('f', 'int f(void){}', ['good'], 'bad'), tried[:])
        unit = '/* a comment with a brace { and (a) { in it */\n\nint g(int);\nfloat h(float);\n\nint f(int a4)\n{\n    return a4;\n}\n'
        got['unit'] = (sizes.unit_head(unit), None)
        want = {'head': (3380, ['own']), 'headbad': (11640, ['bad', 'good']),
                'unit': ('/* a comment with a brace { and (a) { in it */\n\nint g(int);\nfloat h(float);', None),
                'other': (11640, ['bad', 'good']), 'first': (11640, ['good']), 'none': (None, ['bad', 'bad'])}
        bad = ['%s: got %s, want %s' % (k, got[k], w) for k, w in want.items() if got[k] != w]
        if bad:
            self.fail("[ERROR] sizes check failed:\n" + "\n".join(bad))


if __name__ == '__main__':
    unittest.main()
