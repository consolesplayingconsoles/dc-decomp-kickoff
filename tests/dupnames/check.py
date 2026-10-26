#!/usr/bin/env python3
"""Names given to more than one function (scripts/tools/1-2-baseline/dupnames.py), on a synthetic functions.txt, no game data. Stdlib only.

    check.py      a temp repo where:
                    thunk     a 6-byte stub (mov.l @(pool),r3 / jmp @r3) carries the name of the function it jumps to: it becomes
                              thunk_<name> (Zombie Revenge kmiWriteRegister, Virtua Tennis mwRnaInit: one name for two functions, so a
                              call to either compiled as the other and twelve kmSet* functions did not compile)
                    copies    two bodies with one name (a library function linked twice): the second gets its address as a suffix
                    sameaddr  two entries at one address are reported, not changed (which size is right needs a decision)
                    dryrun    without --apply nothing is written
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


def words(ws):
    return b''.join(struct.pack('<H', w) for w in ws)


def main():
    tmp = tempfile.mkdtemp()
    bad = []
    try:
        shutil.copytree(os.path.join(SKILL, 'scripts', 'tools'), os.path.join(tmp, 'tools'), ignore=shutil.ignore_patterns('__pycache__'))
        body = words([0xE001, 0x000B, 0x0009, 0x0009])                  # mov #1,r0 / rts / nop
        stub = words([0xD301, 0x432B, 0x0009, 0x0009]) + struct.pack('<I', BASE)      # mov.l @(pool),r3 / jmp @r3 / nop, pool -> body
        copy2 = body
        data = body + stub + copy2 + body
        open(os.path.join(tmp, '1ST_READ.BIN'), 'wb').write(data)
        open(os.path.join(tmp, 'BASE'), 'w').write('%08X\n' % BASE)
        lines = ['F %08x 8 writereg' % BASE, 'F %08x 6 writereg' % (BASE + 8), 'F %08x 8 libcopy' % (BASE + 20),
                 'F %08x 8 libcopy' % (BASE + 28), 'F %08x 4 twice' % BASE, 'F %08x 6 twice' % BASE]
        open(os.path.join(tmp, 'functions.txt'), 'w').write('\n'.join(lines) + '\n')
        run = lambda *a: subprocess.run([sys.executable, 'tools/1-2-baseline/dupnames.py'] + list(a), cwd=tmp, stdout=subprocess.PIPE,
                                        stderr=subprocess.STDOUT, universal_newlines=True).stdout
        dry = run()
        if open(os.path.join(tmp, 'functions.txt')).read() != '\n'.join(lines) + '\n':
            bad.append('dryrun: functions.txt changed without --apply')
        out = run('--apply')
        got = open(os.path.join(tmp, 'functions.txt')).read().split('\n')
        if 'F %08x 6 thunk_writereg' % (BASE + 8) not in got or 'F %08x 8 writereg' % BASE not in got:
            bad.append('thunk: the stub is not thunk_writereg, or the body lost its name: %s' % got)
        if 'F %08x 8 libcopy' % (BASE + 20) not in got or 'F %08x 8 libcopy_%08x' % (BASE + 28, BASE + 28) not in got:
            bad.append('copies: the second body is not libcopy_<address>: %s' % got)
        if sum(1 for l in got if l.endswith(' twice')) != 2 or 'twice' not in dry:
            bad.append('sameaddr: two entries at one address were changed or not reported: %s / %s' % (got, dry))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    if bad:
        sys.exit('[ERROR] dupnames check failed:\n' + '\n'.join(bad))
    print('[dupnames] ok: a stub sharing its target\'s name becomes thunk_<name>, a second copy gets its address, two entries at one address are reported')


if __name__ == '__main__':
    main()
