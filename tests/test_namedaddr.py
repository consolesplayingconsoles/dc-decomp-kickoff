#!/usr/bin/env python3
"""cbuild.named_addresses() reads globals.txt and symbols.txt; a repo that has no symbols.txt yet is not an error. No game data.
Stdlib only."""
import os
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
TOOLS = os.path.join(os.path.dirname(HERE), 'scripts', 'tools')
sys.path[:0] = [TOOLS, os.path.join(TOOLS, '8-build')]
import toolpath  # noqa: E402,F401

# the tool reads the game's files from the current folder when it is imported: stand-ins in a temporary one
_cwd = os.getcwd()
_tmp = tempfile.TemporaryDirectory()
os.chdir(_tmp.name)
with open('1ST_READ.BIN', 'wb') as _f:
    _f.write(b'\x09\x00' * 64)
with open('BASE', 'w') as _f:
    _f.write('8C010000\n')
with open('functions.txt', 'w') as _f:
    _f.write('F 8c010000 128 stubfn\n')
with open('layout.txt', 'w') as _f:
    _f.write('game 8C010000 8C010080\n')
import cbuild  # noqa: E402
os.chdir(_cwd)


class Named(unittest.TestCase):
    def setUp(self):
        self.addCleanup(os.chdir, os.getcwd())
        d = tempfile.TemporaryDirectory()
        self.addCleanup(d.cleanup)
        os.chdir(d.name)
        with open('globals.txt', 'w') as f:
            f.write('# globals\n8c100000 gOne\n')

    def test_no_symbols_file(self):
        self.assertEqual(cbuild.named_addresses(), {'gOne': 0x8C100000})

    def test_both_files(self):
        with open('symbols.txt', 'w') as f:
            f.write('# <addr> <name>\n8c200000 gTwo\n')
        self.assertEqual(cbuild.named_addresses(), {'gOne': 0x8C100000, 'gTwo': 0x8C200000})


if __name__ == '__main__':
    unittest.main()
