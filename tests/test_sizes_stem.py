"""Every compile sizes.py makes has a scratch name of its own (scripts/tools/7-reduction/sizes.py c_size and unit_sizes). equiv.compile_link
names its logs and outputs after the scratch file's stem, so two compiles in one process under one stem reused each other's files: the
second came back as not compilable (Power Stone 2: 416 of 859 units 'ERR' in one sizes run, and a size gate that compared two builds of
one function saw the second as None). No game data, no compiler: equiv and gen_drv are stand-ins. Stdlib only.

    check.py      c_size       two calls in one process compile two different scratch files; the second is measured, not None
                  cleanup      after each call no zz_size file is left in src/ or build/equiv/
                  unit_sizes   the same for units: two calls, two stems, nothing left behind
"""
import os
import shutil
import sys
import tempfile
import types
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), 'scripts', 'tools'))
import toolpath  # noqa: E402,F401


class TestSizesStem(unittest.TestCase):
    def setUp(self):
        self.addCleanup(os.chdir, os.getcwd())
        saved = list(sys.path)
        self.addCleanup(sys.path.__setitem__, slice(None), saved)
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp, True)
        os.makedirs(os.path.join(self.tmp, 'src'))
        os.makedirs(os.path.join(self.tmp, 'build', 'equiv'))
        os.chdir(self.tmp)
        self.stems = []
        stems = self.stems

        def compile_link(f, defines):
            stem = os.path.splitext(os.path.basename(f))[0]
            if stem in stems:                       # the old harness: a stem used twice found the first compile's files
                raise SystemExit('[ERROR] compile failed: log of %s reused' % stem)
            stems.append(stem)
            with open('build/equiv/%s.map' % stem, 'w') as m:
                m.write("P  H'0C000000 - H'0C000013  H'00000014\n")
            with open('build/equiv/%s.%d.shc.log' % (stem, os.getpid()), 'w') as m:
                m.write('log')
            return b'\x00' * 20, {'_f': 0x0C000000, '_zz_size_end': 0x0C000010}
        eq = types.ModuleType('equiv')
        eq.names = lambda: {}
        eq.functions = lambda: {'f': (0, 16)}
        eq.outside_names = lambda f, table: ({}, {'f'})
        eq.compile_link = compile_link
        eq.SCRATCH = 0x0C000000
        gd = types.ModuleType('gen_drv')
        gd.head_protos = lambda items: ''
        for name, mod in (('equiv', eq), ('gen_drv', gd)):
            old = sys.modules.get(name)
            sys.modules[name] = mod
            self.addCleanup(lambda n=name, o=old: sys.modules.__setitem__(n, o) if o else sys.modules.pop(n, None))
        sys.modules.pop('sizes', None)
        self.addCleanup(sys.modules.pop, 'sizes', None)
        import sizes
        self.sizes = sizes

    def leftovers(self):
        return [f for d in ('src', os.path.join('build', 'equiv')) for f in os.listdir(d) if f.startswith('zz_size')]

    def test_c_size_twice(self):
        a = self.sizes.c_size('f', 'int f(int a4)\n{\n    return a4;\n}\n', {}, '')
        b = self.sizes.c_size('f', 'int f(int a4)\n{\n    return a4 + 1;\n}\n', {}, '')
        self.assertIsNotNone(a)
        self.assertIsNotNone(b)
        self.assertEqual(len(set(self.stems)), 2)

    def test_c_size_cleanup(self):
        self.sizes.c_size('f', 'int f(int a4)\n{\n    return a4;\n}\n', {}, '')
        self.assertEqual(self.leftovers(), [])

    def test_unit_sizes_twice(self):
        text = 'int f(int a4)\n{\n    return a4;\n}\n'
        a = self.sizes.unit_sizes('src/u.c', text, {}, {'f': (0, 16)})
        b = self.sizes.unit_sizes('src/u.c', text, {}, {'f': (0, 16)})
        self.assertIsInstance(a, dict)
        self.assertIsInstance(b, dict)
        self.assertEqual(len(set(self.stems)), 2)
        self.assertEqual(self.leftovers(), [])


if __name__ == '__main__':
    unittest.main()
