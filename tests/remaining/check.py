#!/usr/bin/env python3
"""The report's stages (scripts/tools/5-generated/remaining.py stage): a function is counted at the first step it has not passed.
A reason the generator gives for not reading a function is in its own words, so the old rule's fall-through put every one of them
under "Written C with errors" although no C was written (Virtua Tennis 2026-10-24: 172 functions, none with C). No game data.
Stdlib only.

    check.py      reader      "cannot read: arg gap", "blocked: banked registers", "not read" -> Not written C
                  translated  differs / does not compile -> Checked with errors; no cases -> Drawn with errors
                  readable    "readable, no result in the last report" -> Not drawn
                  batches     read_batches reads N functions at a time and hands each batch's results over before the next one starts, so
                              a stall costs one batch (25 functions, batch 10 -> 10, 10, 5; every name once)
                  limit       alarm_seconds: max(120, size/3) s by default (a 21 KB function gets two hours), and no more than --limit when given
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


def fake_reader(task):
    name, size = task
    return name, 'readable' if size % 2 == 0 else 'cannot read: odd'


def main():
    bad = ['%r -> %r, want %r' % (c, remaining.stage(c), w) for c, w in WANT if remaining.stage(c) != w]
    if set(remaining.STAGES) != set(w for _, w in WANT) | {'Written C with errors'}:
        bad.append('stages %r' % (remaining.STAGES,))
    todo = [('f%d' % i, i) for i in range(25)]
    seen = []
    try:
        remaining.read_batches(todo, 3, 10, fake_reader, lambda done: seen.append(dict(done)))
        sizes = [len(d) for d in seen]
        if sizes != [10, 10, 5]:
            bad.append('batches: sizes %r, want [10, 10, 5]' % sizes)
        names = sorted(n for d in seen for n in d)
        if names != sorted(n for n, _ in todo):
            bad.append('batches: names read %d, want %d, each once' % (len(names), len(todo)))
        if seen and seen[0].get('f3') != 'cannot read: odd':
            bad.append('batches: results not handed over as read: %r' % seen[0].get('f3'))
    except AttributeError as e:
        bad.append('batches: %s' % e)
    try:
        remaining.LIMIT = None
        a = [remaining.alarm_seconds(100), remaining.alarm_seconds(21482)]
        remaining.LIMIT = 300
        b = [remaining.alarm_seconds(100), remaining.alarm_seconds(21482)]
        remaining.LIMIT = 60
        c = remaining.alarm_seconds(100)
        remaining.LIMIT = None
        if a != [120, 7160] or b != [120, 300] or c != 60:
            bad.append('limit: %r %r %r, want [120, 7160] [120, 300] 60' % (a, b, c))
    except AttributeError as e:
        bad.append('limit: %s' % e)
    for b in bad:
        print('FAIL', b)
    print('remaining: %s' % ('OK' if not bad else '%d failures' % len(bad)))
    sys.exit(1 if bad else 0)


if __name__ == '__main__':
    main()
