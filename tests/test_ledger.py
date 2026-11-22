#!/usr/bin/env python3
"""Nothing cuts the reason a function failed (scripts/tools/common/ledger.py, gen_equiv). Stdlib only, a scratch folder, no game data.

    check.py      detail    record() keeps a detail of any length: it cut each at 400 characters, and a DIFFERS line on a long call list
                            lost the call that differs (Virtua Tennis playerInit, 46 functions whose difference could not be sorted)
                  readwhy   step 5 records the reader's whole reason: it kept the first word only ("arg" for "arg gap", decoNumDraw)
                  noslice   no step-5 source slices an error, a reason or a detail (str(e)[:90], detail[:600], why[:100] ...)
"""
import unittest
from unittest import mock
import json
import os
import re
import shutil
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
TOOLS = os.path.join(os.path.dirname(HERE), 'scripts', 'tools')
sys.path.insert(0, TOOLS)
import toolpath  # noqa: E402,F401  (every tools folder on the import path: sim/, common/, the steps)
import ledger  # noqa: E402


class TestLedger(unittest.TestCase):
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

    def test_ledger(self):
        bad = []
        tmp = tempfile.mkdtemp(); cwd = os.getcwd()
        try:
            os.chdir(tmp)
            long_ = 'case 1: calls: original [' + ', '.join('["0C0%05X", ["00000001"], []]' % k for k in range(200)) + '] / C [...]'
            ledger.record('run', 'f', 'DIFFERS', long_)
            got = json.loads(open('state/results.jsonl').readline())['detail']
            if got != long_:
                bad.append('detail: %d of %d characters kept' % (len(got), len(long_)))
        finally:
            os.chdir(cwd); shutil.rmtree(tmp, ignore_errors=True)
        src = open(os.path.join(TOOLS, '5-generated', 'gen_equiv', '__main__.py')).read()
        m = re.search(r"except gen_core\.Skip as e: return \(n,(.*)\)\n", src)
        if not m or 'split()[0]' in m.group(1):
            bad.append('readwhy: the reader\'s refusal is recorded as %s, not the whole reason' % (m.group(1) if m else '?'))
        gdir = os.path.join(TOOLS, '5-generated', 'gen_equiv')
        for f in sorted(os.listdir(gdir)):
            if f.endswith('.py'):
                for k, l in enumerate(open(os.path.join(gdir, f)), 1):
                    if re.search(r"(str\(e\)|str\(r2\['error'\]\)|\bdetail|\bwhy|\berr)\)?\[:\d+\]", l):
                        bad.append('noslice: %s:%d cuts a reason: %s' % (f, k, l.strip()[:120]))
        if bad:
            self.fail('[ERROR] ledger check failed:\n' + '\n'.join(bad))


if __name__ == '__main__':
    unittest.main()
