#!/usr/bin/env python3
"""The memory cap of a gen_equiv pool worker (scripts/tools/5-generated/gen_equiv/__main__.py _cap_memory). No game data. Stdlib only.

A worker's address space is capped (GEN_MEM_GB, default 4) so a function whose reading blows up gets a MemoryError instead of a worker the
kernel kills and a pool that waits for it forever. macOS refuses RLIMIT_AS (setrlimit raises ValueError "current limit exceeds maximum
limit" even with an unlimited hard limit), and every worker died on its first function. A refused cap is skipped: the run goes on as it did
before the cap existed.

    check.py      cap       an unlimited address space:                              setrlimit called once, with GEN_MEM_GB gigabytes and the hard limit
                  lower     a limit already under the cap:                           left as it is (setrlimit not called)
                  refused   the OS raises ValueError or OSError:                      no exception reaches the caller
                  env       GEN_MEM_GB=2:                                             a 2 GB cap
"""
import ast
import os
import resource
import unittest
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))
MAIN = os.path.join(os.path.dirname(HERE), 'scripts', 'tools', '5-generated', 'gen_equiv', '__main__.py')


def lift():
    """_cap_memory as a callable, without running the module (it reads a whole repo at import)"""
    with open(MAIN, encoding='utf-8') as fh:
        tree = ast.parse(fh.read())
    fn = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == '_cap_memory')
    ns = {'os': os}
    exec(compile(ast.Module(body=[fn], type_ignores=[]), MAIN, 'exec'), ns)
    return ns['_cap_memory']


INF = resource.RLIM_INFINITY


class TestCapMemory(unittest.TestCase):
    def run_cap(self, soft, hard, env=None, raises=None):
        cap = lift()
        with mock.patch.dict(os.environ, env or {}), mock.patch('resource.getrlimit', return_value=(soft, hard)), \
                mock.patch('resource.setrlimit', side_effect=raises) as setter:
            cap()
        return setter

    def test_cap(self):
        s = self.run_cap(INF, INF)
        s.assert_called_once_with(resource.RLIMIT_AS, (4 << 30, INF))

    def test_lower(self):
        self.run_cap(1 << 30, INF).assert_not_called()

    def test_refused(self):
        self.run_cap(INF, INF, raises=ValueError('current limit exceeds maximum limit'))
        self.run_cap(INF, INF, raises=OSError('refused'))

    def test_env(self):
        s = self.run_cap(INF, INF, env={'GEN_MEM_GB': '2'})
        s.assert_called_once_with(resource.RLIMIT_AS, (2 << 30, INF))


if __name__ == '__main__':
    unittest.main()
