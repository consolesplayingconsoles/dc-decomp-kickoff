#!/usr/bin/env python3
"""The report's stages (scripts/tools/5-generated/remaining.py stage): a function is counted at the first step it has not passed.
A reason the generator gives for not reading a function is in its own words, so the old rule's fall-through put every one of them
under "Written C with errors" although no C was written (Virtua Tennis 2026-10-24: 172 functions, none with C). No game data.
Stdlib only.

    check.py      reader      "cannot read: arg gap", "blocked: banked registers", "not read" -> Not written C
                  translated  differs / does not compile -> Checked with errors; no cases -> Drawn with errors
                  readable    "readable, no result in the last report" -> Not drawn
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
TOOLS = os.path.join(os.path.dirname(os.path.dirname(HERE)), 'scripts', 'tools')
sys.path.insert(0, os.path.join(TOOLS, '5-generated'))
sys.path.insert(0, TOOLS)
import toolpath  # noqa: E402,F401
import remaining  # noqa: E402

WANT = [
    ('cannot read: arg gap', 'Not written C'),
    ('cannot read: stack arguments without four in registers', 'Not written C'),
    ('blocked: banked registers', 'Not written C'),
    ('not read', 'Not written C'),
    ('runtime helper', 'Not written C'),
    ('translated, differs from the original (calls)', 'Checked with errors'),
    ('translated, does not compile', 'Checked with errors'),
    ('translated, no cases: Skip the original does not finish', 'Drawn with errors'),
    ('readable, no result in the last report', 'Not drawn'),
]


def main():
    bad = ['%r -> %r, want %r' % (c, remaining.stage(c), w) for c, w in WANT if remaining.stage(c) != w]
    if set(remaining.STAGES) != set(w for _, w in WANT) | {'Written C with errors'}:
        bad.append('stages %r' % (remaining.STAGES,))
    for b in bad:
        print('FAIL', b)
    print('remaining: %s' % ('OK' if not bad else '%d failures' % len(bad)))
    sys.exit(1 if bad else 0)


if __name__ == '__main__':
    main()
