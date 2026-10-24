#!/usr/bin/env python3
"""status.txt has three states (scripts/tools/progress.py statuses): `[x] NAME` reached, `[ ] NAME` tested and not reached, `[?] NAME`
not tested yet. The badge shows them as a tick, a cross and a question mark. Each status needs the ones above it: a tick under a
cross or a question mark stops the report, a question mark or a cross under a tick is fine (Crazy Taxi: PLAYABLE ticked with STABLE
not yet tested is not "unstable"). No game data. Stdlib only.

    check.py      statuses() alone, lifted from progress.py (the rest of that module needs a repo):
                    states    [x] -> True, [ ] -> False, [?] -> None, in file order, comments and blank lines skipped
                    order     a tick under a question mark is an error; a question mark or a cross under a tick is not
                    syntax    any other mark is an error that names the line
                    marks     the badge's marks for the three states are a tick, a cross and a question mark
"""
import ast
import os
import re
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
PROGRESS = os.path.join(os.path.dirname(os.path.dirname(HERE)), 'scripts', 'tools', 'progress.py')


def lift(name):
    """The named function of progress.py as a callable, without running the module (it reads a whole repo at import)."""
    tree = ast.parse(open(PROGRESS, encoding='utf-8').read())
    fn = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == name)
    ns = {'os': os, 're': re, 'sys': sys}
    exec(compile(ast.Module(body=[fn], type_ignores=[]), PROGRESS, 'exec'), ns)
    return ns[name]


def marks():
    """The three marks the badge call gives the states, read from the source: {True: tick, False: cross, None: question mark}."""
    src = open(PROGRESS, encoding='utf-8').read()
    m = re.search(r"extra=\[\(n, (.*?)\) for n, on in status\]", src)
    expr = m.group(1)
    return {state: eval(expr, {}, {'on': state}) for state in (True, False, None)}


def run(statuses, text):
    tmp = tempfile.mkdtemp()
    p = os.path.join(tmp, 'status.txt')
    open(p, 'w').write(text)
    try:
        return statuses(p), None
    except SystemExit as e:
        return None, str(e)


def main():
    statuses = lift('statuses')
    bad = []
    out, err = run(statuses, '# comment\n[x] BUILDS FROM C\n\n[x] BOOTS TO MENU\n[ ] PLAYABLE\n[?] STABLE\n')
    if err or out != [('BUILDS FROM C', True), ('BOOTS TO MENU', True), ('PLAYABLE', False), ('STABLE', None)]:
        bad.append('states: expected True, True, False, None, got %s %s' % (out, err or ''))
    out, err = run(statuses, '[x] BUILDS FROM C\n[x] BOOTS TO MENU\n[x] PLAYABLE\n[?] STABLE\n')
    if err or out[-1] != ('STABLE', None):
        bad.append('order: a question mark under ticks must pass, got %s %s' % (out, err or ''))
    out, err = run(statuses, '[x] BUILDS FROM C\n[?] BOOTS TO MENU\n[x] PLAYABLE\n')
    if not err or 'PLAYABLE' not in err:
        bad.append('order: a tick under a question mark must be an error naming the tick, got %s %s' % (out, err or ''))
    out, err = run(statuses, '[x] BUILDS FROM C\n[-] BOOTS TO MENU\n')
    if not err or 'line 2' not in err:
        bad.append('syntax: an unknown mark must be an error naming its line, got %s %s' % (out, err or ''))
    mk = marks()
    if len(set(mk.values())) != 3 or mk[True] != '✅' or mk[False] != '❌' or mk[None] != '❓':
        bad.append('marks: expected tick, cross and question mark for True, False, None, got %r' % mk)
    if not bad:
        print('[status] ok: [x] / [ ] / [?] read as reached / not reached / not tested; a tick under a question mark fails; three badge marks')
        return
    sys.exit('[ERROR] status check failed:\n' + '\n'.join(bad))


if __name__ == '__main__':
    main()
