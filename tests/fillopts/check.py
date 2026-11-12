#!/usr/bin/env python3
"""fill.py lays out shc's asm output like the game. Every option beyond the default layout (the `+` options of an @unit header: +pool32,
+pool00, +synth16, ...) is opt-in: a unit that asks for none gets the same bytes as before the options existed, in every game. This is
the guard for that, on a synthetic unit (what shc writes for one function and its literal pool). No game data, no compiler. Stdlib only.

    check.py      fill.py on a small unit, byte counts taken from the output text:
                    default   no option: .ALIGN becomes 0x0009 nops, a .RES gap 0xEE, the tail up to the unit's end 0xEE; the output is
                              exactly the text below (the layout every Equivalent and earlier Matching unit was built with)
                    size      every output, with or without options, adds up to end - start
                    seeds     the same output under three hash seeds (.EXPORT/.IMPORT lines were once ordered by a set)
                    pool00    +pool00: the gap between a pool's 16-bit and 32-bit entries is zero bytes, a .RES elsewhere stays 0xEE
                    pool32    +pool32: the pool starts on a 32-byte boundary, the padding is the word 0x0900, ALIGN pads too
                    synth16   +synth16: mov.w of 0x0100 from the pool becomes mov #1 / shll8, the word leaves the pool, other loads follow
                    isolated  an option changes nothing for a unit that does not ask for it: the default output after the options ran
                              is still the text below
"""
import os
import re
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
FILL = os.path.join(os.path.dirname(os.path.dirname(HERE)), 'scripts', 'tools', '1-2-baseline', 'fill.py')

UNIT = """          .IMPORT     _x
          .EXPORT     _f
          .SECTION    P,CODE,ALIGN=16
_f:                              ; function: f
          MOV.W       L1,R1
          MOV.L       L1+4,R2    ; _x
          RTS
          MOV         R1,R0
          .ALIGN      16
L1:
          .DATA.W     H'0100
          .RES.W      1
          .DATA.L     _x
          .END
"""

DEFAULT = """          .IMPORT     _x
          .EXPORT     _f
          .SECTION    P,CODE,ALIGN=2
_f:                              ; function: f
          MOV.W       L1,R1
          MOV.L       L1+4,R2    ; _x
          RTS
          MOV         R1,R0
          .DATA.W     H'0009
          .DATA.W     H'0009
          .DATA.W     H'0009
          .DATA.W     H'0009
L1:
          .DATA.W     H'0100
          .DATAB.B    2,H'EE
          .DATA.L     _x
          .DATAB.B    8,H'EE
          .END
"""

# a .RES that is not inside a pool (after code): 0xEE with every option
RES_ELSEWHERE = UNIT.replace("          RTS\n          MOV         R1,R0\n",
                             "          RTS\n          MOV         R1,R0\n          .RES.W      1\n")

# code, a C section with three labels the code's pool points at (what shc writes for tables): the order of the cross-piece
# .IMPORT/.EXPORT lines must not depend on the hash seed
TWO_PIECES = """          .IMPORT     _a
          .EXPORT     _g
          .SECTION    P,CODE,ALIGN=4
_g:                              ; function: g
          MOV.L       L9,R1      ; T3
          MOV.L       L9+4,R2    ; T1
          MOV.L       L9+8,R3    ; T2
          RTS
          MOV.L       @R1,R0
L9:
          .RES.W      1
          .DATA.L     T3
          .DATA.L     T1
          .DATA.L     T2
          .SECTION    C,DATA,ALIGN=4
T1:
          .DATA.L     _a,_a
T2:
          .DATA.L     _a
T3:
          .DATA.L     _a,_a,_a
          .END
"""


def run(text, start, end, opts=(), data=None, seed='0'):
    d = tempfile.mkdtemp()
    src, out, outd = os.path.join(d, 'u.s'), os.path.join(d, 'o.s'), os.path.join(d, 'od.s')
    open(src, 'w').write(text)
    args = [sys.executable, '-I', FILL, src, out, '%08X' % start, '%08X' % end]
    if data:
        args += [outd, '%08X' % data[0], '%08X' % data[1], 'u']
    r = subprocess.run(args + list(opts), capture_output=True, text=True, env=dict(os.environ, PYTHONHASHSEED=seed))
    if r.returncode:
        return None, r.stderr.strip()
    return open(out).read() + (('\n--- data\n' + open(outd).read()) if data else ''), ''


def size(text):
    """Bytes a laid-out piece occupies, counted from its lines (instructions are 2 bytes)."""
    n = 0
    for line in text.splitlines():
        code = line.split(';', 1)[0].strip()
        code = re.sub(r'^\S+:\s*', '', code)
        if not code or code.startswith('---'):
            continue
        op, _, args = code.partition(' ')
        op = op.upper()
        args = args.strip()
        if op in ('.IMPORT', '.EXPORT', '.SECTION', '.END', '.ALIGN'):
            continue
        if op.startswith('.DATA.W'):
            n += 2 * len(args.split(','))
        elif op.startswith('.DATA.L'):
            n += 4 * len(args.split(','))
        elif op.startswith('.DATA.B'):
            n += len(args.split(','))
        elif op.startswith('.DATAB.B'):
            n += int(args.split(',')[0], 0)
        elif op.startswith('.RES'):
            n += int(args, 0) * {'B': 1, 'W': 2, 'L': 4}[op[-1]]
        elif not op.startswith('.'):
            n += 2
    return n


def main():
    bad = []
    S = 0x0C074270

    got, err = run(UNIT, S, S + 0x20)
    if got != DEFAULT:
        bad.append('default: the no-option output changed:\n' + (err or got))
    if got and size(got) != 0x20:
        bad.append('size: default is %d bytes, not 32' % size(got))

    for name, opts, end in (('pool00', ['--pool00'], 0x20), ('pool32', ['--pool32'], 0x40), ('synth16', ['--synth16'], 0x20)):
        out, err = run(UNIT, S, S + end, opts)
        if out is None:
            bad.append('%s: fill.py stopped: %s' % (name, err))
            continue
        if size(out) != end:
            bad.append('size: %s output is %d bytes, not %d' % (name, size(out), end))
        if name == 'pool00':
            if "DATAB.B    2,H'00" not in out or "DATAB.B    8,H'EE" not in out:
                bad.append('pool00: the pool gap should be H\'00 and the tail H\'EE:\n' + out)
            out2, _ = run(RES_ELSEWHERE, S, S + 0x22, ['--pool00'])
            if out2 is None or "DATAB.B    2,H'EE" not in out2.split('L1:')[0]:
                bad.append('pool00: a .RES outside a pool must stay H\'EE')
        if name == 'pool32':
            lab = out.split('L1:')[0]
            if "H'0900" not in lab:
                bad.append('pool32: the padding before the pool should be the word 0x0900:\n' + out)
            before = size(lab)
            if (S + before) % 32:
                bad.append('pool32: the pool starts at %08X, not on a 32-byte boundary' % (S + before))
        if name == 'synth16':
            if 'MOV         #1,R1' not in out or 'SHLL8       R1' not in out:
                bad.append('synth16: mov.w of 0x0100 should become mov #1 / shll8:\n' + out)
            if "H'0100" in out:
                bad.append('synth16: the word 0x0100 should leave the pool')
            if 'MOV.L       L1,R2' not in out:
                bad.append('synth16: the long load should move to the pool start (L1):\n' + out)

    # hash seeds: a unit with code and a C section
    outs = []
    for seed in ('1', '2', '3'):
        o, err = run(TWO_PIECES, 0x0C000000, 0x0C000040, data=(0x0C100000, 0x0C100030), seed=seed)
        outs.append(o if o is not None else err)
    if len(set(outs)) != 1:
        bad.append('seeds: the output depends on the hash seed (%d different outputs for 3 seeds)' % len(set(outs)))

    # nothing leaks between runs: the default again, after the options
    again, _ = run(UNIT, S, S + 0x20)
    if again != DEFAULT:
        bad.append('isolated: the default output differs after options ran')

    if bad:
        sys.exit('[ERROR] fillopts check failed:\n' + '\n'.join(bad))
    print('[fillopts] ok: no-option output is the original layout, every option keeps the unit size, output is the same under any hash seed')


if __name__ == '__main__':
    main()
