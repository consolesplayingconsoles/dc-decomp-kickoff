#!/usr/bin/env python3
"""The generator's reader on tiny synthetic functions, no game data. Stdlib only.

    check.py        builds small SH-4 functions in a temp repo and checks what scripts/gen_equiv writes for them:
                      store    mov.l @(pc),r3 / mov #1,r2 / mov.l r2,@r3 / rts       the store `*(unsigned int *)0xC2A0000 = 0x1;`
                      ifelse   tst / bt / bra over a block (if-else, the literal pool in the middle of the code is skipped)
                      early    a branch whose one side returns (the code after it is not nested)
                      loop     a counted loop (dt / bf back): a do-while with the counter as a C variable
                      whileloop the loop whose test is at the bottom, entered by a jump to it: a while
                      nest     a loop holding an if, and a loop that returns from inside
                    and that a loop with no condition set (it cannot be told) and a loop that never ends are skipped
"""
import os
import shutil
import struct
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
SKILL = os.path.dirname(os.path.dirname(HERE))

BASE = 0x0C010000


class Asm:
    """A few SH-4 instructions, enough to write the test functions. Jumps name labels; constants go after the code."""

    def __init__(self):
        self.w = []                 # a word, or ('jump', kind, label) / ('load', register, pool name)
        self.labels = {}
        self.pools = []

    def label(self, name):
        self.labels[name] = len(self.w) * 2

    def op(self, word):
        self.w.append(word)

    def jump(self, kind, name):        # kind: 'bt' 'bf' 'bt/s' 'bf/s' 'bra'
        self.w.append(('jump', kind, name))

    def pool(self, name, value):
        self.pools.append((name, value))

    def load(self, reg, name):         # mov.l @(pool),reg
        self.w.append(('load', reg, name))

    def bytes(self):
        code = len(self.w) * 2
        where = {}
        pos = (code + 3) & ~3
        for name, _ in self.pools:
            where[name] = pos
            pos += 4
        out = b''
        for i, x in enumerate(self.w):
            at = i * 2
            if isinstance(x, tuple) and x[0] == 'load':
                x = 0xD000 | (x[1] << 8) | ((where[x[2]] - ((at + 4) & ~3)) // 4)
            elif isinstance(x, tuple):
                d = (self.labels[x[2]] - (at + 4)) // 2
                x = (0xA000 | (d & 0xFFF)) if x[1] == 'bra' else \
                    {'bt': 0x8900, 'bf': 0x8B00, 'bt/s': 0x8D00, 'bf/s': 0x8F00}[x[1]] | (d & 0xFF)
            out += struct.pack('<H', x)
        while len(out) % 4:
            out += struct.pack('<H', 0x0009)
        for _, v in self.pools:
            out += struct.pack('<I', v)
        return out


def mov_i(n, i): return 0xE000 | (n << 8) | (i & 0xFF)
def add_i(n, i): return 0x7000 | (n << 8) | (i & 0xFF)
def tst(m, n): return 0x2008 | (n << 8) | (m << 4)
def movl_st(m, n): return 0x2002 | (n << 8) | (m << 4)        # mov.l rm,@rn
def mov(m, n): return 0x6003 | (n << 8) | (m << 4)
def dt(n): return 0x4010 | (n << 8)
def cmp_ge(m, n): return 0x3003 | (n << 8) | (m << 4)
def add(m, n): return 0x300C | (n << 8) | (m << 4)
RTS, NOP = 0x000B, 0x0009
STORE = 0x0C2A0000


def fn_store():
    a = Asm()
    a.load(3, 'p'); a.op(mov_i(2, 1)); a.op(movl_st(2, 3)); a.op(RTS); a.op(NOP); a.pool('p', STORE)
    return a


def fn_ifelse():
    a = Asm()
    a.load(3, 'p'); a.op(tst(4, 4)); a.jump('bt', 'zero'); a.op(mov_i(2, 1)); a.jump('bra', 'end'); a.op(movl_st(2, 3))
    a.label('zero'); a.op(mov_i(2, 2)); a.op(movl_st(2, 3))
    a.label('end'); a.op(RTS); a.op(NOP); a.pool('p', STORE)
    return a


def fn_early():
    a = Asm()
    a.load(3, 'p'); a.op(tst(4, 4)); a.jump('bf', 'go'); a.op(RTS); a.op(NOP)
    a.label('go'); a.op(mov_i(2, 7)); a.op(movl_st(2, 3)); a.op(RTS); a.op(NOP); a.pool('p', STORE)
    return a


def fn_loop():
    a = Asm()
    a.load(3, 'p'); a.op(mov_i(2, 0))
    a.label('top'); a.op(add_i(2, 3)); a.op(dt(4)); a.jump('bf', 'top')
    a.op(movl_st(2, 3)); a.op(RTS); a.op(NOP); a.pool('p', STORE)
    return a


def fn_whileloop():
    # r1 = 0; goto test; body: *p = r1; r1 += 2; test: if (r1 < r4) goto body
    a = Asm()
    a.load(3, 'p'); a.op(mov_i(1, 0)); a.jump('bra', 'test'); a.op(NOP)
    a.label('body'); a.op(movl_st(1, 3)); a.op(add_i(1, 2))
    a.label('test'); a.op(cmp_ge(4, 1)); a.jump('bt', 'body')          # cmp/ge r4,r1 sets T when r1 >= r4: bt loops while T
    a.op(RTS); a.op(NOP); a.pool('p', STORE)
    return a


def fn_nest():
    # for (r2 = 0; r4--; ) { if (r2 & ..) ... } : a loop with an if inside and an early return
    a = Asm()
    a.load(3, 'p'); a.op(mov_i(2, 0))
    a.label('top'); a.op(tst(2, 2)); a.jump('bt', 'skip'); a.op(movl_st(2, 3))
    a.label('skip'); a.op(add_i(2, 1)); a.op(dt(4)); a.jump('bf', 'top')
    a.op(RTS); a.op(NOP); a.pool('p', STORE)
    return a


def fn_nocond():
    a = Asm()
    a.op(mov_i(4, 0)); a.op(add_i(4, 1)); a.jump('bf', 'back0')            # back0 = start
    a.op(RTS); a.op(NOP)
    a.labels['back0'] = 2
    return a


def fn_forever():
    a = Asm()
    a.label('x'); a.op(add_i(4, 1)); a.jump('bra', 'x'); a.op(NOP)
    return a


FUNCS = [('storefn', fn_store), ('ifelsefn', fn_ifelse), ('earlyfn', fn_early), ('loopfn', fn_loop),
         ('whilefn', fn_whileloop), ('nestfn', fn_nest), ('nocondfn', fn_nocond), ('foreverfn', fn_forever)]


def main():
    tmp = tempfile.mkdtemp()
    try:
        os.makedirs(os.path.join(tmp, "tools"))
        shutil.copy(os.path.join(SKILL, "scripts", "shdis.py"), os.path.join(tmp, "tools"))
        shutil.copytree(os.path.join(SKILL, "scripts", "gen_equiv"), os.path.join(tmp, "tools", "gen_equiv"))
        data = b''
        lines = []
        for name, make in FUNCS:
            code = make().bytes()
            lines.append("F %08x %d %s" % (BASE + len(data), len(code), name))
            data += code
            if len(data) % 4:
                data += struct.pack('<H', 0x0009)
        open(os.path.join(tmp, "1ST_READ.BIN"), "wb").write(data)
        open(os.path.join(tmp, "BASE"), "w").write("%08X\n" % BASE)
        open(os.path.join(tmp, "functions.txt"), "w").write("\n".join(lines) + "\n")
        script = ("import sys; sys.path.insert(0, 'tools/gen_equiv'); import gen_core, gen_drv, gen_pipe\n"
                  "for n in sys.argv[1:]:\n"
                  "    try:\n"
                  "        v = gen_pipe.variants(n, False)\n"
                  "        print('@@@@ ' + n); print(gen_drv.build(n, v[0], False)[0])\n"
                  "    except gen_core.Skip as e:\n"
                  "        print('@@@@ ' + n); print('SKIPPED ' + str(e))\n")
        out = subprocess.run([sys.executable, "-c", script] + [n for n, _ in FUNCS], cwd=tmp, stdout=subprocess.PIPE,
                             stderr=subprocess.STDOUT, universal_newlines=True).stdout
        parts = {}
        for chunk in out.split('@@@@ ')[1:]:
            name, _, text = chunk.partition('\n')
            parts[name] = text
        want = [
            ('storefn', ["*(unsigned int *)0xC2A0000 = 0x1;"]),
            ('ifelsefn', ["if (", "} else {", "= 0x1;", "= 0x2;"]),
            ('earlyfn', ["return", "= 0x7;"]),
            ('loopfn', ["do {", "} while (", "+ 0x3)"]),
            ('whilefn', ["while ("]),
            ('nestfn', ["do {", "} while (", "if ("]),
            ('nocondfn', ["SKIPPED"]),
            ('foreverfn', ["SKIPPED"]),
        ]
        bad = []
        for name, needles in want:
            text = parts.get(name, '')
            miss = [x for x in needles if x not in text]
            if miss:
                bad.append("%s: missing %s in\n%s" % (name, miss, text))
        if 'literal pool' in out:
            bad.append('unexpected')
        if not bad:
            print("[gen_equiv] ok: store, if/else, early return, do-while, while, nested loop written; "
                  "a loop without a condition and a loop that never ends are skipped")
            return
        sys.exit("[ERROR] gen_equiv check failed:\n" + "\n".join(bad) + "\n--- all output ---\n" + out)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    main()
