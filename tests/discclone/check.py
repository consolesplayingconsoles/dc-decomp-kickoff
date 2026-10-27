#!/usr/bin/env python3
"""A track file copied for the new disc (scripts/tools/8-build/disc_patch.py copy_track): on macOS an APFS clone, else a byte copy; either
way an independent file, because the patch then writes into it. No game data. Stdlib only.

    check.py      a temp folder where:
                    copy      the destination holds the same bytes as the source
                    apart     writing into the destination leaves the source as it was (a clone copies on write)
                    fallback  with another platform named the bytes are copied and the answer says so
                    across    a destination that cannot be cloned into (a folder that is not there) is an error, not a half file
"""
import os
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(HERE)), 'scripts', 'tools', '8-build'))
import disc_patch as D  # noqa: E402

fails = []


def check(name, ok):
    print('%-8s %s' % (name, 'ok' if ok else 'FAIL'))
    if not ok:
        fails.append(name)


with tempfile.TemporaryDirectory() as t:
    src = os.path.join(t, 'track03.bin')
    data = bytes(range(256)) * 4096
    open(src, 'wb').write(data)
    dst = os.path.join(t, 'copy.bin')
    how = D.copy_track(src, dst)
    check('copy', open(dst, 'rb').read() == data and how in ('cloned', 'copied'))
    with open(dst, 'r+b') as f:
        f.seek(100)
        f.write(b'PATCH')
    check('apart', open(src, 'rb').read() == data and open(dst, 'rb').read() != data)
    real = sys.platform
    try:
        sys.platform = 'linux'
        dst2 = os.path.join(t, 'copy2.bin')
        check('fallback', D.copy_track(src, dst2) == 'copied' and open(dst2, 'rb').read() == data)
    finally:
        sys.platform = real
    try:
        D.copy_track(src, os.path.join(t, 'nowhere', 'x.bin'))
        check('across', False)
    except OSError:
        check('across', True)
sys.exit(1 if fails else 0)
