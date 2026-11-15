#!/usr/bin/env python3
"""A tail the structured form copied into an arm is written once (scripts/tools/5-generated/gen_equiv/gen_drv.py factor_tails).
No game data, no compiler. Stdlib only.

The structured form copies the code after a join into each arm that reaches it: `if (c) { P; T } Q; T` with T ending in a return
(Zombie Revenge FUN_0c02ce56: a ten-line ending three times, 244 bytes in the original, 1,376 in C).

    check.py      factor_tails on C text:
                    once      `if (c) { a = 1; f(); return 2; } b = 3; f(); return 2;` -> `if (c) { a = 1; } else { b = 3; } f(); return 2;`
                    blocks    a tail holding a whole if block is moved too
                    arm       an arm left empty becomes the negated condition around the other code
                    keep      an arm that does not end in a return (it falls through) is left as it is
"""
import tempfile
import unittest
from unittest import mock
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SKILL = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(SKILL, 'scripts', 'tools', '5-generated', 'gen_equiv'))


class TestFactortails(unittest.TestCase):
    def setUp(self):
        self.addCleanup(os.chdir, os.getcwd())
        saved_path = list(sys.path)
        self.addCleanup(sys.path.__setitem__, slice(None), saved_path)
        environ = mock.patch.dict(os.environ)
        environ.start()
        self.addCleanup(environ.stop)
        snapshot = self._snapshot_modules()
        self.addCleanup(self._restore_modules, snapshot)

    def workdir(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        return tmp.name

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

    def test_factortails(self):
        os.chdir(self.workdir())
        sys.path.insert(0, os.path.join(SKILL, 'scripts', 'tools'))
        import importlib.util
        spec = importlib.util.spec_from_file_location('gd', os.path.join(SKILL, 'scripts', 'tools', '5-generated', 'gen_equiv', 'gen_drv.py'))
        src = open(spec.origin).read()
        ns = {'re': __import__('re')}
        i = src.index('def factor_tails(body):')
        j = src.index('\ndef ', i + 1)
        exec(src[i:j], ns)
        ft = ns['factor_tails']
        bad = []
        got = ft(['if (c) {', '    a = 1;', '    f();', '    return 2;', '}', 'b = 3;', 'f();', 'return 2;'])
        if got != ['if (c) {', '    a = 1;', '} else {', '    b = 3;', '}', 'f();', 'return 2;']:
            bad.append('once: %s' % got)
        got = ft(['if (c) {', '    a = 1;', '    if (d) {', '        e = 2;', '    }', '    return 2;', '}', 'b = 3;', 'if (d) {', '    e = 2;', '}', 'return 2;'])
        if got != ['if (c) {', '    a = 1;', '} else {', '    b = 3;', '}', 'if (d) {', '    e = 2;', '}', 'return 2;']:
            bad.append('blocks: %s' % got)
        got = ft(['if (c) {', '    f();', '    return 2;', '}', 'b = 3;', 'f();', 'return 2;'])
        if got != ['if (!(c)) {', '    b = 3;', '}', 'f();', 'return 2;']:
            bad.append('arm: %s' % got)
        src_ = ['if (c) {', '    a = 1;', '    f();', '}', 'b = 3;', 'f();', 'return 2;']
        got = ft(list(src_))
        if got != src_:
            bad.append('keep: %s' % got)
        if bad:
            self.fail('[ERROR] factortails check failed:\n' + '\n'.join(bad))


if __name__ == '__main__':
    unittest.main()
