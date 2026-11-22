#!/usr/bin/env python3
"""C that reads memory through a variable just set to a small constant (scripts/tools/common/consistency.py, low_address). Virtua Tennis
FUN_8c01219e: the stack word holding 0x8C287ACC came out of the generator as the constant 0x12, so each player's CPU flag was read from
0x26 + 4i and the CPU opponent counted as player 2: P2 paused the exhibition. Its two cases never ran that path, so the proof passed.
No compiler. Stdlib only.

    check.py      a temp repo, src/gen_a.c and src/hand.c:
                    f_comma   `(t208 = 0x12, t217 = *(int *)((t208 + 0x10)), ...)`            the VT line: reported
                    f_index   `t234 = 0x12; *(int *)((((t235 << 2) + (t234 + 0x14)) + 0x0))`  the VT loop: reported
                    f_struct  `t5 = 0x26; ((struct o4_int *)(t5))->v`                         reported
                    f_hand    as f_index, in src/hand.c                                      reported (hand-written C too)
                    f_offset  `R3 = (0x494); *(unsigned int *)((((R3 + R14) + R13) + 0x0))`  an offset into a pointer: not reported
                    f_goto    `v0_3 = (0x54);` then a label, then `*(int *)((v0_3 + 0x0))`  goto flow: not reported
                    f_value   `v0_1 = (0x8); *(int *)((v0_0 + 0x0)) = v0_1;`                 a value stored, not an address: not reported
                    f_big     `t1 = 0xC23A180; *(int *)((t1 + 0x4))`                         a real address: not reported
                    f_base    `t5 = 0x1C; *(int *)((0xC2A888C + t5))`                        an offset onto a real address: not reported
                    f_table   `t1 = 0x4; *(int *)((((t1 << 2) + 0xC247030) + 0x0))`          an index into a table: not reported
                    f_store   `*p = 1; *(int *)(p + 12)`                                      a store through p, not a value for p: not reported
                  --fix leaves every one of them where it is (reported, never dropped) and says so
"""
import unittest
from unittest import mock
import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
TOOL = os.path.join(os.path.dirname(HERE), 'scripts', 'tools', 'common', 'consistency.py')

GEN_A = """int f_comma(int a4)
{
    int t208;
    int t217;
    if ((a4 == 0) && ((t208 = 0x12, t217 = *(int *)((t208 + 0x10)), t208 = t217, t208 != 2))) {
        return 1;
    }
    return 0;
}
int f_index(int t235)
{
    int t234;
    t234 = 0x12;
    if ((*(int *)((((t235 << 2) + (t234 + 0x14)) + 0x0))) == 0) {
        return 1;
    }
    return 0;
}
int f_struct(void)
{
    int t5;
    t5 = 0x26;
    return (((struct o4_int *)(t5))->v);
}
int f_offset(int R14, int R13, int R4)
{
    int R3;
    R3 = (0x494);
    *(unsigned int *)((((R3 + R14) + R13) + 0x0)) = R4;
    return 0;
}
int f_goto(int a4)
{
    int v0_3;
    int v0_5;
    v0_3 = (0x54);
    goto L_B;
    L_A:;
    v0_5 = *(int *)((v0_3 + 0x0));
    return v0_5;
    L_B:;
    v0_3 = a4;
    goto L_A;
}
int f_value(int v0_0)
{
    int v0_1;
    v0_1 = (0x8);
    *(unsigned int *)((v0_0 + 0x0)) = v0_1;
    return 0;
}
int f_base(void)
{
    int t5;
    t5 = 0x1C;
    return *(int *)((0xC2A888C + t5));
}
int f_table(void)
{
    int t1;
    t1 = 0x4;
    return *(int *)((((t1 << 2) + 0xC247030) + 0x0));
}
int f_store(int *p)
{
    *p = 1;
    return *(int *)(p + 12);
}
int f_big(void)
{
    int t1;
    t1 = 0xC23A180;
    return *(int *)((t1 + 0x4));
}
"""
HAND = """int f_hand(int t235)
{
    int t234;
    t234 = 0x12;
    return *(int *)((((t235 << 2) + (t234 + 0x14)) + 0x0));
}
"""
NAMES = {'f_comma': 'gen_a', 'f_index': 'gen_a', 'f_struct': 'gen_a', 'f_offset': 'gen_a', 'f_goto': 'gen_a', 'f_value': 'gen_a',
         'f_big': 'gen_a', 'f_base': 'gen_a', 'f_table': 'gen_a', 'f_store': 'gen_a', 'f_hand': 'hand'}
REPORTED = ['f_comma', 'f_hand', 'f_index', 'f_struct']


def run(repo, *args):
    return subprocess.run([sys.executable, TOOL] + list(args), cwd=repo, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                          universal_newlines=True, timeout=120).stdout


def reported(out):
    line = next((l for l in out.splitlines() if l.startswith('low address')), '')
    parts = line.split(None, 3)
    return sorted(parts[3].replace(',', ' ').split()) if len(parts) > 3 else []


class TestConsistencyLowaddr(unittest.TestCase):
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

    def test_consistency_lowaddr(self):
        repo = tempfile.mkdtemp(prefix='consistency_lowaddr_')
        try:
            open(os.path.join(repo, '1ST_READ.BIN'), 'wb').write(bytes(0x200))
            open(os.path.join(repo, 'BASE'), 'w').write('8c010000\n')
            open(os.path.join(repo, 'functions.txt'), 'w').write(''.join('F %08x 16 %s\n' % (0x8c010000 + 0x20 * i, n) for i, n in enumerate(sorted(NAMES))))
            for d in ('src', 'state'):
                os.makedirs(os.path.join(repo, d))
            open(os.path.join(repo, 'src', 'gen_a.c'), 'w').write(GEN_A)
            open(os.path.join(repo, 'src', 'hand.c'), 'w').write(HAND)
            for n, stem in NAMES.items():
                os.makedirs(os.path.join(repo, 'tests', stem), exist_ok=True)
                open(os.path.join(repo, 'tests', stem, n + '.json'), 'w').write('{}')
            open(os.path.join(repo, 'tests', 'equivalent.txt'), 'w').write(''.join(n + '\n' for n in sorted(NAMES)))
            out = run(repo)
            assert reported(out) == REPORTED, 'the reads at a small constant are not the ones reported:\n' + out
            fixed = run(repo, '--fix')
            for n, stem in NAMES.items():
                assert ('int %s(' % n) in open(os.path.join(repo, 'src', stem + '.c')).read(), '--fix removed %s:\n%s' % (n, fixed)
            assert open(os.path.join(repo, 'tests', 'equivalent.txt')).read().split() == sorted(NAMES), '--fix touched the proofs:\n' + fixed
            assert all(('%s: reads memory at a constant below 0x1000' % n) in fixed for n in REPORTED), '--fix does not say what it leaves:\n' + fixed
            assert reported(run(repo)) == REPORTED, 'a second run does not report the same functions'
            print('[consistency_lowaddr] ok: C reading memory through a small constant is reported (generated and hand-written), never dropped')
        finally:
            shutil.rmtree(repo, ignore_errors=True)


if __name__ == '__main__':
    unittest.main()
