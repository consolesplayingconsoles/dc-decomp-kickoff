#!/usr/bin/env python3
"""Short functions that end in a tail jump to another function, passing on argument registers they never write
(scripts/tools/10-port/thunks.py): the thunk's C must take them and pass them on. No game data, no compiler. Stdlib only.

    passes      a thunk whose C takes nothing, jumping to a function that takes two ints, is listed as passing r4 r5
    written     a register the thunk writes before the jump is its own value, not one passed on: only r5 is listed
    declared    a thunk whose C already takes both is not listed
    no_jump     a short function that returns (rts) instead of jumping is not a thunk
"""
import contextlib
import importlib.util
import io
import os
import shutil
import sys
import tempfile
import unittest
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))
TOOLS = os.path.join(os.path.dirname(HERE), 'scripts', 'tools')

TARGET = 'void target(int a, int b)\n{\n}\n'


def listing(*body):
    """a shdis.py listing of one function, `thunk`, with the given instructions"""
    lines = ['thunk:']
    for k, (op, args, com) in enumerate(body):
        lines.append('%08x %04x  %-6s %s%s' % (0x0C010000 + 2 * k, 0, op, args, ('  ; ' + com) if com else ''))
    return '\n'.join(lines) + '\n'


LOAD = ('mov.l', '@(0x8,pc),r3', '=0c020000 target')
JUMP = [('jmp', '@r3', ''), ('nop', '', '')]


class Thunks(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix='thunks')
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.src = os.path.join(self.tmp, 'src')
        os.makedirs(self.src)

    def run_tool(self, thunk_c, dis):
        with open(os.path.join(self.src, 'a.c'), 'w') as f:
            f.write(thunk_c + TARGET)
        path = os.path.join(self.tmp, 'ALL.DIS')
        with open(path, 'w') as f:
            f.write(dis)
        saved_path, saved_mod = list(sys.path), sys.modules.pop('dropped_args', None)
        try:
            with mock.patch.dict(os.environ, {'PORT_SRC': self.src}):
                spec = importlib.util.spec_from_file_location('thunks_under_test', os.path.join(TOOLS, '10-port', 'thunks.py'))
                mod = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(mod)
            out = io.StringIO()
            with mock.patch.object(sys, 'argv', ['thunks.py', path]), contextlib.redirect_stdout(out):
                mod.main()
        finally:
            sys.path[:] = saved_path
            sys.modules.pop('dropped_args', None)
            if saved_mod is not None:
                sys.modules['dropped_args'] = saved_mod
        return out.getvalue()

    def test_passes(self):
        out = self.run_tool('void thunk(void)\n{\n}\n', listing(LOAD, *JUMP))
        self.assertIn('thunk', out)
        self.assertIn('passes on r4 r5', out, out)

    def test_written(self):
        out = self.run_tool('void thunk(void)\n{\n}\n', listing(('mov', '#1,r4', ''), LOAD, *JUMP))
        self.assertIn('passes on r5 ', out, 'r4 is the thunk\'s own value: %r' % out)

    def test_declared(self):
        out = self.run_tool('void thunk(int a, int b)\n{\n}\n', listing(LOAD, *JUMP))
        self.assertEqual(out, '', 'its C already takes both')

    def test_no_jump(self):
        out = self.run_tool('void thunk(void)\n{\n}\n', listing(LOAD, ('rts', '', ''), ('nop', '', '')))
        self.assertEqual(out, '', 'a function that returns is not a thunk')


if __name__ == '__main__':
    unittest.main()
