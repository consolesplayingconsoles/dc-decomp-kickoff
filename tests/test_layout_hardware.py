#!/usr/bin/env python3
"""The SDK code that drives hardware a host does not have: sdk.txt's `hardware` lines (scripts/tools/layout.py).
No game data, no compiler. Stdlib only.

    lines      `hardware <start> <end> <what>` in sdk.txt gives a range and what it is: the Maple bus driver, the GD-ROM file
               system, the memory card's file system. `range` and `func` lines are not hardware
    inside     an address inside a range is hardware; its end is not, and an address outside is not
    mirror     a game linked at 8C lists the range in 8C and is asked in either mirror
    none       a repo with no sdk.txt, or none of these lines, has no hardware: nothing changes for it
    comment    a comment line and a trailing comment are not part of the range
"""
import os
import shutil
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), 'scripts', 'tools'))
import layout  # noqa: E402

SDK = '''# Katana SDK code
range 0c14ab88 0c1789b0 SDK libraries
func 0c075f70 nlRand
hardware 0c161864 0c1629d0 Maple bus driver (kd*, mpdrv*)
hardware 8c15fc8e 8c1605ca GD-ROM file system    # gdFs*
'''


class LayoutHardware(unittest.TestCase):
    def setUp(self):
        self.repo = tempfile.mkdtemp(prefix='layout_hardware')
        self.addCleanup(shutil.rmtree, self.repo, True)
        self.addCleanup(os.chdir, os.getcwd())
        os.chdir(self.repo)

    def sdk(self, text=SDK):
        with open('sdk.txt', 'w') as fp:
            fp.write(text)

    def test_lines(self):
        self.sdk()
        self.assertEqual(layout.hardware(), [(0x0C15FC8E, 0x0C1605CA, 'GD-ROM file system'),
                                             (0x0C161864, 0x0C1629D0, 'Maple bus driver (kd*, mpdrv*)')])

    def test_inside(self):
        self.sdk()
        self.assertEqual(layout.is_hardware(0x0C161864), 'Maple bus driver (kd*, mpdrv*)')
        self.assertTrue(layout.is_hardware(0x0C1629CE))
        self.assertFalse(layout.is_hardware(0x0C1629D0))
        self.assertFalse(layout.is_hardware(0x0C14AB88))

    def test_mirror(self):
        self.sdk()
        self.assertTrue(layout.is_hardware(0x8C160000))
        self.assertTrue(layout.is_hardware(0x0C160000))

    def test_none(self):
        self.assertEqual(layout.hardware(), [])
        self.assertFalse(layout.is_hardware(0x0C161864))
        self.sdk('range 0c14ab88 0c1789b0 SDK libraries\n')
        self.assertEqual(layout.hardware(), [])

    def test_comment(self):
        self.sdk('# hardware 0c000000 0c000010 not this\nhardware 0c161864 0c1629d0 Maple   # the pad\n')
        self.assertEqual(layout.hardware(), [(0x0C161864, 0x0C1629D0, 'Maple')])


if __name__ == '__main__':
    unittest.main()
