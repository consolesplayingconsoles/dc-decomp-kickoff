#!/usr/bin/env python3
"""toolpath.py puts every tools folder on the import path, so a tool imports another by name wherever it lives.

The folders are the step folders (tools/<n>-<step>/), the simulator's (tools/sim/: sh4sim, equiv, shdis), the shared
tools' (tools/common/) and the generator's package. A folder left off the list breaks every import of its tools at once.
Runs toolpath in a child Python so this process's import path is not touched.
"""
import os
import subprocess
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
TOOLS = os.path.join(os.path.dirname(HERE), 'scripts', 'tools')


def paths_after_toolpath():
    code = 'import sys; sys.path.insert(0, %r); import toolpath; print("\\n".join(sys.path))' % TOOLS
    out = subprocess.run([sys.executable, '-c', code], stdout=subprocess.PIPE, universal_newlines=True, check=True).stdout
    return [os.path.normpath(p) for p in out.splitlines()]


class ToolpathTest(unittest.TestCase):
    def setUp(self):
        self.paths = paths_after_toolpath()

    def test_the_simulator_folder_is_on_the_path(self):
        self.assertIn(os.path.join(TOOLS, 'sim'), self.paths)

    def test_the_shared_tools_folder_is_on_the_path(self):
        self.assertIn(os.path.join(TOOLS, 'common'), self.paths)

    def test_every_step_folder_is_on_the_path(self):
        steps = [d for d in os.listdir(TOOLS) if d[:1].isdigit() and os.path.isdir(os.path.join(TOOLS, d))]
        self.assertTrue(steps)
        for d in steps:
            self.assertIn(os.path.join(TOOLS, d), self.paths, d)

    def test_the_kickoff_setup_folder_is_not_on_the_path(self):
        # it is not copied into repos: a repo tool that imported from it would break there
        self.assertNotIn(os.path.join(TOOLS, '1-2-baseline', 'setup'), self.paths)


if __name__ == '__main__':
    unittest.main()
