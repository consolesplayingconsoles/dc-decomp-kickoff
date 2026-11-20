#!/usr/bin/env python3
"""The disc's files into the folder the native game reads (scripts/tools/10-port/extract_disc.py). The disc is a stand-in
for tools/gdi_read.py's reader (its files and their bytes). No game data, no compiler. Stdlib only.

    extract     every file is written under the folder, subfolders kept, with its bytes
    version     an ISO 9660 version suffix (`;1`) is not part of the file's name
    kept        a file already there with the same size is not written again (an earlier extraction is reused)
"""
import contextlib
import importlib.util
import io
import os
import sys
import tempfile
import unittest
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))
TOOLS = os.path.join(os.path.dirname(HERE), 'scripts', 'tools')

FILES = {'/1ST_READ.BIN;1': b'\x01\x02\x03\x04', '/SOUND/MUSIC.ADX;1': b'ADX' * 5, '/COLDC1.BIN': b'\xff' * 7}


class FakeDisc:
    def __init__(self, gdi):
        self.lbas = {k: n for n, k in enumerate(sorted(FILES))}

    def files(self):
        return [(self.lbas[p], len(d), p) for p, d in FILES.items()]

    def read(self, lba, size):
        p = next(k for k, n in self.lbas.items() if n == lba)
        return FILES[p][:size]


def load():
    spec = importlib.util.spec_from_file_location('extract_disc_under_test', os.path.join(TOOLS, '10-port', 'extract_disc.py'))
    mod = importlib.util.module_from_spec(spec)
    saved = list(sys.path)
    try:
        spec.loader.exec_module(mod)
    finally:
        sys.path[:] = saved
    mod.Disc = FakeDisc
    return mod


class ExtractDisc(unittest.TestCase):
    def run_tool(self, out):
        mod = load()
        with mock.patch.object(sys, 'argv', ['extract_disc.py', 'disc.gdi', out]), contextlib.redirect_stdout(io.StringIO()):
            mod.main()

    def test_extract(self):
        with tempfile.TemporaryDirectory() as d:
            self.run_tool(d)
            with open(os.path.join(d, 'SOUND', 'MUSIC.ADX'), 'rb') as f:
                self.assertEqual(f.read(), b'ADX' * 5, 'a file in a subfolder, with its bytes')
            with open(os.path.join(d, 'COLDC1.BIN'), 'rb') as f:
                self.assertEqual(f.read(), b'\xff' * 7)

    def test_version(self):
        with tempfile.TemporaryDirectory() as d:
            self.run_tool(d)
            self.assertTrue(os.path.exists(os.path.join(d, '1ST_READ.BIN')), 'the name without ";1"')
            self.assertFalse(any(';' in n for n in os.listdir(d)), os.listdir(d))

    def test_kept(self):
        with tempfile.TemporaryDirectory() as d:
            with open(os.path.join(d, '1ST_READ.BIN'), 'wb') as f:
                f.write(b'MINE')                              # the same size as the disc's file
            self.run_tool(d)
            with open(os.path.join(d, '1ST_READ.BIN'), 'rb') as f:
                self.assertEqual(f.read(), b'MINE', 'a file of the same size is left as it is')


if __name__ == '__main__':
    unittest.main()
