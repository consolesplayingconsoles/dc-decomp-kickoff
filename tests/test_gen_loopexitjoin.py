#!/usr/bin/env python3
"""An if on the way out of an inner loop is written as an if, its join once (scripts/tools/5-generated/gen_equiv/gen_core.py join_of).
No game data, no compiler. Stdlib only.

A loop that retries a call sits inside an outer loop and has two ways out, one that ends the function and one where the outer
body goes on: when the retry loop is left that way, the outer body goes on (an optional step, then
code every pass runs, then the outer test), and comes back to the retry loop. The generator writes that way out inside the retry
loop's braces, ending in `continue`. A branch met there has its join outside the retry loop's own body, and the join was not taken
as one: each arm was read on to the outer test, so everything after the if was written once per arm, and again for the next if
(a library function of 288 bytes: 11 calls in the original, 31 in the C).

    exit-if     an optional store (0x55) under a test, on the way out of the retry loop, then code every pass runs (0x66, + 3):
                  once      the code after the if is written once
                  step      the optional store is written once
    two-ifs     two such ifs one after the other: the code after each is written once
    inside      an if inside the retry loop's own body keeps its join as before: its code once
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import test_gen_fallthrough as H  # noqa: E402  (asm, the scratch repo and the runner)

# r1 counts the outer passes; the retry loop reads @(8,r4) until it is zero
HEAD = [0xE100, ('bra', 'TEST'), 0x0009,
        'HEAD:', 0x1411,                                              # mov.l r1,@(4,r4)
        'INNER:', 0x5042, 0x2008, ('bt', 'OUT'),                      # mov.l @(8,r4),r0 / tst r0,r0 / bt OUT
        0x504E, 0x2008, ('bf', 'CONT'), ('bra', 'RET'), 0x0009,       # mov.l @(56,r4),r0 / tst r0,r0 / bf CONT / bra RET: the retry gives up, the function ends
        'CONT:', 0x5243, 0x7201, 0x1423, ('bra', 'INNER'), 0x0009]    # the retry: @(12,r4) += 1
STEP = ['OUT:', 0x2118, ('bf', 'SKIP'), 0xE355, 0x1434]               # tst r1,r1 / bf SKIP / mov #0x55,r3 / mov.l r3,@(16,r4)
BODY = ['SKIP:', 0xE366, 0x1435, 0x5246, 0x7203, 0x1426]              # mov #0x66,r3 / mov.l r3,@(20,r4) / @(24,r4) += 3
TAIL = [0x7101, 'TEST:', 0x5047, 0x3103, ('bf', 'HEAD'), 'RET:', 0xE322, 0x143F, 0x000B, 0x0009]   # ... / RET: mov #0x22,r3 / mov.l r3,@(60,r4) / rts   # add #1,r1 / mov.l @(28,r4),r0 / cmp/ge r0,r1 / bf HEAD / rts

EXIT_IF = H.asm(HEAD + STEP + BODY + TAIL)
# a second optional store (0x44 into @(32,r4)) under a test of @(36,r4), then more code every pass runs (@(40,r4) += 5)
STEP2 = [0x5049, 0x2008, ('bt', 'SKIP2'), 0xE344, 0x1438]             # mov.l @(36,r4),r0 / tst r0,r0 / bt SKIP2 / mov #0x44,r3 / mov.l r3,@(32,r4)
BODY2 = ['SKIP2:', 0x524A, 0x7205, 0x142A, 0xE377, 0x143B]            # @(40,r4) += 5 / mov #0x77,r3 / mov.l r3,@(44,r4)
TWO_IFS = H.asm(HEAD + STEP + BODY + STEP2 + BODY2 + TAIL)
# the if inside the retry loop's own body: @(12,r4) += 1 only when @(48,r4) is not zero, then 0x33 into @(52,r4) on every retry
INSIDE = H.asm([0xE100, ('bra', 'TEST'), 0x0009,
                'HEAD:', 0x1411,
                'INNER:', 0x5042, 0x2008, ('bt', 'OUT'),
                0x504E, 0x2008, ('bf', 'CONT'), ('bra', 'RET'), 0x0009,
                'CONT:', 0x504C, 0x2008, ('bt', 'NOINC'), 0x5243, 0x7201, 0x1423,      # mov.l @(48,r4),r0 / tst / bt NOINC / @(12,r4) += 1
                'NOINC:', 0xE333, 0x143D, 0x5246, 0x7203, 0x1426, ('bra', 'INNER'), 0x0009,
                'OUT:'] + TAIL)


class TestGenLoopExitJoin(H.TestGenFallthrough):
    def test_exit_if(self):
        self.run_cases([
            ('exit-if', EXIT_IF, [('0x66', 1, 'the code after the if'), ('+ 0x3)', 1, 'the end of the code after the if'),
                                  ('0x55', 1, 'the optional store')]),
            ('two-ifs', TWO_IFS, [('0x66', 1, 'the code after the first if'), ('0x77', 1, 'the code after the second if'),
                                  ('0x55', 1, 'the first optional store'), ('0x44', 1, 'the second optional store')]),
            ('inside', INSIDE, [('0x33', 1, 'the code after the if inside the retry loop'), ('(a4 + 0xC)) =', 1, 'the optional add')]),
        ])

    # the parent's own tests are not run again from here
    test_fallthrough = test_mirrored_and_chains = test_join_of_several_arms = None


if __name__ == '__main__':
    unittest.main()
