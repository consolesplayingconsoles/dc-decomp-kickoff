#!/usr/bin/env python3
"""The SDK's C in its library's folder: sdk/<library>/, out of the game's src/ (scripts/tools/5-generated/sdk_place.py).
No game data, no compiler. Stdlib only.

    list       without --fix the plan is printed and nothing changes
    whole      a file that holds one library only moves as it is: src/gen_b.c (two nl functions) is sdk/naomi/gen_b.c;
               its cases stay in tests/gen_b/
    split      a file that holds the game's code and two libraries is split by function: the game's function stays in
               src/gen_a.c, the nl function goes to sdk/naomi/gen_a_naomi.c and the km function to sdk/kamui/gen_a_kamui.c,
               each with the file's declarations and structures
    cases      a split function's cases follow it: tests/gen_a/nlFoo.json is tests/gen_a_naomi/nlFoo.json
    record     docs/equivalent.md names the new file and the new cases for each function that moved
    neighbour  a function whose name says no library (search_fat, between two vmsfs functions) goes with the library linked
               around it
    runtime    a compiler helper (_divls) in a library block is the runtime's
    game       a file of game functions is not touched, and the game's part of a split file keeps its name
    built      a library function inside the part of the image the console build compiles (layout.txt's game region, outside
               keep) stays in src/: the console build needs it there
    unit       a matching unit (`/* @unit ...`) is never touched
    start      the start code's _INITSCT is Shinobi's although it is the first function of its block, before any Kamui name
    helper     a helper whose name only looks like the C library's (memcpy2, between two ADX functions) goes with the
               library around it; memcpy itself is the runtime's
    names      afterwards every C file's name is still unique across the folders (tools/layout.py)
"""
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
TOOLS = os.path.join(os.path.dirname(HERE), 'scripts', 'tools')
TOOL = os.path.join(TOOLS, '5-generated', 'sdk_place.py')
sys.path.insert(0, TOOLS)
import layout  # noqa: E402

FUNCS = '''F 0c020100 20 gameThing
F 0c020200 20 gameOther
F 0c030000 8 nlBuiltWithGame
F 0c073a00 16 nlFoo
F 0c073a20 16 nlBar
F 0c073a40 16 nlBaz
F 0c073a60 12 _divls
F 0c14ab98 16 _INITSCT
F 0c14ac00 16 kmSetThing
F 0c160000 16 vmsfs_open
F 0c160020 16 search_fat
F 0c160040 16 vmsfs_close
F 0c162e00 8 vmsRead
F 0c171400 16 ADXB_Decode
F 0c171560 16 memcpy2
F 0c171580 16 ADXB_Copy
F 0c1715a0 16 memcpy
'''
SDK = 'range 0c0739c0 0c089f26 NAOMI library and the C runtime\nrange 0c14ab88 0c1789b0 SDK libraries\nfunc 0c030000 nlBuiltWithGame\n'
LAYOUT = 'game 0C020080 0C14AB88\nkeep 0C0739C0 0C14AB88\n'
GEN_A = '''struct o4_int { char p[0x4]; int v; };
int gameThing(int a4);
int nlFoo(int a4);
int kmSetThing(int a4);

int gameThing(int a4)
{
    return nlFoo(a4) + 1;
}

int nlFoo(int a4)
{
    return (((struct o4_int *)a4)->v);
}

int kmSetThing(int a4)
{
    return a4 + 2;
}
'''
GEN_B = 'int nlBar(int a4);\nint nlBaz(int a4);\n\nint nlBar(int a4)\n{\n    return a4;\n}\n\nint nlBaz(int a4)\n{\n    return nlBar(a4);\n}\n'
GEN_C = ('int vmsfs_open(int a4)\n{\n    return 1;\n}\n\nint search_fat(int a4)\n{\n    return 2;\n}\n\n'
         'int vmsfs_close(int a4)\n{\n    return 3;\n}\n\nint _divls(int a4)\n{\n    return 4;\n}\n')
GEN_D = ('int _INITSCT(void)\n{\n    return 0;\n}\n\nint ADXB_Decode(int a4)\n{\n    return 1;\n}\n\nint memcpy2(int a4)\n{\n    return 2;\n}\n\n'
         'int ADXB_Copy(int a4)\n{\n    return 3;\n}\n\nint memcpy(int a4)\n{\n    return 4;\n}\n')
GAME = 'int gameOther(int a4)\n{\n    return a4;\n}\n\nint nlBuiltWithGame(int a4)\n{\n    return 9;\n}\n'
UNIT = '/* @unit 0C162E00-0C163098 */\nint vmsRead(int a4)\n{\n    return a4;\n}\n'
DOC = '''# Equivalent functions

### gameThing (`0C020100`, 20 bytes, `src/gen_a.c`)
- equivalent on 2 development cases, in `tests/gen_a/gameThing.json`

### nlFoo (`0C073A00`, 16 bytes, `src/gen_a.c`)
- equivalent on 2 development cases, in `tests/gen_a/nlFoo.json`

### nlBar (`0C073A20`, 16 bytes, `src/gen_b.c`)
- equivalent on 2 development cases, in `tests/gen_b/nlBar.json`
'''


def put(path, text):
    os.makedirs(os.path.dirname(path) or '.', exist_ok=True)
    with open(path, 'w') as fp:
        fp.write(text)


def get(path):
    with open(path) as fp:
        return fp.read()


class SdkPlace(unittest.TestCase):
    def setUp(self):
        self.repo = tempfile.mkdtemp(prefix='sdk_place')
        self.addCleanup(shutil.rmtree, self.repo, True)
        self.addCleanup(os.chdir, os.getcwd())
        os.chdir(self.repo)
        put('functions.txt', FUNCS)
        put('sdk.txt', SDK)
        put('layout.txt', LAYOUT)
        put('src/gen_a.c', GEN_A)
        put('src/gen_b.c', GEN_B)
        put('src/gen_c.c', GEN_C)
        put('src/gen_d.c', GEN_D)
        put('src/game_x.c', GAME)
        put('src/unit_v.c', UNIT)
        for stem, names in (('gen_a', ('gameThing', 'nlFoo', 'kmSetThing')), ('gen_b', ('nlBar', 'nlBaz')),
                            ('gen_c', ('vmsfs_open', 'search_fat', 'vmsfs_close', '_divls')), ('game_x', ('gameOther', 'nlBuiltWithGame'))):
            for n in names:
                put('tests/%s/%s.json' % (stem, n), '[]')
        put('docs/equivalent.md', DOC)

    def run_tool(self, *args):
        return subprocess.run([sys.executable, TOOL] + list(args), cwd=self.repo, capture_output=True, text=True)

    def fix(self):
        r = self.run_tool('--fix')
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        return r

    def test_list(self):
        before = {p: get(p) for p in ('src/gen_a.c', 'src/gen_b.c', 'docs/equivalent.md')}
        r = self.run_tool()
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn('gen_b', r.stdout)
        self.assertIn('sdk/naomi', r.stdout)
        for p, t in before.items():
            self.assertEqual(get(p), t, p)
        self.assertFalse(os.path.exists('sdk'))

    def test_whole(self):
        self.fix()
        self.assertFalse(os.path.exists('src/gen_b.c'))
        self.assertEqual(get('sdk/naomi/gen_b.c'), GEN_B)
        self.assertTrue(os.path.exists('tests/gen_b/nlBar.json'))

    def test_split(self):
        self.fix()
        game = get('src/gen_a.c')
        self.assertIn('int gameThing(int a4)\n{', game)
        self.assertNotIn('int nlFoo(int a4)\n{', game)
        self.assertNotIn('int kmSetThing(int a4)\n{', game)
        self.assertIn('int nlFoo(int a4);', game)                       # the declaration its caller needs
        naomi = get('sdk/naomi/gen_a_naomi.c')
        self.assertIn('int nlFoo(int a4)\n{\n    return (((struct o4_int *)a4)->v);\n}', naomi)
        self.assertIn('struct o4_int { char p[0x4]; int v; };', naomi)
        self.assertNotIn('gameThing(int a4)\n{', naomi)
        self.assertNotIn('kmSetThing(int a4)\n{', naomi)
        kamui = get('sdk/kamui/gen_a_kamui.c')
        self.assertIn('int kmSetThing(int a4)\n{\n    return a4 + 2;\n}', kamui)

    def test_cases(self):
        self.fix()
        self.assertTrue(os.path.exists('tests/gen_a_naomi/nlFoo.json'))
        self.assertFalse(os.path.exists('tests/gen_a/nlFoo.json'))
        self.assertTrue(os.path.exists('tests/gen_a_kamui/kmSetThing.json'))
        self.assertTrue(os.path.exists('tests/gen_a/gameThing.json'))

    def test_record(self):
        self.fix()
        d = get('docs/equivalent.md')
        self.assertIn('### nlFoo (`0C073A00`, 16 bytes, `sdk/naomi/gen_a_naomi.c`)', d)
        self.assertIn('in `tests/gen_a_naomi/nlFoo.json`', d)
        self.assertIn('### nlBar (`0C073A20`, 16 bytes, `sdk/naomi/gen_b.c`)', d)
        self.assertIn('in `tests/gen_b/nlBar.json`', d)
        self.assertIn('### gameThing (`0C020100`, 20 bytes, `src/gen_a.c`)', d)

    def test_neighbour(self):
        self.fix()
        self.assertIn('int search_fat(int a4)', get('sdk/shinobi/gen_c_shinobi.c'))
        self.assertIn('int vmsfs_open(int a4)', get('sdk/shinobi/gen_c_shinobi.c'))

    def test_runtime(self):
        self.fix()
        self.assertIn('int _divls(int a4)', get('sdk/runtime/gen_c_runtime.c'))
        self.assertFalse(os.path.exists('src/gen_c.c'))               # nothing of the game's was in it

    def test_game(self):
        self.fix()
        self.assertEqual(get('src/game_x.c'), GAME)

    def test_built(self):
        self.fix()
        self.assertIn('int nlBuiltWithGame(int a4)', get('src/game_x.c'))

    def test_unit(self):
        self.fix()
        self.assertEqual(get('src/unit_v.c'), UNIT)

    def test_start(self):
        self.fix()
        self.assertIn('int _INITSCT(void)', get('sdk/shinobi/gen_d_shinobi.c'))

    def test_helper(self):
        self.fix()
        self.assertIn('int memcpy2(int a4)', get('sdk/sofdec/gen_d_sofdec.c'))
        self.assertIn('int memcpy(int a4)', get('sdk/runtime/gen_d_runtime.c'))
        self.assertNotIn('int memcpy2(int a4)', get('sdk/runtime/gen_d_runtime.c'))

    def test_names(self):
        self.fix()
        files = layout.c_files()
        self.assertEqual(len(files), len({layout.stem(f) for f in files}))
        self.assertIn('sdk/kamui/gen_a_kamui.c', files)


if __name__ == '__main__':
    unittest.main()
