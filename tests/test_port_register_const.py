#!/usr/bin/env python3
"""A hardware register the game's C reaches through a variable still goes through the port's hardware model
(scripts/tools/10-port/native_build.py). Needs the host compiler (clang, opt, objcopy, nm): skipped without them.

    variable   Kamui's render start keeps the register's address in a variable, as the original kept it in a register:
               `R9 = (0xA05F8060); ... *(unsigned int *)((R9 + 0x0)) = R3;` (Crazy Taxi, kmiStartNextRender). The address is a
               constant only once the compiler has folded it, after the pass that turns register accesses into calls had
               looked: the store stayed a plain store, x86-64 encoded the address as a sign-extended displacement, and the game
               faulted at 0xFFFFFFFFA05F8060. The compiled object must call port_mmio_w32 for it
    direct     the direct form, `*(unsigned int *)0xA05F8068 = v;`, calls port_mmio_w32 as before
    ram        a store to RAM through a variable stays a store: the object has no call for it
"""
import importlib.util
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
TOOLS = os.path.join(os.path.dirname(HERE), 'scripts', 'tools')
HAVE = all(shutil.which(t) for t in (os.environ.get('CC', 'clang'), 'opt', 'objcopy', 'nm'))   # CC: as native_build.py

VARIABLE = '''int f(int n, int *src)
{
    int R9;
    int R3;
    int i;
    R9 = (0xA05F8060);
    for (i = 0; i < n; i++) {
        R3 = src[i];
        *(unsigned int *)((R9 + 0x0)) = R3;
    }
    return 0;
}
'''
DIRECT = 'int g(int v)\n{\n    *(unsigned int *)0xA05F8068 = v;\n    return 0;\n}\n'
RAM = 'int h(int v)\n{\n    int p;\n    p = (0x0C2B31C4);\n    *(unsigned int *)((p + 0x0)) = v;\n    return 0;\n}\n'


@unittest.skipUnless(HAVE, 'needs clang, opt, objcopy and nm')
class RegisterConst(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp(prefix='register_const')
        for d in ('src', os.path.join('port', 'runtime'), 'tools'):
            os.makedirs(os.path.join(cls.tmp, d))
        for name, text in (('variable.c', VARIABLE), ('direct.c', DIRECT), ('ram.c', RAM)):
            with open(os.path.join(cls.tmp, 'src', name), 'w') as fp:
                fp.write(text)
        with open(os.path.join(cls.tmp, 'port', 'runtime', 'prelude.h'), 'w') as fp:
            fp.write('static __inline__ unsigned int port_k(unsigned int a) { __asm__("" : "+r"(a)); return a; }\n')
        with open(os.path.join(cls.tmp, 'functions.txt'), 'w') as fp:      # the build reads the function list for its call checks
            fp.write('F 0c020000 16 f\nF 0c020010 16 g\nF 0c020020 16 h\n')
        with open(os.path.join(cls.tmp, 'symbols.txt'), 'w') as fp:
            fp.write('')
        with open(os.path.join(cls.tmp, 'sdk.txt'), 'w') as fp:
            fp.write('')
        shutil.copy(os.path.join(TOOLS, 'toolpath.py'), os.path.join(cls.tmp, 'tools'))
        shutil.copy(os.path.join(TOOLS, 'layout.py'), os.path.join(cls.tmp, 'tools'))                  # the build asks it where the C lives
        os.makedirs(os.path.join(cls.tmp, 'tools', '5-generated'))
        shutil.copy(os.path.join(TOOLS, '5-generated', 'sdk_place.py'), os.path.join(cls.tmp, 'tools', '5-generated'))   # the function reader
        shutil.copytree(os.path.join(TOOLS, '10-port'), os.path.join(cls.tmp, 'tools', '10-port'),
                        ignore=shutil.ignore_patterns('__pycache__'))
        cls.saved_path, cls.saved_env = list(sys.path), dict(os.environ)
        cls.saved_modules = {k: sys.modules.get(k) for k in ('sh4abi', 'toolpath', 'forwarded', 'frame_reads', 'layout', 'sdk_place')}
        for k in cls.saved_modules:
            sys.modules.pop(k, None)
        spec = importlib.util.spec_from_file_location('native_build_register_const',
                                                      os.path.join(cls.tmp, 'tools', '10-port', 'native_build.py'))
        cls.nb = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.nb)
        os.makedirs(cls.nb.OBJ, exist_ok=True)

    @classmethod
    def tearDownClass(cls):
        sys.path[:] = cls.saved_path
        os.environ.clear()
        os.environ.update(cls.saved_env)
        for k, v in cls.saved_modules.items():
            sys.modules.pop(k, None)
            if v is not None:
                sys.modules[k] = v
        shutil.rmtree(cls.tmp, True)

    def needs(self, name):
        """the names the compiled object of src/<name> leaves for the linker"""
        src = os.path.join(os.environ['PORT_SRC'], name)
        got, rc, err = self.nb.compile_one(src)
        self.assertEqual(rc, 0, err)
        out = subprocess.run(['nm', '-u', self.nb.obj_of(src)], capture_output=True, text=True, check=True).stdout
        return set(out.split())

    def test_variable(self):
        self.assertIn('port_mmio_w32', self.needs('variable.c'))

    def test_direct(self):
        self.assertIn('port_mmio_w32', self.needs('direct.c'))

    def test_ram(self):
        self.assertFalse([n for n in self.needs('ram.c') if n.startswith('port_mmio_')])


if __name__ == '__main__':
    unittest.main()
