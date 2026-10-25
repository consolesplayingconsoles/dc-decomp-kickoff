#!/usr/bin/env python3
"""TOTAL TEST COVERAGE counts what is not done as 0 (scripts/tools/progress.py coverage_all). It was the instructions the cases ran of all
instructions over the functions that reached the check, so a game with 1,592 proven functions of 3,890 showed 95.0% (Zombie Revenge,
2026-10-25): the functions with no C did not count. Now every function that can be C is in the denominator, the ones without cases at 0
run, their instructions estimated as half their bytes. No game data. Stdlib only.

    check.py      coverage_all() alone, lifted from progress.py (the rest of that module needs a repo):
                    some      one function proven with 10 of 10 instructions run, two others of 40 bytes with no cases:
                              10 / (10 + 20 + 20) = 20.0%
                    none      nothing proven: 0.0%, not a division by zero
                    all       nothing unproven: the plain share of the instructions run
"""
import ast
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
PROGRESS = os.path.join(os.path.dirname(os.path.dirname(HERE)), 'scripts', 'tools', 'progress.py')


def lift(name):
    tree = ast.parse(open(PROGRESS, encoding='utf-8').read())
    fn = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == name)
    ns = {'os': os, 're': re, 'sys': sys}
    exec(compile(ast.Module(body=[fn], type_ignores=[]), PROGRESS, 'exec'), ns)
    return ns[name]


def main():
    cov = lift('coverage_all')
    got = cov([(10, 10)], [40, 40])
    assert abs(got - 20.0) < 1e-9, 'some: %r, expected 20.0' % got
    got = cov([], [40, 40])
    assert got == 0.0, 'none: %r, expected 0.0' % got
    got = cov([(30, 40), (10, 10)], [])
    assert abs(got - 80.0) < 1e-9, 'all: %r, expected 80.0' % got
    print('[progress_coverage] ok: what has no cases counts as 0 in the total test coverage')


main()
