#!/usr/bin/env python3
"""The addresses a function touches that follow from its arguments (scripts/tools/5-generated/gen_equiv/gen_drv.py addr_vals), on
expressions the reader writes. No game data, no compiler. Stdlib only.

Drawing evaluates a memory address as Python after putting the argument values in. A table index made from a comparison, which C writes
as `(a4 > 0x100) ? 1 : 0`, stopped it ("Skip addr expr", Virtua Tennis cpuDblSignalPut: 0x8C3343AC + (((int)a4 > (int)0x100 ? 1 : 0) << 2)).

    check.py      ternary   that address with a4 = 0x0C800000 (a pointer, above 0x100) is 0x8C3343B0, with a4 = 5 it is 0x8C3343AC
                  plain     an address with no ternary still evaluates as before
"""
import unittest
from unittest import mock
import os
import shutil
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
TOOLS = os.path.join(os.path.dirname(HERE), 'scripts', 'tools')


class C:
    def __init__(self, exprs):
        self.mem_addrs = [('e', e) for e in exprs]


class TestAddrexpr(unittest.TestCase):
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

    def test_addrexpr(self):
        bad = []
        tern = '(0x8C3343AC + (((((int)a4 > (int)0x100)) ? 1 : 0) << 2))'
        plain = '(0x8C100000 + (a4 << 2))'
        for name, exprs, base, want in (('ternary high', [tern], {'a4': 0x0C800000}, [0x8C3343B0]),
                                        ('ternary low', [tern], {'a4': 5}, [0x8C3343AC]),
                                        ('plain', [plain], {'a4': 3}, [0x8C10000C])):
            try:
                got = gen_drv.addr_vals(C(exprs), base)
            except Exception as e:
                got = '%s %s' % (type(e).__name__, str(e)[:60])
            if got != want:
                bad.append('%s: %s, want %s' % (name, got if isinstance(got, str) else [hex(x) for x in got], [hex(x) for x in want]))
        if bad:
            self.fail('[ERROR] addrexpr check failed:\n' + '\n'.join(bad))


if __name__ == '__main__':
    unittest.main()
