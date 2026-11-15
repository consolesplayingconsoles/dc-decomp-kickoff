#!/usr/bin/env python3
"""textpass.apply_one keeps a pass on a function's current C only when it compiles smaller and the function still passes in its file; the
file is put back as it was otherwise. No game data, no compiler (size and check are stand-ins). Stdlib only.

    check.py      a temp repo with src/gen_a.c holding f and g:
                    kept       a smaller C that passes replaces f in its file, g untouched
                    bigger     a C that is not smaller leaves the file as it was
                    failed     a smaller C that fails puts the old file back and checks it again
                    nothing    a pass that changes nothing writes nothing
"""
import unittest
from unittest import mock
import os
import shutil
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
TOOLS = os.path.join(os.path.dirname(HERE), 'scripts', 'tools')
SRC = 'int f(int a4)\n{\n    int t1;\n\n    t1 = a4;\n    return t1;\n}\n\nint g(int a4)\n{\n    return a4;\n}\n'


class TestTextpass(unittest.TestCase):
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

    def test_textpass(self):
        tmp = tempfile.mkdtemp()
        try:
            os.chdir(tmp)
            os.makedirs('src')
            sys.path.insert(0, os.path.join(TOOLS, '7-reduction'))
            sys.path.insert(0, TOOLS)
            import toolpath  # noqa: F401
            import textpass
            reg = lambda c: c.replace('    int t1;', '    register int t1;')
            bad = []
            open('src/gen_a.c', 'w').write(SRC)
            n, why = textpass.apply_one('f', reg, lambda fn, c, u: 10 if 'register' in c else 20, lambda p, fn: ('EQUIVALENT', 'ok'), None)
            t = open('src/gen_a.c').read()
            if n != 10 or 'register int t1;' not in t or 'int g(int a4)\n{\n    return a4;\n}' not in t:
                bad.append('kept: %s %s %r' % (n, why, t))
            open('src/gen_a.c', 'w').write(SRC)
            n, why = textpass.apply_one('f', reg, lambda fn, c, u: 30 if 'register' in c else 20, lambda p, fn: ('EQUIVALENT', 'ok'), None)
            if n is not None or open('src/gen_a.c').read() != SRC:
                bad.append('bigger: %s %s' % (n, why))
            open('src/gen_a.c', 'w').write(SRC)
            checks = []
            n, why = textpass.apply_one('f', reg, lambda fn, c, u: 10 if 'register' in c else 20,
                                        lambda p, fn: (checks.append(open(p).read()) or ('DIFFERS', 'f DIFFERS case 1')), None)
            if n is not None or open('src/gen_a.c').read() != SRC or len(checks) != 2 or checks[1] != SRC:
                bad.append('failed: %s %s, %d checks' % (n, why, len(checks)))
            open('src/gen_a.c', 'w').write(SRC)
            n, why = textpass.apply_one('f', lambda c: c, lambda fn, c, u: 10, lambda p, fn: ('EQUIVALENT', 'ok'), None)
            if n is not None or why != 'nothing to change':
                bad.append('nothing: %s %s' % (n, why))
            if bad:
                self.fail('[ERROR] textpass check failed:\n' + '\n'.join(bad))
            print('[textpass] ok: smaller and passing is kept, bigger is left, failing goes back and is checked again, no change writes nothing')
        finally:
            os.chdir('/')
            shutil.rmtree(tmp, ignore_errors=True)


if __name__ == '__main__':
    unittest.main()
