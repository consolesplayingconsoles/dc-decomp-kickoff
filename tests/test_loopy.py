#!/usr/bin/env python3
"""Which functions drawing treats as loops (scripts/tools/5-generated/gen_equiv/gen_drv.py has_back_goto, wired into tests), on
generated text. No game data, no compiler. Stdlib only.

A loop draws its argument values small: a count or a bound of 0xFFFFFFFF is billions of passes and no drawn case ends. The reader sets
has_loop only when it writes a structured loop; a function read in the flat form (a label per block, goto between them) has none, so
Virtua Tennis _div64, a 66-pass bit-by-bit division, was drawn with huge values and no case ended (168 of 408 small-valued vectors do).

    check.py      back      a goto to a label that appears earlier is a loop
                  forward   a goto to a label further down is not
                  none      text with no goto is not
                  wired     tests() takes a function with a backward goto as loopy
"""
import unittest
from unittest import mock
import os
import re
import shutil
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
TOOLS = os.path.join(os.path.dirname(HERE), 'scripts', 'tools')


class TestLoopy(unittest.TestCase):
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

    def test_loopy(self):
        bad = []
        for name, text, want in (('back', 'int f(int a4)\n{\n    L_8C020010:;\n    a4 = a4 - 1;\n    if (a4 != 0) goto L_8C020010;\n    return a4;\n}\n', True),
                                 ('forward', 'int f(int a4)\n{\n    if (a4 != 0) goto L_8C020020;\n    a4 = 1;\n    L_8C020020:;\n    return a4;\n}\n', False),
                                 ('none', 'int f(int a4)\n{\n    return a4 + 1;\n}\n', False)):
            try:
                got = gen_drv.has_back_goto(text)
            except AttributeError:
                self.fail('[ERROR] loopy check failed:\ngen_drv has no has_back_goto()')
            if got != want:
                bad.append('%s: %s, want %s' % (name, got, want))
        src = open(os.path.join(TOOLS, '5-generated', 'gen_equiv', 'gen_drv.py')).read()
        if not re.search(r'loopy=c\.has_loop or has_back_goto\(src\)', src):
            bad.append('wired: tests() does not take a backward goto as a loop')
        if bad:
            self.fail('[ERROR] loopy check failed:\n' + '\n'.join(bad))


if __name__ == '__main__':
    unittest.main()
