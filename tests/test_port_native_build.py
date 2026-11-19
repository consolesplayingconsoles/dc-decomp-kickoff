#!/usr/bin/env python3
"""What the native build does to the game's C and IR before the host compiler sees them (scripts/tools/10-port/native_build.py).
No game data, no compiler: the text passes only, in a temp repo (the tool reads src/ and port/runtime/ when it is imported).
Stdlib only.

    mmio       which console addresses are hardware registers the port models: the system bus (0xA05F689C, the revision
               register a game reads at start-up) and the PowerVR (0xA05F8068) in any mirror, the SH-4 timers (0xFFD80008) and DMA
               controller (0xFFA00020), the AICA clock (0xA0710000); not RAM (0x8C010000), not the store queues (0xE0000000),
               not another P4 register
    ready      the sound driver's ready word (0xA080005C: the NAOMI library's nlsndInit reads it in a counted loop after it
               starts the sound CPU) is modelled too: the port answers the read once the sound CPU has had its time. The
               rest of sound RAM (0xA0800058, 0xA0800060) is plain memory
    high       an address above 2 GB inside a function body goes through port_k() (x86-64 would sign-extend it); a register
               address stays a constant, because the IR pass below finds registers by their constant; a line outside a body
               and a `case` label are left alone; an address below 2 GB is left alone
    load       a load from a constant register address in the IR becomes a call to port_mmio_r32, and the call is declared
    store      a store to one becomes a call to port_mmio_w32 with the value
    ram        a load from RAM stays a load
    field      `((struct oC_uint *)0xFFA00020)->v`: the IR holds the register as a base and a field offset (0xFFA00020 + 0xC);
               the two are folded into one address and the access becomes a call. Left unfolded, the game wrote plain
               memory at 0xFFA0002C and faulted
    args       an IR argument list splits at its top-level commas only
    globals    a data name the game's C uses is placed at its console address whether symbols.txt or globals.txt names it
               (colliKindTail, 0c26ec24 in globals.txt only: left out, it got storage of its own that the code clearing
               the list at its address never reached); symbols.txt wins where both name it
    name       the program is named after the repo's folder without -decomp (crazy-taxi-decomp: crazy-taxi), for its file,
               its window and its messages; nothing else in the repo (a .recomp.json saying another name) changes it
"""
import importlib.util
import os
import shutil
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
TOOLS = os.path.join(os.path.dirname(HERE), 'scripts', 'tools')


def s32(a):
    return a - (1 << 32) if a >> 31 else a


class NativeBuild(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp(prefix='native_build')
        os.makedirs(os.path.join(cls.tmp, 'src'))
        os.makedirs(os.path.join(cls.tmp, 'port', 'runtime'))
        with open(os.path.join(cls.tmp, 'src', 'a.c'), 'w') as fp:
            fp.write('int f(void) { return 0; }\n')
        os.makedirs(os.path.join(cls.tmp, 'tools'))
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
        spec = importlib.util.spec_from_file_location('native_build_under_test',
                                                      os.path.join(cls.tmp, 'tools', '10-port', 'native_build.py'))
        cls.nb = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.nb)

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

    def test_mmio(self):
        for a in (0xA05F689C, 0xA05F8068, 0x005F8068, 0xFFD80008, 0xFFA00020, 0xA0710000):
            self.assertTrue(self.nb.is_mmio(a), '%08X' % a)
        for a in (0x8C010000, 0x0C2B31C4, 0xE0000000, 0xFF000010, 0xA05F9000):
            self.assertFalse(self.nb.is_mmio(a), '%08X' % a)

    def test_globals(self):
        root = self.nb.ROOT
        with open(os.path.join(root, 'symbols.txt'), 'w') as f:
            f.write('# comment\n0C1799C8 gEventList\n0C26EBCC colliKindHead\n')
        with open(os.path.join(root, 'globals.txt'), 'w') as f:
            f.write('# comment\n0c26ec24 colliKindTail\n0c26ebcc colliKindHead\n0c000000 other\n')
        self.addCleanup(os.remove, os.path.join(root, 'symbols.txt'))
        self.addCleanup(os.remove, os.path.join(root, 'globals.txt'))
        syms = self.nb.read_symbols()
        self.assertEqual(syms['colliKindTail'], 0x0C26EC24)
        self.assertEqual(syms['gEventList'], 0x0C1799C8)
        self.assertEqual(syms['colliKindHead'], 0x0C26EBCC)

    def test_name(self):
        parent = tempfile.mkdtemp(prefix='name')
        self.addCleanup(shutil.rmtree, parent, True)
        d = os.path.join(parent, 'crazy-taxi-decomp')
        os.makedirs(d)
        with open(os.path.join(d, '.recomp.json'), 'w') as f:
            f.write('{"game": "Another Name"}')
        self.assertEqual(self.nb.program_name(d), ('crazy-taxi', 'crazy-taxi'))

    def test_ready(self):
        for a in (0xA080005C, 0x0080005C):
            self.assertTrue(self.nb.is_mmio(a), '%08X' % a)
        for a in (0xA0800058, 0xA0800060, 0xA0800000):
            self.assertFalse(self.nb.is_mmio(a), '%08X' % a)

    def test_high(self):
        """inside a function's body; a line outside one (a data table) is left alone"""
        def h(line):
            out = self.nb.high_literals('int f(int t1)\n{\n    int t0;\n' + line + '\n    return t0;\n}\n')
            return out.split('\n')[3]
        self.assertEqual(h('    t0 = *(int *)0x8C2B31C4;'), '    t0 = *(int *)port_k(0x8C2B31C4);')
        self.assertEqual(h('    *(unsigned int *)0xA05F8068 = t1;'), '    *(unsigned int *)0xA05F8068 = t1;')
        self.assertEqual(h('    case 0x80000000:'), '    case 0x80000000:')
        self.assertEqual(h('    t0 = *(int *)0x0C2B31C4;'), '    t0 = *(int *)0x0C2B31C4;')
        self.assertEqual(self.nb.high_literals('int table = 0x8C2B31C4;'), 'int table = 0x8C2B31C4;')

    def test_load(self):
        ir = '  %%3 = load volatile i32, ptr inttoptr (i32 %d to ptr), align 4\n' % s32(0xA05F689C)
        out = self.nb.mmio_calls(ir)
        self.assertIn('%%3 = call i32 @port_mmio_r32(i32 %d)' % s32(0xA05F689C), out)
        self.assertIn('declare i32 @port_mmio_r32(i32)', out)
        self.assertNotIn('load', out)

    def test_store(self):
        ir = '  store volatile i32 %%7, ptr inttoptr (i32 %d to ptr), align 4\n' % s32(0xA05F8068)
        out = self.nb.mmio_calls(ir)
        self.assertIn('  call void @port_mmio_w32(i32 %d, i32 %%7)' % s32(0xA05F8068), out)
        self.assertIn('declare void @port_mmio_w32(i32, i32)', out)

    def test_ram(self):
        ir = '  %%3 = load i32, ptr inttoptr (i32 %d to ptr), align 4\n' % s32(0x8C2B31C4)
        self.assertEqual(self.nb.mmio_calls(ir), ir)

    def test_field(self):
        ir = ('  store volatile i32 %%9, ptr getelementptr inbounds (%%struct.oC_uint, ptr inttoptr (i32 %d to ptr), i32 0, i32 1), align 4\n'
              % s32(0xFFA00020))
        out = self.nb.mmio_calls(ir)
        self.assertIn('call void @port_mmio_w32(i32 %d, i32 %%9)' % s32(0xFFA0002C), out)
        self.assertNotIn('getelementptr', out)

    def test_args(self):
        self.assertEqual(self.nb.split_args('i32 %1, ptr getelementptr (i8, ptr @g, i32 4), float %2'),
                         ['i32 %1', 'ptr getelementptr (i8, ptr @g, i32 4)', 'float %2'])


if __name__ == '__main__':
    unittest.main()
