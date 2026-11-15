"""overlay_scan.py: classify every file of an extracted disc and prove whether it holds SH-4 code
(scripts/tools/1-2-baseline/overlay_scan.py). No game data: the files are built here from a few bytes. Stdlib only.

The main CPU's code lives in 1ST_READ.BIN; a file elsewhere holds SH-4 code only if it has the function prologue and epilogue
any compiled function has. The sound CPU's executable is ARM, told by its branch vector table or its push-and-call pattern.

    sh4      a prologue and an epilogue, the epilogues not outnumbering the prologues eightfold: SH-4 code
    ratio    many epilogues and a single prologue: data that happens to contain the bytes
    arm      eight branch words ending in 0xEA, or more than 32 push words: ARM code
    magic    DTPK and GBIX headers, an .ADX name: sound bank, texture, audio
    other    anything else, whatever its name says: data
    output   a line per file, SH-4 first and the biggest first; --md prints a table; a count per type closes the list
"""
import os
import struct
import subprocess
import sys
import tempfile
import unittest

SKILL = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOOL = os.path.join(SKILL, 'scripts', 'tools', '1-2-baseline', 'overlay_scan.py')

PRO = b'\xe6\x2f\x22\x4f'
EPI = b'\x26\x4f\x0b\x00\x09\x00'
PAD = b'\x00' * 8


class TestOverlayScan(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)

    def put(self, name, data):
        with open(os.path.join(self.tmp.name, name), 'wb') as f:
            f.write(data)

    def scan(self, *flags):
        done = subprocess.run([sys.executable, TOOL, self.tmp.name] + list(flags), stdout=subprocess.PIPE,
                              stderr=subprocess.PIPE, universal_newlines=True)
        self.assertEqual(done.returncode, 0, done.stderr)
        return done.stdout

    def kind_of(self, name):
        for line in self.scan().split('\n'):
            if line.startswith(name):
                return line[len(name):].strip()
        self.fail('no line for %s' % name)

    def test_prologue_and_epilogue_make_sh4_code(self):
        self.put('OVL.BIN', PAD + PRO + PAD + EPI + PAD)
        self.assertTrue(self.kind_of('OVL.BIN').startswith('SH-4 code'))

    def test_many_epilogues_and_one_prologue_is_data(self):
        self.put('X.BIN', PRO + PAD + (EPI + PAD) * 9)
        self.assertTrue(self.kind_of('X.BIN').startswith('data'))

    def test_a_prologue_alone_is_data(self):
        self.put('X.BIN', PAD + PRO + PAD)
        self.assertTrue(self.kind_of('X.BIN').startswith('data'))

    def test_a_branch_vector_table_is_arm_code(self):
        self.put('SND.BIN', b''.join(struct.pack('<I', 0xEA000000 | i) for i in range(16)))
        self.assertTrue(self.kind_of('SND.BIN').startswith('ARM code'))

    def test_many_push_words_are_arm_code(self):
        self.put('SND.BIN', struct.pack('<I', 0xE92D8000) * 40 + b'\x00' * 64)
        self.assertTrue(self.kind_of('SND.BIN').startswith('ARM code'))

    def test_magic_numbers_and_the_adx_name(self):
        self.put('A.BIN', b'DTPK' + PAD)
        self.put('B.BIN', b'GBIX' + PAD)
        self.put('C.ADX', PAD * 8)
        self.assertTrue(self.kind_of('A.BIN').startswith('DTPK sound bank'))
        self.assertTrue(self.kind_of('B.BIN').startswith('PVR texture'))
        self.assertTrue(self.kind_of('C.ADX').startswith('CRI ADX audio'))

    def test_a_name_says_nothing_about_the_content(self):
        self.put('NAMED_HIT.BIN', PAD * 8)
        self.put('NAMED.MDL', PAD * 8)
        self.assertTrue(self.kind_of('NAMED_HIT.BIN').startswith('data'))
        self.assertTrue(self.kind_of('NAMED.MDL').startswith('data'))

    def test_sh4_code_is_listed_first_and_the_types_are_counted(self):
        self.put('BIG.DAT', PAD * 100)
        self.put('OVL.BIN', PAD + PRO + PAD + EPI + PAD)
        lines = [l for l in self.scan().split('\n') if l.strip()]
        self.assertTrue(lines[0].startswith('OVL.BIN'))
        self.assertIn('SH-4 code', lines[-2])
        self.assertIn('data', lines[-1])

    def test_md_prints_a_table(self):
        self.put('OVL.BIN', PAD + PRO + PAD + EPI + PAD)
        out = self.scan('--md')
        self.assertIn('| file | size | type | SH-4 prologues | SH-4 epilogues |', out)
        self.assertIn('| `OVL.BIN` |', out)

    def test_only_files_directly_in_the_folder_are_read(self):
        os.makedirs(os.path.join(self.tmp.name, 'SUB'))
        self.put('OVL.BIN', PAD)
        self.assertNotIn('SUB', self.scan())


if __name__ == '__main__':
    unittest.main()
