#!/usr/bin/env python3
"""status.txt has three states (scripts/tools/progress.py statuses): `[x] NAME` reached, `[ ] NAME` tested and not reached, `[?] NAME`
not tested yet. The badge shows them as a tick, a cross and a question mark. Each status needs the ones above it: a tick under a
cross or a question mark stops the report, a question mark or a cross under a tick is fine (Crazy Taxi: PLAYABLE ticked with STABLE
not yet tested is not "unstable"). No game data. Stdlib only.

    check.py      statuses() alone, lifted from progress.py (the rest of that module needs a repo):
                    states    [x] -> True, [ ] -> False, [?] -> None, in file order, comments and blank lines skipped
                    columns   three marks are Flycast, Dreamcast, Native (the badge's grid), each column in its own order;
                              two marks, the older form, are Dreamcast and Native with Flycast not tested
                    order     a tick under a question mark is an error; a question mark or a cross under a tick is not
                    syntax    any other mark is an error that names the line
                    hidden    a grid column shows only when its BUILDS FROM C (the grid's first line) is ticked; none
                              ticked, no grid
                    marks     the badge's marks for the three states are a tick, a cross and a question mark
"""
import unittest
from unittest import mock
import ast
import os
import re
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
PROGRESS = os.path.join(os.path.dirname(HERE), 'scripts', 'tools', 'progress.py')


def lift(name):
    """The named function of progress.py as a callable, without running the module (it reads a whole repo at import)."""
    tree = ast.parse(open(PROGRESS, encoding='utf-8').read())
    fn = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == name)
    ns = {'os': os, 're': re, 'sys': sys}
    exec(compile(ast.Module(body=[fn], type_ignores=[]), PROGRESS, 'exec'), ns)
    return ns[name]


def marks():
    """The three marks the badge gives the states, from progress.py's mark(): {True: tick, False: cross, None: question mark}."""
    mark = lift('mark')
    return {state: mark(state) for state in (True, False, None)}


def run(statuses, text):
    tmp = tempfile.mkdtemp()
    p = os.path.join(tmp, 'status.txt')
    open(p, 'w').write(text)
    try:
        return statuses(p), None
    except SystemExit as e:
        return None, str(e)


class TestStatus(unittest.TestCase):
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

    def test_status(self):
        statuses = lift('statuses')
        bad = []
        out, err = run(statuses, '# comment\n[x] BUILDS FROM C\n\n[x] BOOTS TO MENU\n[ ] PLAYABLE\n[?] STABLE\n')
        if err or out != [('BUILDS FROM C', True), ('BOOTS TO MENU', True), ('PLAYABLE', False), ('STABLE', None)]:
            bad.append('states: expected True, True, False, None, got %s %s' % (out, err or ''))
        out, err = run(statuses, '[x] [x] [ ] BUILDS FROM C\n[x] [ ] [?] BOOTS TO MENU\n[?] [ ] [ ] PLAYABLE\n')
        if err or out != [('BUILDS FROM C', True, True, False), ('BOOTS TO MENU', True, False, None), ('PLAYABLE', None, False, False)]:
            bad.append('columns: three marks are Flycast, Dreamcast, Native, got %s %s' % (out, err or ''))
        out, err = run(statuses, '[x] BUILDS FROM C\n[x] [ ] BOOTS TO MENU\n[x] [?] PLAYABLE\n[ ] [ ] STABLE\n')
        if err or out != [('BUILDS FROM C', True), ('BOOTS TO MENU', None, True, False), ('PLAYABLE', None, True, None), ('STABLE', None, False, False)]:
            bad.append('columns: two marks (the older form) are Dreamcast then Native, Flycast not tested, got %s %s' % (out, err or ''))
        out, err = run(statuses, '[ ] [x] [ ] BUILDS FROM C\n[x] [x] [ ] BOOTS TO MENU\n')
        if not err or 'BOOTS TO MENU' not in err:
            bad.append('columns: a Flycast tick under a Flycast cross must be an error naming the tick, got %s %s' % (out, err or ''))
        out, err = run(statuses, '[x] [x] [ ] BUILDS FROM C\n[x] [x] [ ] BOOTS TO MENU\n[x] [x] [x] PLAYABLE\n')
        if not err or 'PLAYABLE' not in err:
            bad.append('columns: a Native tick under a Native cross must be an error naming the tick, got %s %s' % (out, err or ''))
        out, err = run(statuses, '[ ] [ ] [x] BUILDS FROM C\n[ ] [ ] [x] BOOTS TO MENU\n')
        if err:
            bad.append('columns: Native may be ahead of Flycast and Dreamcast (each column has its own order), got %s' % err)
        out, err = run(statuses, '[x] BUILDS FROM C\n[x] BOOTS TO MENU\n[x] PLAYABLE\n[?] STABLE\n')
        if err or out[-1] != ('STABLE', None):
            bad.append('order: a question mark under ticks must pass, got %s %s' % (out, err or ''))
        out, err = run(statuses, '[x] BUILDS FROM C\n[?] BOOTS TO MENU\n[x] PLAYABLE\n')
        if not err or 'PLAYABLE' not in err:
            bad.append('order: a tick under a question mark must be an error naming the tick, got %s %s' % (out, err or ''))
        out, err = run(statuses, '[x] BUILDS FROM C\n[-] BOOTS TO MENU\n')
        if not err or 'line 2' not in err:
            bad.append('syntax: an unknown mark must be an error naming its line, got %s %s' % (out, err or ''))
        grid = lift('grid_columns')
        mark = lift('mark')
        heads, rows = grid([('BUILDS FROM C', True, True, False), ('BOOTS TO MENU', True, False, None), ('PLAYABLE', None, False, False)], mark)
        if heads != ['FLYCAST', 'DREAMCAST'] or [r[1] for r in rows] != [['✅', '✅'], ['✅', '❌'], ['❓', '❌']]:
            bad.append('hidden: a column whose BUILDS FROM C is not ticked must not show, got %s %s' % (heads, rows))
        heads, rows = grid([('BUILDS FROM C', None, False, False), ('BOOTS TO MENU', None, False, False)], mark)
        if heads or rows:
            bad.append('hidden: no BUILDS FROM C ticked, no grid, got %s %s' % (heads, rows))
        heads, rows = grid([('A ONE-MARK LINE', True), ('BUILDS FROM C', False, False, True)], mark)
        if heads != ['NATIVE'] or rows != [('BUILDS FROM C', ['✅'])]:
            bad.append('hidden: one-mark lines are not on the grid; Native alone shows, got %s %s' % (heads, rows))
        mk = marks()
        if len(set(mk.values())) != 3 or mk[True] != '✅' or mk[False] != '❌' or mk[None] != '❓':
            bad.append('marks: expected tick, cross and question mark for True, False, None, got %r' % mk)
        if not bad:
            print('[status] ok: [x] / [ ] / [?] read as reached / not reached / not tested; a tick under a question mark fails; three badge marks')
            return
        self.fail('[ERROR] status check failed:\n' + '\n'.join(bad))


if __name__ == '__main__':
    unittest.main()
