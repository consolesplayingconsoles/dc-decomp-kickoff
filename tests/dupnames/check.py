#!/usr/bin/env python3
"""Names given to more than one function (scripts/tools/1-2-baseline/dupnames.py), on a synthetic functions.txt, no game data. Stdlib only.

    check.py      a temp repo where:
                    thunk     a 6-byte stub (mov.l @(pool),r3 / jmp @r3) carries the name of the function it jumps to: it becomes
                              thunk_<name> (Zombie Revenge kmiWriteRegister, Virtua Tennis mwRnaInit: one name for two functions, so a
                              call to either compiled as the other and twelve kmSet* functions did not compile)
                    copies    two bodies with one name (a library function linked twice): the second gets its address as a suffix
                    sameaddr  two entries at one address that both end before the next function are reported, not changed
                    overlap   of two entries at one address, the one running into the next function is dropped when the other ends
                              before it (Virtua Tennis sprSet266Free: 54 and 74 bytes, the next function 54 bytes on)
                    dryrun    without --apply nothing is written
                    cname     a name that is not a C identifier (a C++ signature: atcomResetBlackList(void),
                              send_message_in_current_mode(char*)) becomes the name up to its bracket, other characters as _, and its
                              address appended when that is taken (Virtua Tennis, Zombie Revenge: five functions no C could define)
                    source    src/ follows: a call to the name (or through a cast of it) in a function whose original calls one of
                              the copies goes to that copy's final name (Zombie Revenge: eleven kmSet* functions call the real
                              kmiWriteRegister, the C linked to its stub); a definition under the name keeps it, with its cases: the
                              first copy is renamed only when it is a stub, which runs into the body the C was written for (Virtua
                              Tennis mwRnaErrEntryFunc, proven at the stub's address)
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
        data = body + stub + copy2 + body + body + body
        open(os.path.join(tmp, '1ST_READ.BIN'), 'wb').write(data)
        open(os.path.join(tmp, 'BASE'), 'w').write('%08X\n' % BASE)
        lines = ['F %08x 8 writereg' % BASE, 'F %08x 6 writereg' % (BASE + 8), 'F %08x 8 libcopy' % (BASE + 20),
                 'F %08x 8 libcopy' % (BASE + 28), 'F %08x 4 twice' % BASE, 'F %08x 6 twice' % BASE,
                 'F %08x 8 over' % (BASE + 36), 'F %08x 12 over' % (BASE + 36), 'F %08x 8 nextfn' % (BASE + 44)]
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
        if [l for l in got if l.endswith(' over')] != ['F %08x 8 over' % (BASE + 36)]:
            bad.append('overlap: the entry running into the next function was not dropped: %s' % [l for l in got if l.endswith(' over')])
        if sum(1 for l in got if l.endswith(' twice')) != 2 or 'twice' not in dry:
            bad.append('sameaddr: two entries at one address were changed or not reported: %s / %s' % (got, dry))
        bad += source_case()
        bad += cname_case()
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    if bad:
        sys.exit('[ERROR] dupnames check failed:\n' + '\n'.join(bad))
    print('[dupnames] ok: a stub sharing its target\'s name becomes thunk_<name>, a second copy gets its address, two entries at one address are reported')


def source_case():
    """A stub first (the copy a name lookup finds), the body after it, one caller of each, a definition of the name, its cases."""
    bad = []
    tmp = tempfile.mkdtemp()
    try:
        shutil.copytree(os.path.join(SKILL, 'scripts', 'tools'), os.path.join(tmp, 'tools'), ignore=shutil.ignore_patterns('__pycache__'))
        stub, body, ca, cb = BASE, BASE + 12, BASE + 20, BASE + 40
        call = lambda tgt: words([0x4F22, 0xD103, 0x410B, 0x0009, 0x4F26, 0x000B, 0x0009, 0x0009]) + struct.pack('<I', tgt) + words([0x0009, 0x0009])
        data = (words([0xD301, 0x432B, 0x0009, 0x0009]) + struct.pack('<I', body)      # the stub: jumps to the body
                + words([0xE001, 0x000B, 0x0009, 0x0009])                           # the body
                + call(stub) + call(body))
        open(os.path.join(tmp, '1ST_READ.BIN'), 'wb').write(data)
        open(os.path.join(tmp, 'BASE'), 'w').write('%08X\n' % BASE)
        open(os.path.join(tmp, 'functions.txt'), 'w').write('F %08x 6 wr\nF %08x 8 wr\nF %08x 16 callA\nF %08x 16 callB\n' % (stub, body, ca, cb))
        os.makedirs(os.path.join(tmp, 'src')); os.makedirs(os.path.join(tmp, 'tests', 'gen_d'))
        open(os.path.join(tmp, 'src', 'gen_c.c'), 'w').write('int wr(int);\n\nint callA(void)\n{\n    return ((int (*)(int))(wr))(1);\n}\n\nint callB(void)\n{\n    return wr(2);\n}\n')
        open(os.path.join(tmp, 'src', 'gen_d.c'), 'w').write('int wr(int a4);\n\nint wr(int a4)\n{\n    return a4;\n}\n')
        open(os.path.join(tmp, 'tests', 'gen_d', 'wr.json'), 'w').write('{"dev": []}')
        open(os.path.join(tmp, 'tests', 'equivalent.txt'), 'w').write('callA\nwr\n')
        subprocess.run([sys.executable, 'tools/1-2-baseline/dupnames.py', '--apply'], cwd=tmp, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        c = open(os.path.join(tmp, 'src', 'gen_c.c')).read(); d = open(os.path.join(tmp, 'src', 'gen_d.c')).read()
        if 'return ((int (*)(int))(thunk_wr))(1);' not in c or 'return wr(2);' not in c:      # a call through a cast too (FUN_0c220360)
            bad.append('source: the callers do not call the copy their original calls:\n' + c)
        if 'int thunk_wr(int);' not in c:
            bad.append('source: no prototype for thunk_wr where it is now called:\n' + c)
        if 'int wr(int a4)\n{' not in d or not os.path.exists(os.path.join(tmp, 'tests', 'gen_d', 'wr.json')):
            bad.append('source: the definition of the body lost its name: %s %s' % (d, os.listdir(os.path.join(tmp, 'tests', 'gen_d'))))
        eq = open(os.path.join(tmp, 'tests', 'equivalent.txt')).read().split()
        if 'wr' not in eq or 'thunk_wr' in eq:
            bad.append('source: tests/equivalent.txt lost the body: %s' % eq)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    return bad


def cname_case():
    bad = []
    tmp = tempfile.mkdtemp()
    try:
        shutil.copytree(os.path.join(SKILL, 'scripts', 'tools'), os.path.join(tmp, 'tools'), ignore=shutil.ignore_patterns('__pycache__'))
        open(os.path.join(tmp, '1ST_READ.BIN'), 'wb').write(words([0xE001, 0x000B, 0x0009, 0x0009]) * 4)
        open(os.path.join(tmp, 'BASE'), 'w').write('%08X\n' % BASE)
        open(os.path.join(tmp, 'functions.txt'), 'w').write('F %08x 8 reset(void)\nF %08x 8 send_msg(char*)\nF %08x 8 taken(int)\nF %08x 8 taken\n'
                                                          % (BASE, BASE + 8, BASE + 16, BASE + 24))
        subprocess.run([sys.executable, 'tools/1-2-baseline/dupnames.py', '--apply'], cwd=tmp, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        got = open(os.path.join(tmp, 'functions.txt')).read().split()
        want = ['reset', 'send_msg', 'taken_%08x' % (BASE + 16), 'taken']
        names = got[3::4]
        if names != want:
            bad.append('cname: names %s, want %s' % (names, want))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    return bad


if __name__ == '__main__':
    main()
