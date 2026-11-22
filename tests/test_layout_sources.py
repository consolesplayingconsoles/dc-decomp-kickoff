#!/usr/bin/env python3
"""Where a repo's C lives: the game's in src/, the SDK's in sdk/<library>/ (scripts/tools/common/layout.py).
No game data, no compiler. Stdlib only.

    flat       a repo with src/ only: its files, in name order; the SDK list is empty
    libraries  sdk/shinobi/fm.c and sdk/kamui/kmtex.c are C files too, listed after the game's, by folder then name;
               a file directly in sdk/ counts as well
    game       game_files() is src/ alone: what the console build compiles. It is the same list whether sdk/ is there or not
    lookup     a file is found by its name without `.c` wherever it lives: `fm` is sdk/shinobi/fm.c, `camera` is src/camera.c
    new        a name no folder has yet is a new game file: src/<name>.c
    cases      the cases of a file are in tests/<name>/ whatever folder the file is in, so moving a file moves no case
    library    sdk_library() names the library of a path under sdk/ and is None for a game file
    twice      the same file name in two folders is an error that names both: a name must say which file it is
    other      only .c files count; sdk/include/ and its headers are not sources
"""
import os
import shutil
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), 'scripts', 'tools'))
import toolpath  # noqa: E402,F401  (every tools folder on the import path: sim/, common/, the steps)
import layout  # noqa: E402


def put(path, text='int f(void) { return 0; }\n'):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w') as fp:
        fp.write(text)


class LayoutSources(unittest.TestCase):
    def setUp(self):
        self.repo = tempfile.mkdtemp(prefix='layout_sources')
        self.addCleanup(shutil.rmtree, self.repo, True)
        self.addCleanup(os.chdir, os.getcwd())
        os.chdir(self.repo)
        put('src/camera.c')
        put('src/gen_a.c')

    def sdk(self):
        put('sdk/shinobi/fm.c')
        put('sdk/kamui/kmtex.c')
        put('sdk/boot.c')
        put('sdk/include/kamui.h', '/* header */\n')

    def test_flat(self):
        self.assertEqual(layout.c_files(), ['src/camera.c', 'src/gen_a.c'])
        self.assertEqual(layout.sdk_files(), [])

    def test_libraries(self):
        self.sdk()
        self.assertEqual(layout.c_files(), ['src/camera.c', 'src/gen_a.c', 'sdk/boot.c', 'sdk/kamui/kmtex.c', 'sdk/shinobi/fm.c'])
        self.assertEqual(layout.sdk_files(), ['sdk/boot.c', 'sdk/kamui/kmtex.c', 'sdk/shinobi/fm.c'])

    def test_game(self):
        before = layout.game_files()
        self.sdk()
        self.assertEqual(layout.game_files(), before)
        self.assertEqual(before, ['src/camera.c', 'src/gen_a.c'])

    def test_lookup(self):
        self.sdk()
        self.assertEqual(layout.c_path('fm'), 'sdk/shinobi/fm.c')
        self.assertEqual(layout.c_path('camera'), 'src/camera.c')
        self.assertEqual(layout.c_path('boot'), 'sdk/boot.c')

    def test_new(self):
        self.sdk()
        self.assertEqual(layout.c_path('gen_zz'), 'src/gen_zz.c')

    def test_cases(self):
        self.sdk()
        self.assertEqual(layout.cases_dir('sdk/shinobi/fm.c'), 'tests/fm')
        self.assertEqual(layout.cases_dir('src/camera.c'), 'tests/camera')
        self.assertEqual(layout.stem('sdk/shinobi/fm.c'), 'fm')

    def test_library(self):
        self.sdk()
        self.assertEqual(layout.sdk_library('sdk/shinobi/fm.c'), 'shinobi')
        self.assertEqual(layout.sdk_library('sdk/boot.c'), '')
        self.assertIsNone(layout.sdk_library('src/camera.c'))

    def test_twice(self):
        self.sdk()
        put('sdk/shinobi/camera.c')
        with self.assertRaises(SystemExit) as e:
            layout.c_files()
        self.assertIn('src/camera.c', str(e.exception))
        self.assertIn('sdk/shinobi/camera.c', str(e.exception))

    def test_other(self):
        self.sdk()
        put('src/notes.txt', 'x')
        self.assertNotIn('sdk/include/kamui.h', layout.c_files())
        self.assertNotIn('src/notes.txt', layout.c_files())


if __name__ == '__main__':
    unittest.main()
