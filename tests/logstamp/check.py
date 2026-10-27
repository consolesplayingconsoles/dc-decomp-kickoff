#!/usr/bin/env python3
"""Step 5's log lines carry the wall-clock time (scripts/tools/5-generated/gen_equiv/stamp.py). Stdlib only.

    check.py      lines     every line ends with the time, once, also when one line is written in pieces or several in one write
                  wired     gen_equiv's output (the terminal and build/gen_run.log) goes through it
"""
import io
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
GEN = os.path.join(os.path.dirname(os.path.dirname(HERE)), 'scripts', 'tools', '5-generated', 'gen_equiv')
sys.path.insert(0, GEN)
import stamp  # noqa: E402


def main():
    bad = []
    b = io.StringIO()
    s = stamp.Stamp(b, clock=lambda: '09:13:06')
    s.write('[ 606s] read 125 '); s.write('of 132 functions\n')
    s.write('  drawn a   10 B\n  drawn b   12 B\n\n')
    s.write('last')
    want = '[ 606s] read 125 of 132 functions  09:13:06\n  drawn a   10 B  09:13:06\n  drawn b   12 B  09:13:06\n\nlast'
    if b.getvalue() != want:
        bad.append('lines: %r; want %r' % (b.getvalue(), want))
    src = open(os.path.join(GEN, '__main__.py')).read()
    if 'stamp.Stamp(' not in src:
        bad.append('wired: gen_equiv does not write its output through stamp.Stamp')
    if bad:
        sys.exit('[ERROR] logstamp check failed:\n' + '\n'.join(bad))
    print('[logstamp] ok: every line of the step-5 log ends with the wall-clock time')


if __name__ == '__main__':
    main()
