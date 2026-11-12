#!/usr/bin/env python3
"""The SDK is not C in an equivalent project, and is delivered in a matching one (scripts/tools/progress.py; ZR, 2026-11-11: the library
functions that are never built from C kept the game short of 100%). No game data, no compiler. Stdlib only.

    check.py      a temp repo with four functions of 8 bytes: two with proven C, one listed in sdk.txt, one in sdk-verified.txt
                    equivalent   only the SDK function proven to be the SDK's (sdk-verified.txt, sdk-identical.txt) is out of the count; one
                                 merely listed in sdk.txt is not done: 1 left of 3 (ZR, 2026-11-11: two functions listed by hand hid behind 100%)
                    proven       an SDK function that also has proven C stays in the count (it is built): 3 functions, 0 left
                    matching     MODE: matching, nothing else proven: the SDK source counts as done, 3 of the 4 functions are left
"""
import os
import re
import shutil
import struct
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
SKILL = os.path.dirname(os.path.dirname(HERE))
BASE = 0x8C010000
CODE = struct.pack('<16H', *([0x000B, 0x0009] * 8))
NAMES = ['alpha', 'beta', 'sdk_listed', 'sdk_verified']


def report(tmp, proven, mode='equivalent'):
    w = lambda p, t: open(os.path.join(tmp, p), 'w').write(t)
    w('functions.txt', ''.join('F %08x 8 %s\n' % (BASE + 8 * i, n) for i, n in enumerate(NAMES)))
    w('tests/equivalent.txt', ''.join(n + '\n' for n in proven))
    w('sdk.txt', 'func %08x sdk_listed\n' % (BASE + 16))
    w('sdk-verified.txt', '# verified\nsdk_verified\n')
    w('status.txt', 'MODE: %s\n' % mode)
    r = subprocess.run([sys.executable, 'tools/progress.py'], cwd=tmp, capture_output=True, text=True)
    return r.stdout + r.stderr


def left(out):
    m = re.search(r'FUNCTIONS LEFT\s+\(\s*([\d.]+)% complete\)\s+(\d+)\s+of the (\d+) functions', out)
    return (float(m.group(1)), int(m.group(2)), int(m.group(3))) if m else None


def main():
    bad = []
    tmp = tempfile.mkdtemp()
    try:
        shutil.copytree(os.path.join(SKILL, 'scripts', 'tools'), os.path.join(tmp, 'tools'), ignore=shutil.ignore_patterns('__pycache__'))
        open(os.path.join(tmp, '1ST_READ.BIN'), 'wb').write(CODE)
        open(os.path.join(tmp, 'BASE'), 'w').write('%08X\n' % BASE)
        os.makedirs(os.path.join(tmp, 'tests'))
        os.makedirs(os.path.join(tmp, 'src'))
        out = report(tmp, ['alpha', 'beta'])
        if not left(out) or left(out)[1:] != (1, 3):
            bad.append('equivalent: %r, want 1 left of 3: only a proven SDK function is out of the count, a listed one is not done\n%s' % (left(out), out[-600:]))
        out = report(tmp, ['alpha', 'beta', 'sdk_listed'])
        if left(out) != (100.0, 0, 3):
            bad.append('proven: %r, want (100.0, 0, 3): a proven SDK function stays in the count\n%s' % (left(out), out[-600:]))
        out = report(tmp, [], 'matching')
        if left(out) != (25.0, 3, 4):
            bad.append('matching: %r: the SDK source is delivered, so it is done work there\n%s' % (left(out), out[-600:]))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    if bad:
        print('[progress_sdk] FAIL\n' + '\n'.join(bad))
        sys.exit(1)
    print('[progress_sdk] ok: the SDK is out of the 100% in equivalent mode and done work in matching mode')


main()
