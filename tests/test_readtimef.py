#!/usr/bin/env python3
"""The time a function may take to be read scales with GEN_TIME_FACTOR, as the time to draw its cases does (scripts/tools/5-generated/gen_equiv/
__main__.py). No game data, no compiler. Stdlib only.

The read alarm was max(300, size / 4) seconds whatever the factor. Zombie Revenge kmRenderTexture (1,622 bytes) reads in about 260 s on a quiet
machine and 408 s next to four other jobs: it timed out against 405 s, and GEN_TIME_FACTOR, the setting for a shared machine, did not help.

    check.py      the source of the read step:
                    scaled    its alarm is multiplied by TIMEF
"""
import unittest
from unittest import mock
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(os.path.dirname(HERE), 'scripts', 'tools', '5-generated', 'gen_equiv', '__main__.py')


class TestReadtimef(unittest.TestCase):
    def setUp(self):
        self.addCleanup(os.chdir, os.getcwd())
        saved_path = list(sys.path)
        self.addCleanup(sys.path.__setitem__, slice(None), saved_path)
        environ = mock.patch.dict(os.environ)
        environ.start()
        self.addCleanup(environ.stop)
        snapshot = self._snapshot_modules()
        self.addCleanup(self._restore_modules, snapshot)

    @staticmethod
    def _snapshot_modules():
        tools = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'scripts')
        modules = dict(sys.modules)
        state = {}
        for name, mod in modules.items():
            if (getattr(mod, '__file__', None) or '').startswith(tools):
                state[name] = dict(vars(mod))
        return modules, state

    @staticmethod
    def _restore_modules(snapshot):
        modules, state = snapshot
        for name in list(sys.modules):
            if name not in modules:
                del sys.modules[name]
        sys.modules.update(modules)
        for name, saved in state.items():
            vars(modules[name]).clear()
            vars(modules[name]).update(saved)

    def test_readtimef(self):
        text = open(SRC).read()
        m = re.search(r'def _read\(n\):\s*\n\s*signal\.alarm\((.*)\)', text)
        if not m:
            self.fail('[ERROR] readtimef check failed:\nno read alarm found in _read()')
        if 'TIMEF' not in m.group(1):
            self.fail('[ERROR] readtimef check failed:\nscaled: the read alarm %s does not use TIMEF' % m.group(1))


if __name__ == '__main__':
    unittest.main()
