#!/usr/bin/env python3
"""The arity scan's cache follows the scanner's code (scripts/tools/5-generated/gen_equiv/gen_core.py, state/arity_scan.json). No game
data, no compiler. Stdlib only.

What the scan counts for each function is kept in state/arity_scan.json across runs. The cache was dropped only when a version number
written by hand changed, so entries scanned by an older scanner stayed: 11 of the 51 callees checked on one game were wrong (four
arguments for a function that reads none), every caller passed registers it never set, the draw threw out every case and the caller was
skipped, "the original does not finish on the cases". The cache now also carries a hash of the scanner's source and is read again when
that changes.

    check.py      a temp repo with a function that reads r4 and r5 before writing them, and a cached entry of four arguments for it:
                    stale     the cache written by another scanner (no hash, or another one): the function is scanned again, two arguments
                    current   the cache written by this scanner: the cached four are used (the cache still works)
"""
import unittest
import json
import os
import shutil
import struct
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
SKILL = os.path.dirname(HERE)
BASE = 0x0C010000
READS_R4_R5 = [0x6043, 0x305C, 0x000B, 0x0009]          # mov r4,r0; add r5,r0; rts; nop
SCRIPT = ("import sys; sys.path.insert(0, 'tools'); sys.path.insert(0, 'tools/5-generated/gen_equiv'); import toolpath, gen_core\n"
          "print('ARITY', gen_core.callee_arity('f'))\n"
          "print('KEY', getattr(gen_core, '_SCAN_KEY', None))\n")


class TestArityScanCache(unittest.TestCase):
    def repo(self):
        tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, tmp, True)
        shutil.copytree(os.path.join(SKILL, 'scripts', 'tools'), os.path.join(tmp, 'tools'), ignore=shutil.ignore_patterns('__pycache__'))
        open(os.path.join(tmp, '1ST_READ.BIN'), 'wb').write(b''.join(struct.pack('<H', w) for w in READS_R4_R5))
        open(os.path.join(tmp, 'BASE'), 'w').write('%08X\n' % BASE)
        open(os.path.join(tmp, 'functions.txt'), 'w').write('F 0c010000 8 f\n')
        os.makedirs(os.path.join(tmp, 'src'))
        os.makedirs(os.path.join(tmp, 'state'))
        return tmp

    def run_in(self, tmp):
        out = subprocess.run([sys.executable, '-c', SCRIPT], cwd=tmp, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                             universal_newlines=True).stdout
        got = {l.split(None, 1)[0]: l.split(None, 1)[1] for l in out.splitlines() if l.startswith(('ARITY', 'KEY'))}
        return got, out

    def test_arityscan_cache(self):
        bad = []
        tmp = self.repo()
        got, out = self.run_in(tmp)                                   # a first scan, to learn the version and the key
        ver = json.load(open(os.path.join(tmp, 'state', 'arity_scan.json')))['__scan']
        for what, cache in (('stale (no hash)', {'__scan': ver, 'f': [4, 0]}),
                            ('stale (another hash)', {'__scan': ver, '__code': 'another', 'f': [4, 0]})):
            json.dump(cache, open(os.path.join(tmp, 'state', 'arity_scan.json'), 'w'))
            got, out = self.run_in(tmp)
            if got.get('ARITY') != '(2, 0)':
                bad.append('stale: with a cache %s the function was not scanned again: %s' % (what, got.get('ARITY', out[-300:])))
        key = got.get('KEY')
        json.dump({'__scan': ver, '__code': key, 'f': [4, 0]}, open(os.path.join(tmp, 'state', 'arity_scan.json'), 'w'))
        got, out = self.run_in(tmp)
        if got.get('ARITY') != '(4, 0)':
            bad.append('current: a cache written by this scanner was not used: %s' % got.get('ARITY', out[-300:]))
        if bad:
            self.fail('[ERROR] arityscan cache check failed:\n' + '\n'.join(bad))


if __name__ == '__main__':
    unittest.main()
