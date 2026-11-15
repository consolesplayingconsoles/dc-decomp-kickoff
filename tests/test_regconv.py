#!/usr/bin/env python3
"""A register a function reads and only changes in place is an input of its own convention (scripts/tools/5-generated/classify.py
register_inputs, no_c_form). No game data, no compiler. Stdlib only.

Zombie Revenge FUN_0c0f1ef4, FUN_0c0f07d4, FUN_0c0f0edc, FUN_0c0f1bdc keep a vertex buffer pointer in r12: `add #28,r12`, stores through
it (`mov.l r5,@-r12`), `pref @r12`, and return with r12 32 bytes on. r12 was counted as written (by the add), so not as an input, and
the reader wrote C from a temp nothing sets: stores through an unset pointer, which the check showed as writes the C never made.

    check.py      synthetic code:
                    inplace   add #28,r12 / mov.l r0,@r12 / mov.l r5,@-r12 / rts / add #32,r12: r12 is an input, no C form
                    set       mov #0,r12 first, then the same: r12 is the function's own, not an input
                    zero      xor r12,r12 first (zeroing, no read): the same
"""
import unittest
from unittest import mock
import os
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
TOOLS = os.path.join(os.path.dirname(HERE), 'scripts', 'tools')
sys.path[:0] = [os.path.join(TOOLS, '5-generated'), TOOLS]
import toolpath  # noqa: E402,F401
import classify  # noqa: E402

BASE = 0x8C010000


def words(ws):
    return b''.join(struct.pack('<H', w) for w in ws)


class TestRegconv(unittest.TestCase):
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

    def test_regconv(self):
        import tempfile
        os.chdir(tempfile.mkdtemp())                     # no_c_form reads functions.txt
        open('functions.txt', 'w').write('F %08x 12 inplace\n' % BASE)
        bad = []
        inplace = words([0x7C1C, 0x2C02, 0x2C56, 0x000B, 0x7C20, 0x0009])      # add #28,r12 / mov.l r0,@r12 / mov.l r5,@-r12 / rts / add #32,r12
        ins = classify.register_inputs(inplace, BASE, BASE, len(inplace))
        if 12 not in ins:
            bad.append('inplace: r12, read and only changed in place, is not an input: %s' % ins)
        if not classify.no_c_form(inplace, BASE, BASE, len(inplace)):
            bad.append('inplace: no_c_form does not name it')
        owned = words([0xEC00, 0x7C1C, 0x2C02, 0x2C56, 0x000B, 0x7C20, 0x0009])  # mov #0,r12 first
        if 12 in classify.register_inputs(owned, BASE, BASE, len(owned)):
            bad.append('set: r12 set by the function itself is taken for an input')
        zeroed = words([0x2CCA, 0x7C1C, 0x2C02, 0x2C56, 0x000B, 0x7C20, 0x0009])   # xor r12,r12 first
        if 12 in classify.register_inputs(zeroed, BASE, BASE, len(zeroed)):
            bad.append('zero: xor r12,r12 is taken for a read of r12')
        if bad:
            self.fail('[ERROR] regconv check failed:\n' + '\n'.join(bad))


if __name__ == '__main__':
    unittest.main()
