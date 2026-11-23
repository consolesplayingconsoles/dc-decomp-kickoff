#!/usr/bin/env python3
"""The margins of the progress badge (badges/progress.svg, written by scripts/tools/progress.py write_badge). No game data, no compiler.
Stdlib only.

The badge is a card of text and bars; its four margins are the same number (M = 12), whatever it holds:
a badge with only the metrics, and one with the status grid below them.

    check.py      left      every left-aligned text (the row labels, the secondary metric, the status names) starts at x = M
                  right     every right-aligned text (the percentages, the matching figure) ends at x = width - M
                  top       the first bar's top edge is at y = M
                  bottom    the last text's baseline is 15 (3 of descender, then M) above the bottom edge
                  columns   the last status column's centre leaves half of its heading (19) and M to the right edge
"""
import os
import re
import shutil
import struct
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
SKILL = os.path.dirname(HERE)
BASE = 0x8C010000
CODE = struct.pack('<16H', *([0x000B, 0x0009] * 8))
M = 12


def badge(status):
    """the SVG progress.py writes for a temp repo of two proven functions; status: the text of status.txt, or None for no file"""
    tmp = tempfile.mkdtemp()
    try:
        shutil.copytree(os.path.join(SKILL, 'scripts', 'tools'), os.path.join(tmp, 'tools'), ignore=shutil.ignore_patterns('__pycache__'))
        for name, data, mode in (('1ST_READ.BIN', CODE, 'wb'), ('BASE', '%08X\n' % BASE, 'w'),
                                 ('functions.txt', 'F %08x 8 alpha\nF %08x 8 beta\n' % (BASE, BASE + 8), 'w'),
                                 ('tests/equivalent.txt', 'alpha\nbeta\n', 'w'), ('README.md', '# t\n', 'w')):
            os.makedirs(os.path.dirname(os.path.join(tmp, name)) or tmp, exist_ok=True)
            with open(os.path.join(tmp, name), mode) as fh:
                fh.write(data)
        os.makedirs(os.path.join(tmp, 'src'))
        if status is not None:
            with open(os.path.join(tmp, 'status.txt'), 'w') as fh:
                fh.write(status)
        r = subprocess.run([sys.executable, 'tools/progress.py'], cwd=tmp, capture_output=True, text=True)
        assert r.returncode == 0, r.stdout[-300:] + r.stderr[-300:]
        with open(os.path.join(tmp, 'badges', 'progress.svg')) as fh:
            return fh.read()
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def texts(svg):
    """[(x, y, anchor, size, text)] of every <text>, the anchor and size from the nearest enclosing <g> that sets them (start for a row label)"""
    out = []
    stack = []
    for m in re.finditer(r'<g ([^>]*)>|</g>|<text ([^>]*)>([^<]*)</text>', svg):
        if m.group(0) == '</g>':
            stack.pop()
        elif m.group(1) is not None:
            stack.append(m.group(1))
        else:
            attrs = m.group(2)
            anchor = re.search(r'text-anchor="(\w+)"', attrs)
            if not anchor:
                for g in reversed(stack):
                    anchor = re.search(r'text-anchor="(\w+)"', g)
                    if anchor:
                        break
            out.append((int(re.search(r'x="(\d+)"', attrs).group(1)), int(re.search(r'y="(\d+)"', attrs).group(1)),
                        anchor.group(1) if anchor else 'start', m.group(3)))
    return out


GRID = 'MODE: equivalent\n[x] [x] [x] BUILDS FROM C\n[x] [ ] [ ] BOOTS TO MENU\n[ ] [ ] [ ] PLAYABLE\n[ ] [ ] [ ] STABLE\n'


class TestBadgeMargins(unittest.TestCase):
    def check(self, svg):
        w = int(re.search(r'<svg[^>]* width="(\d+)"', svg).group(1))
        h = int(re.search(r'<svg[^>]* height="(\d+)"', svg).group(1))
        ts = texts(svg)
        left = sorted(set(x for x, y, a, t in ts if a == 'start'))
        right = sorted(set(x for x, y, a, t in ts if a == 'end'))
        self.assertEqual(left, [M], 'left-aligned texts start at M: %s' % left)
        self.assertEqual(right, [w - M], 'right-aligned texts end at width - M: %s' % right)
        bars = [int(m.group(1)) for m in re.finditer(r'<rect x="\d+" y="(\d+)" width="\d+" height="10"', svg)]
        self.assertEqual(min(bars), M, 'the first bar starts at the top margin')
        self.assertEqual(h - max(y for x, y, a, t in ts), M + 3, 'the last baseline sits M + 3 above the bottom edge')
        return w, ts

    def test_metrics(self):
        self.check(badge(None))

    def test_grid(self):
        w, ts = self.check(badge(GRID))
        heads = [(x, t) for x, y, a, t in ts if t in ('FLYCAST', 'DREAMCAST', 'NATIVE')]
        self.assertEqual(len(heads), 3)
        self.assertEqual(max(x for x, t in heads), w - M - 19, 'the last column leaves half its heading and M')


if __name__ == '__main__':
    unittest.main()
