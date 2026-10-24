#!/usr/bin/env python3
"""The generator's case drawing keeps to a time budget (scripts/tools/5-generated/gen_equiv/gen_drv.py pick, grow): a function whose
runs mostly hit the simulator's step cap used to spend its whole 60 s drawing and time out with nothing (Virtua Tennis: 117 of 799
functions, 118 runs of the original at 0.3 s each). Now one deadline (DRAW_SECONDS from the start of the function's drawing) covers
every attempt: the candidates and the growth stop at it, however few ended, and later attempts are skipped (what is left goes to
directed.rescue). The first version stopped only once 12 had ended, so a wait loop that random cases rarely end (2 of 40 on Virtua
Tennis rankDispLoad, 2 s a run) still ran every candidate and timed out: 9 of 22 timeouts on 2026-10-24. The deadline is two thirds of
the function's limit in the run, max(60, size/8) s times GEN_TIME_FACTOR. No game data, no compiler. Stdlib only.

    check.py      original_runs replaced by a stand-in:
                    budget     at 0.005 s a run, one case in five ending: pick returns within 4 s of a 0.5 s budget, from 300 candidates,
                               with 12 or more cases kept
                    survivors  the cases kept are ones the stand-in ended on
                    few        when fewer than 12 end, the loop still stops at the deadline (it used to run every candidate)
                    scale      draw_seconds: 40 s for a small function, size/8 * 2/3 for a big one, times GEN_TIME_FACTOR
"""
import os
import random
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
TOOLS = os.path.join(os.path.dirname(os.path.dirname(HERE)), 'scripts', 'tools')
os.environ['GEN_DRAW_SECONDS'] = '0.5'
tmp = tempfile.mkdtemp()
os.chdir(tmp)
open('functions.txt', 'w').write('F 0c020000 8 fn\nF 0c020008 4800 big\n')
open('BASE', 'w').write('0C020000\n')
open('1ST_READ.BIN', 'wb').write(b'\x00\x09' * 4)
sys.path.insert(0, os.path.join(TOOLS, '5-generated', 'gen_equiv'))
sys.path.insert(0, TOOLS)
import toolpath  # noqa: E402,F401
import gen_drv  # noqa: E402


def main():
    bad = []
    calls = [0]

    def standin(ends_every, secs):
        def run(name, case):
            calls[0] += 1
            time.sleep(secs)
            if case['k'] % ends_every == 0:
                return 10, {case['k']}
            return None, set()
        return run

    cases = [{'k': i, 'regs': {}, 'poke': {}, 'calls': []} for i in range(300)]
    gen_drv.original_runs = standin(5, 0.005)      # about 100 runs fit in the budget, 20 of them end
    t = time.time()
    chosen = gen_drv.pick('fn', cases, 36)
    dt = time.time() - t
    if dt > 4.0:
        bad.append('budget: pick took %.1f s from 300 candidates at 0.005 s a run' % dt)
    if len(chosen) < 12 or any(c['k'] % 5 for c in chosen):
        bad.append('survivors: %r' % [c['k'] for c in chosen][:8])
    if calls[0] >= 300:
        bad.append('budget: all %d candidates were run' % calls[0])
    calls[0] = 0
    gen_drv.original_runs = standin(150, 0.02)    # two of 300 end: fewer than 12
    gen_drv.DEADLINE[0] = None
    t = time.time()
    gen_drv.pick('fn', cases, 36)
    dt = time.time() - t
    if dt > 4.0 or calls[0] >= 300:
        bad.append('few: %d of 300 candidates run in %.1f s, past the 0.5 s deadline' % (calls[0], dt))
    del os.environ['GEN_DRAW_SECONDS']
    want = {('fn', '1'): 40.0, ('big', '1'): 400.0, ('fn', '3'): 120.0}
    for (n, f), w in want.items():
        os.environ['GEN_TIME_FACTOR'] = f
        if abs(gen_drv.draw_seconds(n) - w) > 0.01:
            bad.append('scale: draw_seconds(%s) at factor %s is %r, want %r' % (n, f, gen_drv.draw_seconds(n), w))
    os.environ.pop('GEN_TIME_FACTOR', None)
    for b in bad:
        print('FAIL', b)
    print('drawbudget: %s' % ('OK' if not bad else '%d failures' % len(bad)))
    sys.exit(1 if bad else 0)


if __name__ == '__main__':
    main()
