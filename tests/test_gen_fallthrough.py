#!/usr/bin/env python3
"""A body the original reaches from two places is written once (scripts/tools/5-generated/gen_equiv/gen_core.py). No game data, no
compiler. Stdlib only.

A state function often runs an init for state 0 and then FALLS INTO the body of state 1, which state 1 jumps to directly, and every
other state skips both and meets them at the function's common end:

        switch (state) { case 0: init; /* falls through */ case 1: body; break; default: break; }  end;

The arms of the first compare meet only at `end`, not at the body, so the generator wrote the body once per arm (Power Stone 2: the
phase-1 body twice in FUN_0c153a4c, 491 lines, 9,024 of its 13,964 bytes; the same in eight more functions, each hand version of
which writes the body once).

    check.py      a function `state==0: init; state==1: body; other: skip; end` (the arms of the first compare meet at `end`):
                    once      the body's statement is written once, not once per arm
                    init      the init is written once, and only on the path that has it
                    end       the code after the common end is written once
                    apart     a second function whose state-1 body differs from the one state 0 falls into is written with both bodies
                    state     the init sets a register the body reads: the body is still written once, a variable carries the register
                    tworet    another state returns by itself, so the arms end at separate returns (no common end): still once
                    nofall    a third whose state 0 does not fall into the body (it ends with its own return) keeps the body once

The same body is also reached the other way round and through longer chains of compares, and a join that several arms reach (and
that another arm skips) is no different: a node entered from two places that is not where every path meets. Each is written once:
the paths into it set a flag (and what they leave different), and its code follows the branch under a test of the flag.

    mirrored      the compare is `bf`: the fall-through arm is the init, the taken arm holds the test that jumps to the body
    chain         state 0's init falls into the body state 2 jumps to; state 1, tested in between, has a body of its own
    mid           state 1's init falls into state 2's body in the middle of the chain; state 0, before them, has its own body
    steps         state 0 falls into state 1's body, which falls into state 2's body: each of the three written once
    apart2        mirrored, but the tested state has a different body from the one the init falls into: both are written
    nofall2       a chain where every state ends with its own jump to the end: each body once, as before
    join          states 0 and 1 each run their own code and meet at a body that state 2 skips: the body is written once
    nested        an if / else whose arms meet at a body that one inner path skips: once
    carried       the arms that meet at the body leave a register it reads different: once, a variable carries the value
    ladder        three tests that each jump to the same fail code or go on to the same pass code: each written once
    past          a path leaves an inner if for the body; the code after that inner if's own join is not run on it (it stands in the
                  else of that path, not after the if)
    tail          as join, but the body has no branch in it: it stays at the end of each arm (the compiler writes one copy of
                  such a tail, and a flag would cost more than nothing)
    switch        a jump table: two cases meet at a body the third case skips: the body is written once
"""
import unittest
import os
import re
import shutil
import struct
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
SKILL = os.path.dirname(HERE)
BASE = 0x0C010000
W = lambda ws: b''.join(struct.pack('<H', w) for w in ws)

# mov.b @(12,r4),r0 / cmp/eq #0,r0 / bt S0 / cmp/eq #1,r0 / bt S1 / bra END / nop
HEAD = [0x844C, 0x8800, 0x8903, 0x8801, 0x8903, 0xA005, 0x0009]
INIT = [0xE101, 0x1411]                           # S0: mov #1,r1 / mov.l r1,@(4,r4)
BODY = [0x5241, 0x7203, 0x1422]                   # S1: mov.l @(4,r4),r2 / add #3,r2 / mov.l r2,@(8,r4)
END = [0xE309, 0x1434, 0x000B, 0x0009]            # END: mov #9,r3 / mov.l r3,@(16,r4) / rts / nop

FALL = HEAD + INIT + BODY + END
# state 1 does not run the body state 0 falls into: its own body adds 5, state 0 runs init then the add-3 body, both then meet at END
APART = [0x844C, 0x8800, 0x8903, 0x8801, 0x8908, 0xA00A, 0x0009,        # head: bt S0 / bt S1 / bra END
         0xE101, 0x1411, 0x5241, 0x7203, 0x1422, 0xA003, 0x0009,        # S0: init, add-3 body, bra END / nop
         0x5241, 0x7205, 0x1422,                                         # S1: add-5 body
         0xE309, 0x1434, 0x000B, 0x0009]                                 # END
# state 0 ends with its own return after the init: it never reaches the body
NOFALL = [0x844C, 0x8800, 0x8903, 0x8801, 0x8905, 0xA007, 0x0009,       # head: bt S0 / bt S1 / bra END
          0xE101, 0x1411, 0x000B, 0x0009,                               # S0: init, rts / nop
          0x5241, 0x7203, 0x1422,                                       # S1: the body
          0xE309, 0x1434, 0x000B, 0x0009]                               # END

# the init changes a register the body reads: mov.l @r4,r1 first; state 0 sets r1 to 7, state 1 keeps the loaded one, then the body stores r1
STATE = [0x6142, 0x844C, 0x8800, 0x8903, 0x8801, 0x8902, 0xA002, 0x0009,    # r1 = @r4 / state / bt S0 / bt S1 / bra END
         0xE107,                                                            # S0: mov #7,r1 (falls into S1)
         0x1412,                                                            # S1: mov.l r1,@(8,r4)
         0xE309, 0x1434, 0x000B, 0x0009]                                    # END

# a third state returns on its own, so the arms of the first compare end at separate returns and no node is on every path
TWORET = [0x844C, 0x8800, 0x8907, 0x8801, 0x8907, 0x8802, 0x8901, 0xA007, 0x0009,   # bt S0 / bt S1 / cmp/eq #2 / bt R2 / bra END
          0x000B, 0x0009,                                                           # R2: rts / nop
          0xE101, 0x1411, 0x5241, 0x7203, 0x1422,                                   # S0: init (falls into S1) / S1: body
          0xE309, 0x1434, 0x000B, 0x0009]                                           # END


def asm(items):
    """Words from a list of words, labels ('name:'), branches (('bt'|'bf'|'bra', 'name')) and jump table words (('off', 'name', the
    number of the word after the braf's delay slot)), the displacements worked out here."""
    at, k = {}, 0
    for x in items:
        if isinstance(x, str):
            at[x[:-1]] = k
        else:
            k += 1
    out = []
    for x in items:
        if isinstance(x, str):
            continue
        if isinstance(x, tuple) and x[0] == 'off':                 # a jump table word: the offset of a label from the word numbered x[2]
            x = (2 * (at[x[1]] - x[2])) & 0xFFFF
        elif isinstance(x, tuple):
            d = at[x[1]] - len(out) - 2
            x = {'bt': 0x8900 | (d & 0xFF), 'bf': 0x8B00 | (d & 0xFF), 'bra': 0xA000 | (d & 0xFFF)}[x[0]]
        out.append(x)
    return out


STATEB = [0x844C]                                             # mov.b @(12,r4),r0
# a body with a branch in it (one without, ending two arms, is merged by the compiler and stays written in each: `tail` below)
#   the add-3 body / tst r2,r2 / bt +1 / mov.l r2,@(32,r4) / mov.l @(8,r4),r3 / add #7,r3 / mov.l r3,@(28,r4)
BODY6 = BODY + [0x2228, 0x8900, 0x1428, 0x5342, 0x7307, 0x1437]
#   mov.l @(8,r4),r2 / add #5,r2 / mov.l r2,@(24,r4) / tst r2,r2 / bt +1 / mov.l r2,@(40,r4) / @(24,r4) + 11 -> @(36,r4)
BODY5 = [0x5242, 0x7205, 0x1426, 0x2228, 0x8900, 0x142A, 0x5346, 0x730B, 0x1439]
LINE6 = BODY + [0x5342, 0x7307, 0x1437, 0x5342, 0x730D, 0x143B]      # no branch: the add-3 body, @(8,r4) + 7 -> @(28,r4), + 13 -> @(44,r4)
OWN = [0xE155, 0x1415]                                        # mov #0x55,r1 / mov.l r1,@(20,r4)
OWN2 = [0xE166, 0x1415]                                       # mov #0x66,r1 / mov.l r1,@(20,r4)

# bf: the fall-through arm is the init (it falls into the body), the taken arm tests state 1 and jumps back to the body
MIRROR = asm(STATEB + [0x8800, ('bf', 'T')] + INIT + ['X:'] + BODY6 + ['END:'] + END +
             ['T:', 0x8801, ('bt', 'X'), ('bra', 'END'), 0x0009])
# state 0: init, falls into the body; state 1: its own code; state 2: the body
CHAIN = asm(STATEB + [0x8800, ('bt', 'S0'), 0x8801, ('bt', 'S1'), 0x8802, ('bt', 'X'), ('bra', 'END'), 0x0009,
                      'S1:'] + OWN + [('bra', 'END'), 0x0009, 'S0:'] + INIT + ['X:'] + BODY6 + ['END:'] + END)
# state 0: its own code; state 1: init, falls into state 2's body
MID = asm(STATEB + [0x8800, ('bt', 'S0'), 0x8801, ('bt', 'S1'), 0x8802, ('bt', 'X'), ('bra', 'END'), 0x0009,
                    'S0:'] + OWN + [('bra', 'END'), 0x0009, 'S1:'] + INIT + ['X:'] + BODY6 + ['END:'] + END)
# state 0 falls into state 1's body, which falls into state 2's
STEPS = asm(STATEB + [0x8800, ('bt', 'S0'), 0x8801, ('bt', 'S1'), 0x8802, ('bt', 'S2'), ('bra', 'END'), 0x0009,
                      'S0:'] + INIT + ['S1:'] + BODY6 + ['S2:'] + BODY5 + ['END:'] + END)
# mirrored, but state 1 has its own (add-5) body: nothing is shared
APART2 = asm(STATEB + [0x8800, ('bf', 'T')] + INIT + BODY6 + ['END:'] + END +
             ['T:', 0x8801, ('bt', 'Y'), ('bra', 'END'), 0x0009, 'Y:'] + BODY5 + [('bra', 'END'), 0x0009])
# every state ends with its own jump to the end
NOFALL2 = asm(STATEB + [0x8800, ('bt', 'S0'), 0x8801, ('bt', 'S1'), 0x8802, ('bt', 'S2'), ('bra', 'END'), 0x0009,
                        'S0:'] + OWN + [('bra', 'END'), 0x0009, 'S1:'] + BODY6 + [('bra', 'END'), 0x0009,
                        'S2:'] + BODY5 + ['END:'] + END)

# states 0 and 1 run their own code and meet at the body; every other state runs its own code and skips the body
JOIN = asm(STATEB + [0x8800, ('bt', 'S0'), 0x8801, ('bt', 'S1'), 0xE177, 0x1415, ('bra', 'END'), 0x0009,
                     'S0:'] + OWN + [('bra', 'X'), 0x0009, 'S1:'] + OWN2 + ['X:'] + BODY6 + ['END:'] + END)
# as JOIN, the body without a branch
TAIL = asm(STATEB + [0x8800, ('bt', 'S0'), 0x8801, ('bt', 'S1'), 0xE177, 0x1415, ('bra', 'END'), 0x0009,
                     'S0:'] + OWN + [('bra', 'X'), 0x0009, 'S1:'] + OWN2 + ['X:'] + LINE6 + ['END:'] + END)
# if (state == 0) { if (@(4,r4) == 0) skip; own } else { own2 }  body;  end       (tst r1,r1 = 0x2118)
NESTED = asm(STATEB + [0x8800, ('bf', 'ELSE'), 0x5141, 0x2118, ('bt', 'END')] + OWN + [('bra', 'X'), 0x0009,
                       'ELSE:'] + OWN2 + ['X:'] + BODY6 + ['END:'] + END)
# the arms that meet at the body set r1 differently and the body stores it: mov.l r1,@(8,r4), then the rest of the body
CARRIED = asm(STATEB + [0x8800, ('bt', 'S0'), 0x8801, ('bt', 'S1'), ('bra', 'END'), 0x0009,
                        'S0:', 0xE155, ('bra', 'X'), 0x0009, 'S1:', 0xE166, 'X:', 0x1412] + BODY5 + ['END:'] + END)
# three tests, each jumping to the fail code when it holds; all three passing reaches the pass code; both go on to the end
#   mov.l @(n,r4),r1 / tst r1,r1 / bt FAIL  three times
LADDER = asm([0xE000, 0x5141, 0x2118, ('bt', 'FAIL'), 0x5142, 0x2118, ('bt', 'FAIL'), 0x5143, 0x2118, ('bt', 'FAIL')] +
             BODY6 + [('bra', 'END'), 0x0009, 'FAIL:'] + BODY5 + ['END:'] + END)

# a jump table on @(12,r4) (0..2): case 0 and case 1 run their own code and meet at the body, case 2 runs its own and skips it
#   mov.l @(12,r4),r1 / mov #3,r2 / cmp/hs r2,r1 / bt END / add r1,r1 / mova TABLE,r0 / mov.w @(r0,r1),r0 / braf r0 / nop / (pad)
SWITCH = asm([0x5143, 0xE203, 0x3122, ('bt', 'END'), 0x311C, 0xC702, 0x001D, 0x0023, 0x0009, 0x0009,
              ('off', 'C0', 9), ('off', 'C1', 9), ('off', 'C2', 9),
              'C0:'] + OWN + [('bra', 'X'), 0x0009, 'C1:'] + OWN2 + ['X:'] + BODY6 + ['END:', 0xE000] + END +
             ['C2:', 0xE177, 0x1415, ('bra', 'END'), 0x0009])

# state 0: if (@(4,r4)) { own; if (@(8,r4) == 0) goto body; } else { own2 }      state 1: 0x44 is stored, then the body
# The body and both arms of state 0's if go on to `@(20,r4) = state; return` (the join of that if: one store, too short to be written
# once by itself); every other state returns at once, so that join is not one the first compare's arms stop at. The path that leaves
# the if for the body must not run that store and return first: they stand in the else of that path, never after the if.
PAST = asm(STATEB + [0x8800, ('bt', 'ARM0'), 0x8801, ('bt', 'ARM1'), 0x000B, 0x0009,
                     'ARM0:', 0x5141, 0x2118, ('bt', 'ELSE')] + OWN + [0x5142, 0x2118, ('bt', 'X'), ('bra', 'JJ'), 0x0009,
                     'ELSE:'] + OWN2 + [('bra', 'JJ'), 0x0009,
                     'ARM1:', 0xE144, 0x1415, 'X:'] + BODY6 + ['JJ:', 0x1405, 0x000B, 0x0009])


def build(fn, tmp):
    code = W(fn) + (W([0x0009]) if len(fn) % 2 else b'')
    open(os.path.join(tmp, '1ST_READ.BIN'), 'wb').write(code)
    open(os.path.join(tmp, 'BASE'), 'w').write('%08X\n' % BASE)
    open(os.path.join(tmp, 'functions.txt'), 'w').write('F %08x %d xform\n' % (BASE, len(code)))
    os.makedirs(os.path.join(tmp, 'src'), exist_ok=True)
    script = ("import sys; sys.path.insert(0, 'tools'); import toolpath, gen_core, gen_drv\n"
              "try:\n"
              "    print(gen_drv.build('xform', 'r0', False)[0])\n"
              "except gen_core.Skip as e:\n"
              "    print('SKIPPED ' + str(e))\n")
    return subprocess.run([sys.executable, '-c', script], cwd=tmp, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                          universal_newlines=True).stdout


class TestGenFallthrough(unittest.TestCase):
    def test_fallthrough(self):
        bad = []
        tmp = tempfile.mkdtemp()
        try:
            shutil.copytree(os.path.join(SKILL, 'scripts', 'tools'), os.path.join(tmp, 'tools'), ignore=shutil.ignore_patterns('__pycache__'))
            out = build(FALL, tmp)
            if 'SKIPPED' in out or 'xform' not in out:
                bad.append('written: the generator did not write it:\n%s' % out)
            else:
                if out.count('+ 0x3)') != 1:
                    bad.append('once: the body (+ 0x3) is written %d times:\n%s' % (out.count('+ 0x3)'), out))
                if out.count('= 0x1;') != 1:
                    bad.append('init: the init (= 0x1;) is written %d times:\n%s' % (out.count('= 0x1;'), out))
                if out.count('= 0x9;') != 1:
                    bad.append('end: the code after the common end (= 0x9;) is written %d times:\n%s' % (out.count('= 0x9;'), out))
            out = build(APART, tmp)
            if 'SKIPPED' in out or '+ 0x3)' not in out or '+ 0x5)' not in out:
                bad.append('apart: two different bodies were not both written:\n%s' % out)
            out = build(STATE, tmp)
            if 'SKIPPED' in out or out.count('(a4 + 0x8)') != 1 or '0x7' not in out:
                bad.append('state: the body that reads a register the init changes is not written once, with both values:\n%s' % out)
            out = build(TWORET, tmp)
            if 'SKIPPED' in out or out.count('+ 0x3)') != 1 or out.count('= 0x1;') != 1:
                bad.append('tworet: with a separate return on another state the body or the init is not written once:\n%s' % out)
            out = build(NOFALL, tmp)
            if 'SKIPPED' in out or out.count('+ 0x3)') != 1:
                bad.append('nofall: the body (+ 0x3) is not written exactly once:\n%s' % out)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
        if bad:
            self.fail('[ERROR] gen_fallthrough check failed:\n' + '\n'.join(bad))

    def run_cases(self, cases):
        """cases: (name, words, [(marker, how many times it must be written, what it is)])."""
        bad = []
        tmp = tempfile.mkdtemp()
        try:
            shutil.copytree(os.path.join(SKILL, 'scripts', 'tools'), os.path.join(tmp, 'tools'), ignore=shutil.ignore_patterns('__pycache__'))
            for name, fn, marks in cases:
                out = build(fn, tmp)
                if 'SKIPPED' in out or 'xform' not in out:
                    bad.append('%s: the generator did not write it:\n%s' % (name, out))
                    continue
                if 'goto ' in out:
                    bad.append('%s: written in the flat form (goto):\n%s' % (name, out))
                    continue
                for mark, n, what in marks:
                    got = len(re.findall(mark[3:], out)) if mark.startswith('re:') else out.count(mark)
                    if got != n:
                        bad.append('%s: %s (%s) is written %d times, not %d:\n%s' % (name, what, mark, got, n, out))
                        break
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
        if bad:
            self.fail('[ERROR] gen_fallthrough check failed:\n' + '\n'.join(bad))

    B3 = ('(a4 + 0x20)) =', 1, 'the store under the branch inside the add-3 body')
    B7 = ('+ 0x7)', 1, 'the end of the add-3 body')
    B5 = ('+ 0xB)', 1, 'the end of the add-5 body')
    I1 = ('= 0x1;', 1, 'the init')
    E9 = ('= 0x9;', 1, 'the code after the common end')
    O5 = ('0x55', 1, 'the first own code')
    O6 = ('0x66', 1, 'the second own code')

    def test_mirrored_and_chains(self):
        s = self
        self.run_cases([
            ('mirrored', MIRROR, [s.B3, s.B7, s.I1, s.E9]),
            ('chain', CHAIN, [s.B3, s.B7, s.I1, s.O5, s.E9]),
            ('mid', MID, [s.B3, s.B7, s.I1, s.O5, s.E9]),
            ('steps', STEPS, [s.B3, s.B7, s.B5, s.I1, s.E9]),
            ('apart2', APART2, [s.B3, s.B5, s.I1, s.E9]),
            ('nofall2', NOFALL2, [s.B3, s.B5, s.O5, s.E9]),
        ])

    def test_join_of_several_arms(self):
        s = self
        self.run_cases([
            ('join', JOIN, [s.B3, s.B7, s.O5, s.O6, ('0x77', 1, 'the code of the state that skips the body'), s.E9]),
            ('nested', NESTED, [s.B3, s.B7, s.O5, s.O6, s.E9]),
            ('carried', CARRIED, [('(a4 + 0x8)) =', 1, 'the store of the carried register'), s.B5, s.O5, s.O6, s.E9]),
            ('ladder', LADDER, [s.B3, s.B7, s.B5, s.E9]),
            ('past', PAST, [s.B3, s.B7, s.O5, s.O6, ('0x44', 1, 'the code of state 1'),
                            (r're:\(a4 \+ 0x8\)\)\) != 0\) \{\n\s*\*\(unsigned int \*\)\(\(a4 \+ 0x14\)\) = t0;\n\s*return t0;\n\s*\}', 1,
                             'the store and return after the inner join, under the test of the path that does not go to the body')]),
            ('tail', TAIL, [('+ 0xD)', 2, 'the body without a branch, in each of the two arms it ends'), s.O5, s.O6, s.E9]),
            ('switch', SWITCH, [('switch (', 1, 'the switch'), s.B3, s.B7, s.O5, s.O6, ('0x77', 1, 'the code of the case that skips the body'), s.E9]),
        ])


if __name__ == '__main__':
    unittest.main()
