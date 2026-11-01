#!/usr/bin/env python3
"""sdk_identical.py keeps what an earlier run found (scripts/tools/1-2-baseline/sdk_identical.py). Stdlib only, no game data.

Each run wrote sdk-identical.txt from scratch, so a run given other SDK directories than the one before dropped the functions only
those found: Virtua Tennis lost _quick_evn_mvn, _quick_odd_mvn, _slow_strcpy and setjmp (sh4plfzz.lib, sh4nlfzz.lib) when it was run on
the NAOMI and r10.1 trees only (2026-10-31), and they went back to "not done". A line stays while its function is still in
functions.txt and not proven by C; a function proven by C since then is dropped from the list (it is done either way).

    check.py      a temp repo with three functions and an SDK tree that holds only the first one's bytes; sdk-identical.txt already lists
                  the other two from an earlier run:
                    found    the first is found in this run's library
                    kept     the second, still open, keeps its earlier line
                    proven   the third, in tests/equivalent.txt now, is not kept
"""
import os
import shutil
import struct
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
SKILL = os.path.dirname(os.path.dirname(HERE))
BASE = 0x8C010000
W = lambda ws: b''.join(struct.pack('<H', w) for w in ws)

ONE = W([0xE031, 0xE132, 0xE233, 0xE334, 0xE435, 0xE536, 0xE637, 0xE738, 0xE039, 0xE13A, 0xE23B, 0xE33C, 0x000B, 0xE43D])
TWO = W([0xE041, 0xE142, 0xE243, 0xE344, 0xE445, 0xE546, 0xE647, 0xE748, 0xE049, 0xE14A, 0xE24B, 0xE34C, 0x000B, 0xE44D])
THREE = W([0xE051, 0xE152, 0xE253, 0xE354, 0xE455, 0xE556, 0xE657, 0xE758, 0xE059, 0xE15A, 0xE25B, 0xE35C, 0x000B, 0xE45D])


def main():
    bad = []
    tmp = tempfile.mkdtemp()
    try:
        shutil.copytree(os.path.join(SKILL, 'scripts', 'tools'), os.path.join(tmp, 'tools'), ignore=shutil.ignore_patterns('__pycache__'))
        open(os.path.join(tmp, '1ST_READ.BIN'), 'wb').write(ONE + TWO + THREE)
        open(os.path.join(tmp, 'BASE'), 'w').write('%08X\n' % BASE)
        n = len(ONE)
        open(os.path.join(tmp, 'functions.txt'), 'w').write('F %08x %d onefn\nF %08x %d twofn\nF %08x %d threefn\n'
                                                            % (BASE, n, BASE + n, n, BASE + 2 * n, n))
        os.makedirs(os.path.join(tmp, 'tests'))
        open(os.path.join(tmp, 'tests', 'equivalent.txt'), 'w').write('threefn\n')
        open(os.path.join(tmp, 'sdk-identical.txt'), 'w').write('# header\ntwofn %d other.lib 100\nthreefn %d other.lib 200\n' % (n, n))
        os.makedirs(os.path.join(tmp, 'sdk'))
        open(os.path.join(tmp, 'sdk', 'this.lib'), 'wb').write(b'\xee' * 32 + ONE + b'\xee' * 8)
        r = subprocess.run([sys.executable, 'tools/1-2-baseline/sdk_identical.py', 'sdk'], cwd=tmp, stdout=subprocess.PIPE,
                           stderr=subprocess.STDOUT, universal_newlines=True)
        names = [l.split()[0] for l in open(os.path.join(tmp, 'sdk-identical.txt')).read().splitlines()[1:] if l.strip()]
        if 'onefn' not in names:
            bad.append('found: onefn not found in this run (%s)' % r.stdout.strip()[-200:])
        if 'twofn' not in names:
            bad.append('kept: twofn, found by an earlier run and still open, was dropped: %r' % names)
        if 'threefn' in names:
            bad.append('proven: threefn is proven by C now but kept: %r' % names)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    if bad:
        sys.exit('[ERROR] sdkident_keep check failed:\n' + '\n'.join(bad))
    print('[sdkident_keep] ok: a run keeps the open functions an earlier run found in other SDK directories')


if __name__ == '__main__':
    main()
