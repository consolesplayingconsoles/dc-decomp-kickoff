#!/usr/bin/env python3
"""The port build falls back to the SDK's own source for a function the repo has no C for, and leaves out hardware only
(scripts/tools/10-port/native_build.py). No game data, no compiler: the units' text, in a temp repo. Stdlib only.

    fallback   a function with no C in src/ or sdk/ that sdk-verified.txt lists gets a unit from its SDK source file: the
               file's includes, types, data and static helpers, with that function only
    ours       a function the repo has its own C for is not taken from the SDK source: our C is the one the build uses
    hardware   a function inside a `hardware` range of sdk.txt gets no unit: the host has no such hardware
    only       the functions left without a unit are reported with why: `missed()` is empty when hardware is all that is
               left out, and names a function whose source file was not found
    headers    a unit's header folders start with its own file's folder and its source tree's include folders, before the
               SDK's: another copy of <machine.h> first gave the file the wrong one
    tables     an address above 2 GB in a data table stays a constant (`{0xA05F6888, 0x80000000}`): wrapped in the helper
               the build puts around such addresses in code, the initializer was no longer constant
"""
import importlib.util
import os
import shutil
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
TOOLS = os.path.join(os.path.dirname(HERE), 'scripts', 'tools')

GDFS = '#include <shinobi.h>\n\nint gdFsRead(int a)\n{\n    return a;\n}\n'
RTC = ('#include <shinobi.h>\nstatic int rtc_base;\n\nstatic int rtc_read(void)\n{\n    return rtc_base;\n}\n\n'
       'int syRtcGet(int a)\n{\n    return rtc_read() + a;\n}\n\nint syRtcSet(int a)\n{\n    return a;\n}\n\nint syRtcOurs(int a)\n{\n    return a;\n}\n')


def leak(name, source, body):
    return '/* %s, from the SDK source you supplied: its own code */\n%s' % (source, body)


class LeakFallback(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix='leak_fallback')
        self.addCleanup(shutil.rmtree, self.tmp, True)
        files = {
            'functions.txt': 'F 0c160116 16 gdFsRead\nF 0c170000 16 syRtcGet\nF 0c170010 16 syRtcSet\nF 0c170020 16 syRtcOurs\nF 0c170030 16 syLost\n',
            'sdk-verified.txt': '# verified\ngdFsRead\nsyRtcGet\nsyRtcSet\nsyRtcOurs\nsyLost\n',
            'sdk.txt': 'range 0c14ab88 0c1789b0 SDK libraries\nhardware 0c15fc8e 0c1605ca GD-ROM file system\n',
            'sdk-source/gdFsRead.c': leak('gdFsRead', 'GDFS.C', 'int gdFsRead(int a)\n{\n    return a;\n}\n'),
            'sdk-source/syRtcGet.c': leak('syRtcGet', 'RTC.C', 'int syRtcGet(int a)\n{\n    return rtc_read() + a;\n}\n'),
            'sdk-source/syRtcSet.c': leak('syRtcSet', 'RTC.C', 'int syRtcSet(int a)\n{\n    return a;\n}\n'),
            'sdk-source/syRtcOurs.c': leak('syRtcOurs', 'RTC.C', 'int syRtcOurs(int a)\n{\n    return a;\n}\n'),
            'sdk-source/syLost.c': leak('syLost', 'GONE.C', 'int syLost(void)\n{\n    return 0;\n}\n'),
            'build/sdk-source/work/t0/shinobi/GDFS.C': GDFS,
            'build/sdk-source/work/t0/shinobi/RTC.C': RTC,
            'build/sdk-source/work/t0/include/shinobi.h': '/* the tree\'s own */\n',
            'build/sdk-source/work/sdkinc0/shinobi.h': '/* the SDK\'s */\n',
            'src/a.c': 'int f(void) { return 0; }\n',
            'sdk/shinobi/ours.c': 'int syRtcOurs(int a)\n{\n    return a + 0;\n}\n',
        }
        for name, text in files.items():
            path = os.path.join(self.tmp, name)
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, 'w') as fp:
                fp.write(text)
        os.makedirs(os.path.join(self.tmp, 'port', 'runtime'))
        os.makedirs(os.path.join(self.tmp, 'tools'))
        for f in ('toolpath.py', 'layout.py'):
            shutil.copy(os.path.join(TOOLS, f), os.path.join(self.tmp, 'tools'))
        for d in ('10-port', '5-generated'):
            shutil.copytree(os.path.join(TOOLS, d), os.path.join(self.tmp, 'tools', d), ignore=shutil.ignore_patterns('__pycache__', 'gen_equiv'))
        saved_path, saved_env = list(sys.path), dict(os.environ)
        saved = {k: sys.modules.get(k) for k in ('sh4abi', 'toolpath', 'forwarded', 'frame_reads', 'layout', 'sdk_place')}

        def restore():
            sys.path[:] = saved_path
            os.environ.clear()
            os.environ.update(saved_env)
            for k, v in saved.items():
                sys.modules.pop(k, None)
                if v is not None:
                    sys.modules[k] = v
        self.addCleanup(restore)
        for k in saved:
            sys.modules.pop(k, None)
        spec = importlib.util.spec_from_file_location('native_build_leak_fallback',
                                                      os.path.join(self.tmp, 'tools', '10-port', 'native_build.py'))
        self.nb = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.nb)
        self.units = self.nb.sdk_source_units(self.tmp)
        self.text = '\n'.join(u[0] for u in self.units.values())

    def test_fallback(self):
        self.assertIn('int syRtcGet(int a)\n{', self.text)
        self.assertIn('int syRtcSet(int a)\n{', self.text)
        self.assertIn('static int rtc_read(void)\n{', self.text)
        self.assertIn('static int rtc_base;', self.text)

    def test_ours(self):
        self.assertNotIn('int syRtcOurs(int a)\n{', self.text)

    def test_hardware(self):
        self.assertNotIn('int gdFsRead(int a)\n{', self.text)

    def test_only(self):
        self.assertEqual(self.nb.sdk_source_missed(self.tmp), [('syLost', 'its source file GONE.C was not found')])

    def test_headers(self):
        dirs = [os.path.relpath(d, self.tmp) for d in list(self.units.values())[0][1]]
        self.assertEqual(dirs[0], os.path.join('build', 'sdk-source', 'work', 't0', 'shinobi'))
        self.assertLess(dirs.index(os.path.join('build', 'sdk-source', 'work', 't0', 'include')),
                        dirs.index(os.path.join('build', 'sdk-source', 'work', 'sdkinc0')))

    def test_tables(self):
        src = ('static const unsigned int table[2][2] = {\n    {0xA05F6888, 0x80000000},\n    {0x8C000000, 0},\n};\n\n'
               'int f(void)\n{\n    return *(int *)0x8C2B31C4;\n}\n')
        out = self.nb.high_literals(src)
        self.assertIn('    {0xA05F6888, 0x80000000},', out)
        self.assertIn('    {0x8C000000, 0},', out)
        self.assertIn('    return *(int *)port_k(0x8C2B31C4);', out)


    def test_macro(self):
        """macro: an address above 2 GB named through a macro (`#define LIBTBL (*(void **)0x8C00FFF0)`) is used inside a
        function, where the compiler would sign-extend it: the macro's body is wrapped too. Left as it was, ovInit faulted at
        0xFFFFFFFF8C00FFF0 (Crazy Taxi). A hardware register in a macro stays a constant, as in code"""
        src = ('#define LIBTBL          (*(void **)0x8C00FFF0)\n#define TCR2 (*(volatile unsigned short *)0xFFD80028)\n\n'
               'void ovInit(void *t)\n{\n    LIBTBL = t;\n}\n')
        out = self.nb.high_literals(src)
        self.assertIn('#define LIBTBL          (*(void **)port_k(0x8C00FFF0))', out)
        self.assertIn('#define TCR2 (*(volatile unsigned short *)0xFFD80028)', out)


if __name__ == '__main__':
    unittest.main()
