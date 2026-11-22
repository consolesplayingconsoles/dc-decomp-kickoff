#!/usr/bin/env python3
"""The check compiles the file it was given, wherever it lives (scripts/tools/sim/equiv.py).
No game data, no compiler. Stdlib only.

    game      src/camera.c is handed to the compiler as src\\camera.c
    sdk       sdk/naomi/nlfoo.c is handed to it as sdk\\naomi\\nlfoo.c: the path was built as src\\<name>.c whatever folder the
              file was in, and a file under sdk/ failed with "Cannot open source file"
    given     a path with ./ in front, or absolute inside the repo, gives the same
    command   the compile command is built from that path, not from a fixed folder
"""
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
TOOLS = os.path.join(os.path.dirname(HERE), 'scripts', 'tools')
sys.path.insert(0, TOOLS)
import toolpath  # noqa: E402,F401  (every tools folder on the import path: sim/, common/, the steps)
import equiv  # noqa: E402


class EquivPath(unittest.TestCase):
    def test_game(self):
        self.assertEqual(equiv.compiler_path('src/camera.c'), 'src\\camera.c')

    def test_sdk(self):
        self.assertEqual(equiv.compiler_path('sdk/naomi/nlfoo.c'), 'sdk\\naomi\\nlfoo.c')

    def test_given(self):
        self.assertEqual(equiv.compiler_path('./sdk/naomi/nlfoo.c'), 'sdk\\naomi\\nlfoo.c')
        self.assertEqual(equiv.compiler_path(os.path.join(os.getcwd(), 'src', 'camera.c')), 'src\\camera.c')

    def test_command(self):
        with open(os.path.join(TOOLS, 'sim', 'equiv.py')) as fp:
            text = fp.read()
        self.assertNotIn('shc.exe" "src\\\\%s.c"', text)
        self.assertIn('compiler_path(cfile)', text)


if __name__ == '__main__':
    unittest.main()
