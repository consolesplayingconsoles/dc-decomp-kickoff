#!/usr/bin/env python3
"""How the build from C decides that it fits (scripts/tools/8-build/fit.py), from a map and a log as the linker writes them; no
compiler, no game data. Stdlib only.

    check.py      a map with the sections the build links (PB1 in the fill block, PS, PB2 in the old game code, P3 the overflow):
                    sections   a section spans from its first row to the last row under it (rows with no name), empty rows left out
                    fits       PB1 and PB2 inside their places and no P3: fits, with the spare bytes
                    over       PB2 running past its end: does not fit, by how much
                    overflow   any byte in P3 (code that did not fit in place) is a failure, whatever the parts say
                    room       a part filled before an optimized link takes cap * plain / opt * margin plain bytes; no ratio: the cap
                    unreached  RELOCATION SIZE OVERFLOW lines (a short branch that no longer reaches) are found, once each
                    empty      a part with no code in the map fails (the optimizer crashed with PROGRAM ERROR(1704) and wrote a map
                               with no sections; the first fit check read the empty parts as spare and said the build fit, Crazy Taxi)
                    fatal      PROGRAM ERROR, ERROR: address space duplicate, CANNOT EXECUTE and (F) lines are found
                    perpart    room with one measured ratio per part (each part shrinks by its own)
                    firstpass  the optimizer's ** 1170 ADDRESS SPACE DUPLICATE is not fatal (its first, unoptimized pass overlaps
                               parts filled for the optimized sizes; Crazy Taxi fitted with it in the log), elf2bin's ERROR: is
                    overlaps   loadable ELF segments that share an address are found; side by side ones are not
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(HERE)), 'scripts', 'tools', '8-build'))
import fit  # noqa: E402

MAP = """SECTION NAME                         START    -     END        LENGTH
              UNIT NAME                        MODULE NAME

ATTRIBUTE  :   CODE  NOSHR

PB1                               H'0C011C28  -  H'0C011D27  H'00000100
              u001                             u001
                                  H'0C011D28  -  H'0C011E27  H'00000100
              u002                             u002
PS                                H'0C020000  -  H'0C02007F  H'00000080
              boot_stub                        boot_stub
PB2                               H'0C020080  -  H'0C0200FF  H'00000080
              u003                             u003
                                  H'0C020100  -  H'0C020100  H'00000000
              empty                            empty
"""
REG = {'PB1': (0x0C011C28, 0x0C020000), 'PB2': (0x0C020080, 0x0C020180)}


def main():
    bad = []
    s = fit.sections(MAP)
    if s.get('PB1') != (0x0C011C28, 0x0C011E28, 0x200) or s.get('PB2') != (0x0C020080, 0x0C020100, 0x80) or 'PS' not in s:
        bad.append('sections: %s' % s)
    ok, lines = fit.check(s, REG, ('P3',))
    if not ok or 'PB2: 128 bytes, 128 spare' not in lines:
        bad.append('fits: %s %s' % (ok, lines))
    ok, lines = fit.check(s, {'PB1': REG['PB1'], 'PB2': (0x0C020080, 0x0C0200C0)}, ('P3',))
    if ok or not any('64 bytes over' in x for x in lines):
        bad.append('over: %s %s' % (ok, lines))
    s3 = fit.sections(MAP + "P3                                H'0C5D0000  -  H'0C5D0013  H'00000014\n              u009                             u009\n")
    ok, lines = fit.check(s3, REG, ('P3',))
    if ok or not any('P3: 20 bytes' in x for x in lines):
        bad.append('overflow: %s %s' % (ok, lines))
    if fit.room([1000, 2000], 102, 100, 1.0) != [1020, 2040] or fit.room([1000], 102, 100, 0.99) != [1009] or fit.room([1000], 0, 0) != [1000]:
        bad.append('room: %s %s %s' % (fit.room([1000, 2000], 102, 100, 1.0), fit.room([1000], 102, 100, 0.99), fit.room([1000], 0, 0)))
    log = ('** 108 RELOCATION SIZE OVERFLOW(0c06b4f4_psgSetState.P - H\'00000018)\n'
           '** 108 RELOCATION SIZE OVERFLOW(0c06b4f4_psgSetState.P - H\'00000018)\n** 105 UNDEFINED EXTERNAL SYMBOL(_x)\n')
    if fit.unreached(log) != ["0c06b4f4_psgSetState.P - H'00000018"]:
        bad.append('unreached: %s' % fit.unreached(log))
    ok, lines = fit.check({'PB2': (0x0C020080, 0x0C020100, 0x80)}, REG, ('P3',))
    if ok or not any('PB1: no code' in x for x in lines):
        bad.append('empty: %s %s' % (ok, lines))
    flog = '** 3110 PROGRAM ERROR(1704)\nERROR: address space duplicate\n** 3740 CANNOT EXECUTE(OPTSH.EXE)\n** 2310 UNDEFINED(_x)\n'
    if len(fit.fatal(flog)) != 3:
        bad.append('fatal: %s' % fit.fatal(flog))
    if fit.room([1000, 2000], [1020, 2000], [1000, 2000], 1.0) != [1020, 2000]:
        bad.append('perpart: %s' % fit.room([1000, 2000], [1020, 2000], [1000, 2000], 1.0))
    if fit.fatal('** 1170 ADDRESS SPACE DUPLICATE\n** 0220 SAME_CODE OPTIMIZE:u188._com_opt1 IS CREATED\n'):
        bad.append('firstpass: %s' % fit.fatal('** 1170 ADDRESS SPACE DUPLICATE\n'))
    import tempfile
    sf = os.path.join(tempfile.mkdtemp(), 'sub', 'fit.json')
    if fit.load_ratios(sf) is not None:
        bad.append('seed: a file that is not there gave ratios')
    fit.save_ratios(sf, ([49920, 341324], [49366, 337278]))
    if fit.load_ratios(sf) != ([49920.0, 341324.0], [49366.0, 337278.0]):
        bad.append('seed: %s' % (fit.load_ratios(sf),))
    for junk in ('{', '{"plain": [1, 2]}', '{"plain": [1], "linked": [1, 2]}', '{"plain": [0, 2], "linked": [1, 2]}', '[]'):
        open(sf, 'w').write(junk)
        if fit.load_ratios(sf) is not None:
            bad.append('seed: unusable file read as ratios: %s' % junk)
    import struct

    def elf(segs):
        h = bytearray(0x34)
        h[:4] = b'\x7fELF'
        struct.pack_into('<I', h, 0x1C, 0x34)
        struct.pack_into('<HH', h, 0x2A, 32, len(segs))
        for va, n in segs:
            h += struct.pack('<8I', 1, 0, va, va, n, n, 5, 4)
        return bytes(h)
    if fit.overlaps(elf([(0x100, 0x100), (0x200, 0x10)])) or not fit.overlaps(elf([(0x100, 0x100), (0x1F0, 0x10)])):
        bad.append('overlaps: %s / %s' % (fit.overlaps(elf([(0x100, 0x100), (0x200, 0x10)])), fit.overlaps(elf([(0x100, 0x100), (0x1F0, 0x10)]))))
    if bad:
        sys.exit('[ERROR] fit check failed:\n' + '\n'.join(bad))
    print('[fit] ok: section extents from the map, parts inside their places, an overflow fails, room by the optimizer ratio, '
          'unreached short branches found, the measured ratios kept for the next build')


if __name__ == '__main__':
    main()
