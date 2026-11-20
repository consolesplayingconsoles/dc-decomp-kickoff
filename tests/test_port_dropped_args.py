#!/usr/bin/env python3
"""Functions whose C takes fewer arguments than their callers pass (scripts/tools/10-port/dropped_args.py). On the SH-4 a
dropped argument still reaches the next call in its register; on the host it is lost. No game data, no compiler. Stdlib only.

    counts     a parameter list's int and float arguments: void and () take none, a float pointer is an int, `...` is
               variadic, a structure passed on the stack (Stk<n>) takes no register
    dropped    a definition that takes one int where another file's declaration passes two ints and a float is listed,
               with both counts
    same_file  a declaration in the definition's own file is not a caller: nothing is listed
    variadic   a variadic definition is never listed, whatever its callers pass
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


def load(src_dir):
    """dropped_args.py reads PORT_SRC when it is imported: a fresh module for each folder"""
    with mock.patch.dict(os.environ, {'PORT_SRC': src_dir}):
        spec = importlib.util.spec_from_file_location('dropped_args_under_test', os.path.join(TOOLS, '10-port', 'dropped_args.py'))
        mod = importlib.util.module_from_spec(spec)
        saved = list(sys.path)
        try:
            spec.loader.exec_module(mod)
        finally:
            sys.path[:] = saved
    return mod


class DroppedArgs(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix='dropped_args')
        self.addCleanup(shutil.rmtree, self.tmp, True)

    def write(self, name, text):
        with open(os.path.join(self.tmp, name), 'w') as f:
            f.write(text)

    def run_main(self):
        mod = load(self.tmp)
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            mod.main()
        return out.getvalue(), err.getvalue()

    def test_counts(self):
        counts = load(self.tmp).counts
        self.assertEqual(counts('void'), (0, 0, False))
        self.assertEqual(counts(''), (0, 0, False))
        self.assertEqual(counts('int a, float b, float *c'), (2, 1, False), 'a float pointer travels in an int register')
        self.assertEqual(counts('const char *fmt, ...'), (1, 0, True))
        self.assertEqual(counts('int a, Stk16 s'), (1, 0, False), 'a structure on the stack takes no register')

    def test_dropped(self):
        self.write('a.c', 'int f(int a)\n{\n    return a;\n}\n')
        self.write('b.c', 'int f(int a, int b, float c);\nint g(void)\n{\n    return f(1, 2, 3.0f);\n}\n')
        out, err = self.run_main()
        self.assertIn('f', out.split()[:1], 'f is listed: %r' % out)
        self.assertIn('takes 1 int 0 float, callers pass up to 2 int 1 float (b.c)', out)
        self.assertIn('1 functions take fewer arguments', err)

    def test_same_file(self):
        self.write('a.c', 'int f(int a, int b);\nint f(int a)\n{\n    return a;\n}\n')
        out, err = self.run_main()
        self.assertEqual(out, '', 'a declaration in the same file is not a caller')
        self.assertIn('0 functions take fewer arguments', err)

    def test_variadic(self):
        self.write('a.c', 'int p(const char *fmt, ...)\n{\n    return 0;\n}\n')
        self.write('b.c', 'int p(const char *fmt, int a, int b, int c);\n')
        out, err = self.run_main()
        self.assertEqual(out, '', 'a variadic definition takes whatever it is passed')


if __name__ == '__main__':
    unittest.main()
