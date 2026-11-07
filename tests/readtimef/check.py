#!/usr/bin/env python3
"""The time a function may take to be read scales with GEN_TIME_FACTOR, as the time to draw its cases does (scripts/tools/5-generated/gen_equiv/
__main__.py). No game data, no compiler. Stdlib only.

The read alarm was max(300, size / 4) seconds whatever the factor. Zombie Revenge kmRenderTexture (1,622 bytes) reads in about 260 s on a quiet
machine and 408 s next to four other jobs: it timed out against 405 s, and GEN_TIME_FACTOR, the setting for a shared machine, did not help.

    check.py      the source of the read step:
                    scaled    its alarm is multiplied by TIMEF
"""
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(os.path.dirname(os.path.dirname(HERE)), 'scripts', 'tools', '5-generated', 'gen_equiv', '__main__.py')


def main():
    text = open(SRC).read()
    m = re.search(r'def _read\(n\):\s*\n\s*signal\.alarm\((.*)\)', text)
    if not m:
        sys.exit('[ERROR] readtimef check failed:\nno read alarm found in _read()')
    if 'TIMEF' not in m.group(1):
        sys.exit('[ERROR] readtimef check failed:\nscaled: the read alarm %s does not use TIMEF' % m.group(1))
    print('[readtimef] ok: the read alarm scales with GEN_TIME_FACTOR')


if __name__ == '__main__':
    main()
