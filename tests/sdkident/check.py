#!/usr/bin/env python3
"""The SDK library match (scripts/tools/1-2-baseline/sdk_identical.py) on a synthetic function, no game data. Stdlib only.

    check.py      a temp repo with one function and a fake SDK tree:
                    relaxed   a function that matches its library code only after the linker's changes (jsr @r1 in the library, bsrf r1
                              in the game, a different pool word) is found, though 450 other places in the libraries start with the same
                              8 bytes and the library is there in several identical copies: the search stopped after 400 candidates, so
                              the result depended on how many SDK directories were given (Virtua Tennis _calcnpw, sh4nlfzn.lib, lost
                              when both SDK trees were scanned)
                    aligned   an exact match in a library that follows an odd-sized file is found: the files were joined end to end and
                              only even positions searched, so its code sat on odd ones (Virtua Tennis: 34 libnlobj.elf functions, found
                              only while a second copy happened to land on an even position)
                    poolonly  a function whose only difference from its library code is a literal-pool word (an address the linker
                              filled in), with no call relaxed, is the library's code too (Zombie Revenge FUN_0c0ef250 and FUN_0c0efd04,
                              the SHC runtime's own code in sh4plfzz.elf, were left out because no call of theirs was relaxed)
                    deadpool  a pool word no reachable load reads, holding the game's address where a linked library copy holds its
                              own (Zombie Revenge syTmrGenMicroToCount, two left-over pool words with _divls and _modls), is the linker's too
                    oddmember a library archive does not align its members: code at an odd offset in the file is found too (Virtua
                              Tennis _quick_odd_mvn at 23471 in sh4plfzz.lib, lost once the files were aligned)
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

HEAD = [0xE005, 0xE106, 0xE207, 0xE308]                 # mov #5,r0 / #6,r1 / #7,r2 / #8,r3: the 8 bytes the search starts from
GAME = HEAD + [0xD102, 0x0103, 0x0009, 0x000B, 0x0009, 0x0009]      # mov.l @(pool),r1 / bsrf r1 / nop / rts / nop / nop
LIB = HEAD + [0xD102, 0x410B, 0x0009, 0x000B, 0x0009, 0x0009]       # the same with jsr @r1, before the linker relaxed it


def words(ws):
    return b''.join(struct.pack('<H', w) for w in ws)


def main():
    tmp = tempfile.mkdtemp()
    bad = []
    try:
        shutil.copytree(os.path.join(SKILL, 'scripts', 'tools'), os.path.join(tmp, 'tools'), ignore=shutil.ignore_patterns('__pycache__'))
        game = words(GAME) + struct.pack('<I', 0x8C012345)          # the pool word holds the linked address
        lib = words(LIB) + struct.pack('<I', 0)                     # unlinked in the library
        open(os.path.join(tmp, '1ST_READ.BIN'), 'wb').write(game)
        open(os.path.join(tmp, 'BASE'), 'w').write('%08X\n' % BASE)
        exact = words([0xE009, 0xE10A, 0xE20B, 0xE30C, 0xE40D, 0xE50E, 0xE60F, 0xE710, 0xE011, 0xE112, 0xE213, 0xE314, 0x000B, 0xE415])      # rts with a mov in its delay slot: no padding to trim
        odd = words([0xE021, 0xE122, 0xE223, 0xE324, 0xE425, 0xE526, 0xE627, 0xE728, 0xE029, 0xE12A, 0xE22B, 0xE32C, 0x000B, 0xE42D])
        pcode = [0xE031, 0xE132, 0xE233, 0xE334, 0xE435, 0xE536, 0xE637, 0xE738, 0xD102, 0x000B, 0xE43F, 0x0009, 0x0009, 0x0009]
        dcode = [0xE041, 0xE142, 0xE243, 0xE344, 0xE445, 0xE546, 0xA001, 0x0009]   # ... bra over the left-over pool word
        dgame = words(dcode) + struct.pack('<I', 0x8C0E5FE4) + words([0xE047, 0xE148, 0x000B, 0x0009])
        dlib = words(dcode) + struct.pack('<I', 0x8C0171DC) + words([0xE047, 0xE148, 0x000B, 0x0009])   # a linked sample's own address
        pgame = words(pcode) + struct.pack('<I', 0x8C054321)        # mov.l @(pool),r1 / rts: the pool word holds a linked address
        plib = words(pcode) + struct.pack('<I', 0)                  # the same code, the pool word unlinked
        open(os.path.join(tmp, '1ST_READ.BIN'), 'wb').write(game + exact + odd + pgame + dgame)
        p0 = BASE + len(game) + len(exact) + len(odd)
        open(os.path.join(tmp, 'functions.txt'), 'w').write('F %08x %d calcfn\nF %08x %d exactfn\nF %08x %d oddfn\nF %08x %d poolfn\n'
                                                            % (BASE, len(game), BASE + len(game), len(exact), BASE + len(game) + len(exact), len(odd),
                                                               p0, len(pgame)) + 'F %08x %d deadfn\n' % (p0 + len(pgame), len(dgame)))
        os.makedirs(os.path.join(tmp, 'sdk', 'a'))
        open(os.path.join(tmp, 'sdk', 'a', 'aaodd.lib'), 'wb').write(b'\xee' * 1001)      # an odd-sized file first
        os.makedirs(os.path.join(tmp, 'sdk', 'b'))
        open(os.path.join(tmp, 'sdk', 'b', 'shobj.elf'), 'wb').write(b'\xee' * 64 + exact + b'\xee' * 8)
        open(os.path.join(tmp, 'sdk', 'b', 'shcrt.lib'), 'wb').write(b'\xee' * 65 + odd + b'\xee' * 8)       # a member at an odd offset
        open(os.path.join(tmp, 'sdk', 'b', 'shrun.elf'), 'wb').write(b'\xee' * 40 + plib + b'\xee' * 8)
        open(os.path.join(tmp, 'sdk', 'b', 'sample.elf'), 'wb').write(b'\xee' * 20 + dlib + b'\xee' * 8)
        decoys = (words(HEAD) + b'\xee' * 16) * 450                 # other code that opens the same way
        for k in range(3):                                          # the same library in three SDK releases
            d = os.path.join(tmp, 'sdk', 'r%d' % k, 'lib')
            os.makedirs(d)
            open(os.path.join(d, 'shmath.lib'), 'wb').write(decoys + lib + b'\xee' * 32)
        r = subprocess.run([sys.executable, 'tools/1-2-baseline/sdk_identical.py', 'sdk'], cwd=tmp, stdout=subprocess.PIPE,
                           stderr=subprocess.STDOUT, universal_newlines=True)
        out = open(os.path.join(tmp, 'sdk-identical.txt')).read() if os.path.exists(os.path.join(tmp, 'sdk-identical.txt')) else ''
        line = [l for l in out.splitlines() if l.startswith('calcfn ')]
        ex = [l for l in out.splitlines() if l.startswith('exactfn ')]
        if not ex or 'shobj.elf' not in ex[0]:
            bad.append('aligned: exactfn not found in a library after an odd-sized file: %r' % ex)
        od = [l for l in out.splitlines() if l.startswith('oddfn ')]
        if not od or 'shcrt.lib 65' not in od[0]:
            bad.append('oddmember: oddfn at an odd offset of its library not found: %r' % od)
        po = [l for l in out.splitlines() if l.startswith('poolfn ')]
        if not po or 'shrun.elf 40' not in po[0]:
            bad.append('poolonly: poolfn, which differs from its library code only in a pool word, not found: %r' % po)
        de = [l for l in out.splitlines() if l.startswith('deadfn ')]
        if not de or 'sample.elf 20' not in de[0]:
            bad.append('deadpool: deadfn, whose left-over pool word holds another address in a linked copy, not found: %r' % de)
        if not line or not line[0].endswith('relaxed') or 'shmath.lib' not in line[0]:
            bad.append('relaxed: calcfn not found after the linker\'s relaxation behind 450 decoys: %r / %s' % (line, r.stdout.strip()[-200:]))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    if bad:
        sys.exit('[ERROR] sdkident check failed:\n' + '\n'.join(bad))
    print('[sdkident] ok: a function the linker relaxed is found in its library however many places start the same way')


if __name__ == '__main__':
    main()
