#!/usr/bin/env python3
"""coalesce.py never gives a temporary the name of an array local (scripts/tools/5-generated/gen_equiv/coalesce.py). Stdlib only.

It named the shared variables t0, t1, ... u0, u1, ... from the pool size, and the generator's ftrv vectors are float arrays named u<N> too:
a scalar renamed to the name of an array was declared twice and the compiler stopped (Zombie Revenge FUN_0c0ed6d8, `float u3[4];` and
`register float u3;`, "Not a parameter name").

    check.py      two float temporaries that can share a name, and an array u0:
                    apart     the shared name is not u0, the name the array has
"""
import unittest
from unittest import mock
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), 'scripts', 'tools', '5-generated', 'gen_equiv'))
import coalesce  # noqa: E402

TEXT = '''float f(float a4)
{
    float u1;
    float u2;
    float u0[4];

    u1 = a4 * 2.0f;
    u0[0] = u1;
    u2 = u0[0] + 1.0f;
    return u2;
}'''


class TestCoalescearr(unittest.TestCase):
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

    def test_coalescearr(self):
        out = coalesce.coalesce(TEXT)
        scalars = re.findall(r'^\s+float (u\d+);', out, re.M)
        arrays = re.findall(r'^\s+float (u\d+)\[', out, re.M)
        bad = []
        if 'u0' in scalars and 'u0' in arrays:
            bad.append('apart: u0 is declared as a scalar and as an array:\n%s' % out)
        if len(set(scalars)) != len(scalars) or set(scalars) & set(arrays):
            bad.append('apart: a name is declared twice:\n%s' % out)
        if bad:
            self.fail('[ERROR] coalescearr check failed:\n' + '\n'.join(bad))


if __name__ == '__main__':
    unittest.main()
