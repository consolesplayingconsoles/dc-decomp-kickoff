#!/usr/bin/env python3
"""The generator's reader on tiny synthetic functions, no game data. Stdlib only.

    check.py        builds small SH-4 functions in a temp repo and checks what scripts/tools/5-generated/gen_equiv writes for them:
                      store    mov.l @(pc),r3 / mov #1,r2 / mov.l r2,@r3 / rts       the store `*(unsigned int *)0xC2A0000 = 0x1;`
                      ifelse   tst / bt / bra over a block (if-else, the literal pool in the middle of the code is skipped)
                      early    a branch whose one side returns (the code after it is not nested)
                      loop     a counted loop (dt / bf back): for (;;) with a break, the counter as a C variable
                      whileloop the loop whose test is at the bottom, entered by a jump to it: for (;;) with the test as a break
                      nest     a loop holding an if, and a loop that returns from inside
                    and that a loop with no condition set (it cannot be told) is skipped and a loop that never ends is written as for (;;) with no break
                      thunk    a tail jump that touches no register takes and passes the callee's arguments (thunk_nlCloseEvent, Crazy Taxi)
                      caller   a call passes a register its callee only hands on to a call through a pointer (InitSys ->
                               nlSetIntrFunction: the dropped callback crashed the boot, Crazy Taxi)
                      copy     _slow_mvn with a constant length is a char struct assignment, not a load and a store per byte
                               (replayChangeControl: 864 bytes, Crazy Taxi)
                      defcaller a callee whose code reads one register but whose proven definition takes three gets three
                      defthunk  a tail jump to a callee that reads nothing but whose proven definition takes one: the stub takes it and passes it on
                      fptr     a float pointer parameter in a callee's definition is an integer argument (Drv_FacePsgFrame)
                      order    two call results passed to a third call: each call its own statement, in order (Drv_FacePsgFrame)
                      struct   a structure returned through a hidden pointer pushed in the delay slot, and one passed by value on
                               the stack with a single register argument (primFrameCorners, Virtua Tennis): a failing case means the tools are
                               not ready to commit
                               (the scan stops at the first return: replayChangeControl read as 1 argument for 5, Crazy Taxi)
                      stackpass / stackind / stackspill / stackclobber
                               a pushed word makes r4-r7 positional: untouched ones are the function's own incoming arguments, ones an earlier
                               call changed go as 0, and a word pushed earlier and not dropped is no argument (mwlRnaStartCopy, Virtua Tennis)
                      switch / brafcomp
                               a jump table the structured form cannot take is written by the flat form; a braf that is no table stays skipped
                      stackframe  a callee whose definition takes stack words, called with nothing pushed, gets the caller's frame at SP
                      deferred    the stack adjustment deferred past the next call: each call takes the words its callee reads from the stack
"""
import os
import re
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


def jsr(n): return 0x400B | (n << 8)
def jmp(n): return 0x402B | (n << 8)
def movl_ld(m, n): return 0x6002 | (n << 8) | (m << 4)       # mov.l @rm,rn
STS_PR, LDS_PR = 0x4F22, 0x4F26                              # sts.l pr,@-r15 / lds.l @r15+,pr
ADDR = {}                                                    # entry of each test function, filled as they are laid out


def fn_twoarg():
    # reads r5 only: two arguments (a callee for the ones below)
    a = Asm()
    a.load(3, 'p'); a.op(movl_st(5, 3)); a.op(RTS); a.op(NOP); a.pool('p', STORE)
    return a


def fn_thunk():
    # a tail jump to twoargfn touching no register: its two incoming arguments go on as they came
    a = Asm()
    a.load(1, 'f'); a.op(jmp(1)); a.op(NOP); a.pool('f', ADDR['twoargfn'])
    return a


def fn_pass():
    # reads r4 itself, then calls through a pointer read from memory with r5-r7 untouched: what the caller put there
    # goes on (a dispatcher, like nlSetIntrFunction: a scan that stops at the reads saw one argument)
    a = Asm()
    a.op(STS_PR); a.op(tst(4, 4)); a.load(1, 'p'); a.op(movl_ld(1, 2)); a.op(jsr(2)); a.op(NOP); a.op(LDS_PR); a.op(RTS); a.op(NOP)
    a.pool('p', STORE)
    return a


def fn_caller():
    # passfn(1, 7): r5 is set for the callee's callee; the call must pass it
    a = Asm()
    a.op(STS_PR); a.load(1, 'f'); a.op(mov_i(4, 1)); a.op(jsr(1)); a.op(mov_i(5, 7)); a.op(LDS_PR); a.op(RTS); a.op(NOP)
    a.pool('f', ADDR['passfn'])
    return a


def fn_slowmvn_helper():
    # stands in for the runtime's byte mover; the generator knows it by name
    a = Asm(); a.op(RTS); a.op(NOP)
    return a


def fn_copy():
    # _slow_mvn(r0 = 16 bytes, r1 = a4, r2 = a5): a block of bytes copied by the runtime helper
    a = Asm()
    a.op(STS_PR); a.load(3, 'f'); a.op(mov(4, 1)); a.op(mov(5, 2)); a.op(jsr(3)); a.op(mov_i(0, 16)); a.op(LDS_PR); a.op(RTS); a.op(NOP)
    a.pool('f', ADDR['_slow_mvn'])
    return a


def fn_onereg():
    # reads only r4 in its code; its proven C definition (src/defs.c) takes three parameters
    a = Asm()
    a.load(3, 'p'); a.op(movl_st(4, 3)); a.op(RTS); a.op(NOP); a.pool('p', STORE)
    return a


def fn_defcaller():
    # threearg(1, 2, 3): the definition's count wins over the scan
    a = Asm()
    a.op(STS_PR); a.load(1, 'f'); a.op(mov_i(4, 1)); a.op(mov_i(5, 2)); a.op(jsr(1)); a.op(mov_i(6, 3)); a.op(LDS_PR); a.op(RTS); a.op(NOP)
    a.pool('f', ADDR['threearg'])
    return a


def fn_ret():
    a = Asm(); a.op(RTS); a.op(NOP)
    return a


def fn_passdef():
    # itself a tail jump to onefn touching no register, so its code reads nothing; its proven definition (DEFS_C) takes a4
    a = Asm()
    a.load(1, 'f'); a.op(jmp(1)); a.op(NOP); a.pool('f', ADDR['onefn'])
    return a


def fn_defthunk():
    # a tail jump to passdef touching no register: the callee's code reads nothing, its definition takes one argument, so the
    # stub takes it and passes it on (mpdrv_set_hreset -> mpdrv_set_hreset_ns, Virtua Tennis: `return f();` against `f(int a4)`
    # is SHC's "Scalar required for !", 32 functions)
    a = Asm()
    a.load(1, 'f'); a.op(jmp(1)); a.op(NOP); a.pool('f', ADDR['passdef'])
    return a


def fn_structret():
    # returns a structure: the caller's pushed word (the first stack argument, at @(0,r15) on entry) is where it goes
    a = Asm()
    a.op(0x51F0); a.op(movl_st(4, 1)); a.op(RTS); a.op(NOP)       # mov.l @(0,r15),r1 / mov.l r4,@r1
    return a


def fn_struct():
    # SHC's structures on the stack (primFrameCorners, Virtua Tennis): vecmk returns a structure through a hidden pointer the
    # caller pushes in the delay slot; vsetfn(p, v) takes p in r4 and the structure by value as a word on the stack
    a = Asm()
    a.op(STS_PR); a.op(0x7FF0)                                   # add #-16,r15: room for the returned structure
    a.load(13, 'mk'); a.op(jsr(13)); a.op(0x2FF6)                # jsr vecmk / mov.l r15,@-r15 (the hidden pointer)
    a.op(0x7F04)                                                 # add #4,r15
    a.load(2, 'set'); a.op(mov_i(3, 9)); a.op(jsr(2)); a.op(0x2F36)    # jsr vsetfn / mov.l r3,@-r15 (one word by value), p in r4
    a.op(0x7F04); a.op(0x7F10)                                   # add #4,r15 / add #16,r15
    a.op(LDS_PR); a.op(RTS); a.op(NOP)
    a.pool('mk', ADDR['vecmk']); a.pool('set', ADDR['vsetfn'])
    return a


def fn_fivecall():
    # five(1, 2, 3, 4, 9): four register arguments and the fifth pushed on the stack in the delay slot (what works today)
    a = Asm()
    a.op(STS_PR); a.load(1, 'five'); a.op(mov_i(4, 1)); a.op(mov_i(5, 2)); a.op(mov_i(6, 3)); a.op(mov_i(7, 4)); a.op(mov_i(3, 9))
    a.op(jsr(1)); a.op(0x2F36)                                   # jsr five / mov.l r3,@-r15 (the fifth argument)
    a.op(0x7F04); a.op(LDS_PR); a.op(RTS); a.op(NOP)             # add #4,r15
    a.pool('five', ADDR['fivefn'])
    return a


def fn_structarg():
    # ptfn(5, p): a 12-byte point built in the frame, copied to the outgoing stack by the byte mover, then the call with one register
    # argument (gdc_CourseStartLoadReq -> gdc_CoursePointLoadReq, Psg_Execute -> Start_Proposal, Crazy Taxi). The generated C copied
    # the point into its own frame array one word off and called ptfn(0x5) with nothing on the stack
    a = Asm()
    a.op(STS_PR); a.op(0x7FF4)                                   # add #-12,r15: the point
    a.op(0x2F42); a.op(0x1F51); a.op(0x1F62)                     # mov.l r4,@r15 / r5,@(4,r15) / r6,@(8,r15)
    a.op(0x62F3); a.op(0xE00C); a.op(0x3F08)                     # mov r15,r2 / mov #12,r0 / sub r0,r15: the outgoing area
    a.load(3, 'm'); a.op(jsr(3)); a.op(0x61F3)                   # _slow_mvn(r0 = 12, r1 = sp, r2 = the point)
    a.load(1, 'f'); a.op(jsr(1)); a.op(0xE405)                   # ptfn, mov #5,r4 in the delay slot
    a.op(0x7F0C); a.op(0x7F0C); a.op(LDS_PR); a.op(RTS); a.op(NOP)
    a.pool('m', ADDR['_slow_mvn']); a.pool('f', ADDR['ptfn'])
    return a


def fn_stackread():
    # reads only the word its caller left at the top of the stack (kmiSetVideoTimings, Crazy Taxi: a structure by value); the generated
    # definition declared r4-r7 as arguments it never reads
    a = Asm()
    a.load(3, 'p'); a.op(0x62F2); a.op(movl_st(2, 3)); a.op(RTS); a.op(NOP); a.pool('p', STORE)     # mov.l @r15,r2 / mov.l r2,@r3
    return a


def fn_retval():
    # the result of a call returned in r0, as LoadBackupData has it (Crazy Taxi; its caller warns when it is not 0): one exit
    # loads a constant and jumps past the other's "mov r14,r0" to the shared epilogue. The generated definition was void, so
    # the caller read a leftover register
    a = Asm()
    a.op(STS_PR); a.load(1, 'f'); a.op(jsr(1)); a.op(NOP)
    a.op(0x8817); a.op(0x8D03); a.op(0x6E03)                     # cmp/eq #23,r0 / bt/s (to the mov) / mov r0,r14
    a.op(0xE0FF); a.op(0xA001); a.op(NOP)                        # mov #-1,r0 / bra (past the mov) / nop
    a.op(0x60E3); a.op(LDS_PR); a.op(RTS); a.op(NOP)             # mov r14,r0 / the epilogue
    a.pool('f', ADDR['onefn'])
    return a


def fn_phantom():
    # sets and stores r6, then sets r4 and calls a one-argument callee: only registers read before they are written are parameters.
    # Every call counted as reading r4-r7, so r5-r7 looked live at entry and the definition took a4-a7; its callers were then
    # compared on leftover registers (Start_Fog, gdc_SpriteFreeMenu, hudDrawTime, Crazy Taxi)
    a = Asm()
    a.op(STS_PR); a.load(1, 'f'); a.load(3, 'p'); a.op(mov_i(6, 5)); a.op(movl_st(6, 3)); a.op(mov_i(4, 1)); a.op(jsr(1)); a.op(NOP)
    a.op(LDS_PR); a.op(RTS); a.op(NOP)
    a.pool('f', ADDR['onefn']); a.pool('p', STORE)
    return a


def fn_fivepass():
    # five(a4, 2, a6, 4, 9): the incoming r4 and r6 passed on beside set registers and a pushed word
    a = Asm()
    a.op(STS_PR); a.load(1, 'five'); a.op(mov_i(5, 2)); a.op(mov_i(7, 4)); a.op(mov_i(3, 9))
    a.op(jsr(1)); a.op(0x2F36)
    a.op(0x7F04); a.op(LDS_PR); a.op(RTS); a.op(NOP)
    a.pool('five', ADDR['fivefn'])
    return a


def fn_stackpass():
    # five(1, a5, a6, a7, 9): r4 set, r5-r7 never touched (the function's own incoming arguments), the fifth argument pushed in the delay
    # slot (mwlRnaStartCopy, serveGetPos in playerInit, Virtua Tennis). A pushed word makes all four registers positional
    a = Asm()
    a.op(STS_PR); a.load(1, 'five'); a.op(mov_i(4, 1)); a.op(mov_i(3, 9))
    a.op(jsr(1)); a.op(0x2F36)                                   # jsr five / mov.l r3,@-r15
    a.op(0x7F04); a.op(LDS_PR); a.op(RTS); a.op(NOP)             # add #4,r15
    a.pool('five', ADDR['fivefn'])
    return a


def fn_stackind():
    # the same through a pointer read from memory (a vtable call, as mwlRnaStartCopy makes): the callee's arity is not known
    a = Asm()
    a.op(STS_PR); a.load(1, 'p'); a.op(movl_ld(1, 2)); a.op(mov_i(4, 1)); a.op(mov_i(3, 9))
    a.op(jsr(2)); a.op(0x2F36)
    a.op(0x7F04); a.op(mov_i(0, 0)); a.op(LDS_PR); a.op(RTS); a.op(NOP)      # an instruction between the cleanup and the epilogue, as in the game
    a.pool('p', STORE)
    return a


def fn_stackspill():
    # a word pushed earlier and not dropped after the call is not an argument: onefn(1) takes one
    a = Asm()
    a.op(STS_PR); a.load(1, 'f'); a.op(mov_i(3, 9)); a.op(0x2F36); a.op(mov_i(4, 1)); a.op(jsr(1)); a.op(NOP)
    a.op(LDS_PR); a.op(RTS); a.op(NOP)
    a.pool('f', ADDR['voidfn'])
    return a


def fn_stackclobber():
    # an earlier call has changed r5-r7: they are no longer the function's incoming arguments but leftovers, and go as 0 in the pushed-word call
    a = Asm()
    a.op(STS_PR); a.load(1, 'one'); a.op(jsr(1)); a.op(NOP)
    a.load(1, 'five'); a.op(mov_i(4, 1)); a.op(mov_i(3, 9)); a.op(jsr(1)); a.op(0x2F36)
    a.op(0x7F04); a.op(LDS_PR); a.op(RTS); a.op(NOP)
    a.pool('one', ADDR['onefn']); a.pool('five', ADDR['fivefn'])
    return a


class Raw:
    """Words laid out by hand, for code the Asm helper cannot place (a jump table inside the code)."""

    def __init__(self, words):
        self.words = words

    def bytes(self):
        return b''.join(struct.pack('<H', w) for w in self.words)


def fn_switch():
    # switch (a4) { case 0: return 1; case 1: return 2; default: return 0; } as SHC writes it (commonLoadStep, kmySetVirticalFilterMode,
    # kmyGetDisplayParametersInfo, Virtua Tennis): bounds check, shll / mova / mov.w @(r0,r1) / braf, a table of word offsets from braf + 4
    return Raw([0x6043,                                      # mov r4,r0
                0xE102, 0x3012, 0x8B01,                      # mov #2,r1 / cmp/hs r1,r0 / bf (past the default jump)
                0xA011, NOP,                                 # bra default / nop
                0x4000, 0x6103, 0xC702,                      # shll r0 / mov r0,r1 / mova table,r0
                0x001D, 0x0023, NOP, NOP, NOP,               # mov.w @(r0,r1),r0 / braf r0 / nop / pads: the table is 4-aligned
                0x000A, 0x0010, NOP,                         # table (offsets from the braf + 4): case 0, case 1 / pad
                0xE001, RTS, NOP,                            # case 0: return 1
                0xE002, RTS, NOP,                            # case 1: return 2
                0xE000, RTS, NOP])                           # default: return 0


def fn_brafcomputed():
    # braf through a register that is no jump table (no mova / mov.w before it): a computed jump the generator cannot write
    return Raw([0x0423, NOP, RTS, NOP])                      # braf r4 / nop / rts / nop


def fn_stackframe():
    # stk4fn(): a callee whose proven definition takes four words from the stack, called with nothing pushed: it reads the caller's own frame at
    # SP, the two locals stored just before (ADXF_LoadPartition -> ADXERR_CallErrFunc, Virtua Tennis: the compared stack words were the frame's)
    a = Asm()
    a.op(STS_PR); a.op(0x7FF0)                                   # sts.l pr,@-r15 / add #-16,r15: the frame
    a.op(0x2F42); a.op(0x1F51)                                   # mov.l r4,@r15 / mov.l r5,@(4,r15): two locals
    a.load(1, 'f'); a.op(jsr(1)); a.op(NOP)                      # jsr stk4fn / nop: nothing pushed
    a.op(0x7F10); a.op(LDS_PR); a.op(RTS); a.op(NOP)             # add #16,r15
    a.pool('f', ADDR['stk4fn'])
    return a


def fn_stackframeint():
    # fivefn(0x33, a5, a6, a7, <the word at SP>): the callee's definition takes its fifth argument as a plain int past r4-r7, and the call
    # pushes nothing, so the fifth word is the caller's own frame at SP, here a6 stored there (adxf_read_sj32 -> ADXERR_CallErrFunc,
    # Crazy Taxi: the error message in r4 and the compared stack word was a6's slot)
    a = Asm()
    a.op(STS_PR); a.op(0x7FFC)                                   # sts.l pr,@-r15 / add #-4,r15: the frame
    a.op(0x2F62)                                                 # mov.l r6,@r15: a local
    a.op(mov_i(4, 0x33))                                         # mov #0x33,r4
    a.load(1, 'f'); a.op(jsr(1)); a.op(NOP)                      # jsr fivefn / nop: nothing pushed
    a.op(0x7F04); a.op(LDS_PR); a.op(RTS); a.op(NOP)             # add #4,r15
    a.pool('f', ADDR['fivefn'])
    return a


def fn_stackframeint2():
    # the same after an earlier call, with only r4 and r5 set (adxf_SetFileInfo -> ADXERR_CallErrFunc, Crazy Taxi): r6 and r7 are leftovers of
    # that call, not arguments of this one, and go as 0 (as in stackclobberfn); the fifth word is still the caller's frame at SP
    a = Asm()
    a.op(STS_PR); a.op(0x7FFC)                                   # sts.l pr,@-r15 / add #-4,r15: the frame
    a.op(0x2F62)                                                 # mov.l r6,@r15: a local
    a.load(1, 'v'); a.op(jsr(1)); a.op(NOP)                      # jsr voidfn / nop
    a.op(mov_i(4, 0x33)); a.op(mov_i(5, 5))                      # mov #0x33,r4 / mov #5,r5
    a.load(1, 'f'); a.op(jsr(1)); a.op(NOP)                      # jsr fivefn / nop: nothing pushed
    a.op(0x7F04); a.op(LDS_PR); a.op(RTS); a.op(NOP)             # add #4,r15
    a.pool('v', ADDR['voidfn']); a.pool('f', ADDR['fivefn'])
    return a


def fn_readstack2():
    # a callee that takes r4-r7 and two words from the stack: stores the four registers and the words at @r15 and @(4,r15)
    a = Asm()
    a.load(3, 'p'); a.op(movl_st(4, 3)); a.op(movl_st(5, 3)); a.op(movl_st(6, 3)); a.op(movl_st(7, 3))
    a.op(0x62F2); a.op(movl_st(2, 3)); a.op(0x52F1); a.op(movl_st(2, 3)); a.op(RTS); a.op(NOP); a.pool('p', STORE)
    return a


def fn_readstack1():
    # the same with one word from the stack
    a = Asm()
    a.load(3, 'p'); a.op(movl_st(4, 3)); a.op(movl_st(5, 3)); a.op(movl_st(6, 3)); a.op(movl_st(7, 3))
    a.op(0x62F2); a.op(movl_st(2, 3)); a.op(RTS); a.op(NOP); a.pool('p', STORE)
    return a


def fn_readframe3():
    # a callee with a frame of its own (r14 and PR pushed, a 4-byte local) that takes r4 and reads three words the caller left above it,
    # at @(12,r15), @(16,r15), @(20,r15) (sprPutAtAlpha reads the 12-byte point passed by value that way): (int a4, Stk3 s), not a8-a10
    # after phantom a5-a7
    a = Asm()
    a.op(0x2FE6); a.op(STS_PR); a.op(0x7FFC)                                   # mov.l r14,@-r15 / sts.l pr,@-r15 / add #-4,r15
    a.load(3, 'p'); a.op(movl_st(4, 3))
    a.op(0x52F3); a.op(movl_st(2, 3)); a.op(0x52F4); a.op(movl_st(2, 3)); a.op(0x52F5); a.op(movl_st(2, 3))
    a.op(0x7F04); a.op(LDS_PR); a.op(RTS); a.op(0x6EF6); a.pool('p', STORE)    # add #4,r15 / lds.l @r15+,pr / rts / mov.l @r15+,r14
    return a


def fn_readframe3p():
    # the same three words reached through a pointer into the caller's area, as sprPutAtAlpha does: `mov r15,r4 / add #12,r4`, then
    # fmov.s @r4, @(4,r4), @(8,r4) (a float register argument is in fr4 and the 12-byte point is passed by value)
    a = Asm()
    a.op(0x2FE6); a.op(STS_PR); a.op(0x7FFC)                                   # mov.l r14,@-r15 / sts.l pr,@-r15 / add #-4,r15
    a.load(2, 'p'); a.op(movl_st(4, 2))
    a.op(0x64F3); a.op(0x740C)                                                  # mov r15,r4 / add #12,r4
    a.op(0xF348); a.op(0xF23A)                                                  # fmov.s @r4,fr3 / fmov.s fr3,@r2
    a.op(0xE004); a.op(0xF346); a.op(0xF23A)                                    # mov #4,r0 / fmov.s @(r0,r4),fr3 / fmov.s fr3,@r2
    a.op(0xE008); a.op(0xF346); a.op(0xF23A)                                    # mov #8,r0 / fmov.s @(r0,r4),fr3 / fmov.s fr3,@r2
    a.op(0x7F04); a.op(LDS_PR); a.op(RTS); a.op(0x6EF6); a.pool('p', STORE)
    return a


def fn_stackonly1():
    # a callee that takes NO register argument and reads one word the caller left on the stack, in a frame of its own (vecMake: the output
    # pointer is its first stack word, r4-r7 are not read): declared as a structure by value, and a structure of one word is passed in a
    # register, not on the stack, so it must stay padded to four words (a structure SHC puts on the stack)
    a = Asm()
    a.op(STS_PR); a.op(0x7FF4)                                                  # sts.l pr,@-r15 / add #-12,r15
    a.load(3, 'p'); a.op(0x51F4); a.op(movl_st(1, 3))                           # mov.l @(16,r15),r1 / mov.l r1,@r3
    a.op(0x7F0C); a.op(LDS_PR); a.op(RTS); a.op(NOP); a.pool('p', STORE)        # add #12,r15 / lds.l @r15+,pr / rts
    return a


def fn_copyin():
    # copies the three words the caller left on the stack into a local with the word mover (hudFontNumPut, Virtua Tennis: its 12-byte
    # point is passed by value and copied with _quick_odd_mvn from sp + 60): the copy reads all three, so all three are parameters,
    # though only the copy's first address appears in the C
    a = Asm()
    a.op(0x2FE6); a.op(STS_PR); a.op(0x7FF4)                     # mov.l r14,@-r15 / sts.l pr,@-r15 / add #-12,r15: the local
    a.op(0x62F3); a.op(0x7214); a.op(0x61F3)                     # mov r15,r2 / add #20,r2 (the caller's first stack word) / mov r15,r1
    a.load(3, 'm'); a.op(jsr(3)); a.op(0xE00C)                   # _quick_odd_mvn(r0 = 12, r1 = the local, r2 = the caller's words)
    a.load(7, 'p'); a.op(movl_st(4, 7)); a.op(0x51F2); a.op(movl_st(1, 7))      # r4 and the local's third word to the store
    a.op(0x7F0C); a.op(LDS_PR); a.op(RTS); a.op(0x6EF6)          # add #12,r15 / lds.l @r15+,pr / rts / mov.l @r15+,r14
    a.pool('m', ADDR['_quick_odd_mvn']); a.pool('p', STORE)
    return a


def fn_sret():
    # returns a 12-byte structure by value (vecMake, Virtua Tennis): builds it from fr4-fr6 in a local, then copies it with the word
    # mover to the address the caller passed as its first stack word (SHC's hidden return pointer), reading no r4-r7
    a = Asm()
    a.op(STS_PR); a.op(0x7FF4); a.op(mov_i(0, 4)); a.op(0x64F3)              # sts.l pr,@-r15 / add #-12,r15 / mov #4,r0 / mov r15,r4
    a.load(3, 'm'); a.op(0x6243)                                                # mov r4,r2
    a.op(0xF44A); a.op(0xF457); a.op(mov_i(0, 8)); a.op(0xF467)                # fmov.s fr4,@r4 / fr5,@(r0,r4) / mov #8,r0 / fr6,@(r0,r4)
    a.op(0x51F4); a.op(jsr(3)); a.op(0xE00C)                                    # mov.l @(16,r15),r1 / jsr _quick_odd_mvn / mov #12,r0
    a.op(0x7F0C); a.op(LDS_PR); a.op(RTS); a.op(NOP)
    a.pool('m', ADDR['_quick_odd_mvn'])
    return a


def fn_sretcall():
    # v = sretdef(1.0f, 0.0f, 1.0f) into a local, then v's first word stored (mtxGetPos, Virtua Tennis): the local's address is pushed alone
    # in the delay slot, r4-r7 untouched. sretdef's definition returns Stk3: the call is an assignment of the structure, with no
    # register integers (they were passed as phantom a4..a6 and compared at every caller)
    a = Asm()
    a.op(STS_PR); a.op(0x7FF0)                                                  # add #-16,r15
    a.op(0xF49D); a.op(0xF58D); a.op(0xF69D)                                    # fldi1 fr4 / fldi0 fr5 / fldi1 fr6
    a.op(0x62F3); a.op(0x7204)                                                  # mov r15,r2 / add #4,r2: the local
    a.load(3, 'f'); a.op(jsr(3)); a.op(0x2F26)                                  # jsr sretdef / mov.l r2,@-r15
    a.op(0x7F04); a.op(0x51F1)                                                  # add #4,r15 / mov.l @(4,r15),r1
    a.load(7, 'p'); a.op(movl_st(1, 7))
    a.op(0x7F10); a.op(LDS_PR); a.op(RTS); a.op(NOP)
    a.pool('f', ADDR['sretdef']); a.pool('p', STORE)
    return a


def fn_sretcallp():
    # *p = sretdef(1.0f, 0.0f, 1.0f) with p the function's own r4: the pushed word is a pointer the caller holds, not a local's address
    a = Asm()
    a.op(STS_PR); a.op(0xF49D); a.op(0xF58D); a.op(0xF69D)                     # fldi1 fr4 / fldi0 fr5 / fldi1 fr6
    a.op(0x6243)                                                                # mov r4,r2
    a.load(3, 'f'); a.op(jsr(3)); a.op(0x2F26)                                  # jsr sretdef / mov.l r2,@-r15
    a.op(0x7F04); a.op(LDS_PR); a.op(RTS); a.op(NOP)                            # add #4,r15
    a.pool('f', ADDR['sretdef'])
    return a


def fn_argupdate():
    # adds 1.0f to the first word of the 12-byte point it was passed by value, writing it back into its own argument area, then passes
    # the point on to ptfn by copying those 12 bytes (hudSignFirstPut, Virtua Tennis): the copy must see the updated word. The store was
    # kept in a C variable only, and the frame array the copy reads still held the caller's value
    a = Asm()
    a.op(STS_PR); a.op(mov_i(0, 4)); a.op(0xF2F6)                               # sts.l pr,@-r15 / mov #4,r0 / fmov.s @(r0,r15),fr2
    a.op(0xF39D); a.op(0xF230); a.op(0xFF27)                                    # fldi1 fr3 / fadd fr3,fr2 / fmov.s fr2,@(r0,r15)
    a.op(0x62F3); a.op(0x7204); a.op(0xE00C); a.op(0x3F08)                      # mov r15,r2 / add #4,r2 / mov #12,r0 / sub r0,r15
    a.load(3, 'm'); a.op(jsr(3)); a.op(0x61F3)                                  # _quick_odd_mvn(12, sp, the point)
    a.load(2, 'f'); a.op(jsr(2)); a.op(0xE405)                                  # ptfn(5, the point)
    a.op(0x7F0C); a.op(LDS_PR); a.op(RTS); a.op(NOP)
    a.pool('m', ADDR['_quick_odd_mvn']); a.pool('f', ADDR['ptfn'])
    return a


def fn_argnarrow():
    # stores a short into the upper half of the first word of the point it was passed by value (mov.w into its own argument area;
    # cameraExec cases 5, 6 and 9, Virtua Tennis, a short at sp+42), reads it back with mov.w, then passes the point on: the read sees
    # the short, the copy sees the merged word. The reader stopped: a store into the caller frame other than a whole word
    a = Asm()
    a.op(STS_PR); a.op(mov_i(1, 7)); a.op(mov_i(0, 6)); a.op(0x0F15)            # sts.l pr,@-r15 / mov #7,r1 / mov #6,r0 / mov.w r1,@(r0,r15)
    a.op(0x04FD)                                                                # mov.w @(r0,r15),r4 (the short back, for ptfn's first argument)
    a.op(0x62F3); a.op(0x7204); a.op(0xE00C); a.op(0x3F08)                      # mov r15,r2 / add #4,r2 / mov #12,r0 / sub r0,r15
    a.load(3, 'm'); a.op(jsr(3)); a.op(0x61F3)                                  # _quick_odd_mvn(12, sp, the point)
    a.load(2, 'f'); a.op(jsr(2)); a.op(NOP)                                     # ptfn(the short, the point)
    a.op(0x7F0C); a.op(LDS_PR); a.op(RTS); a.op(NOP)
    a.pool('m', ADDR['_quick_odd_mvn']); a.pool('f', ADDR['ptfn'])
    return a


def fn_constfirst():
    # reads the caller's first stack word through r1 = 4 + r15, the constant first (bodyInit, Virtua Tennis: its hidden return pointer at
    # @(0x32C + sp)), and stores a4 through it: the word must be a stack parameter, though the address reads constant + (stk + n)
    a = Asm()
    a.op(STS_PR); a.op(0x62F3)                                                  # sts.l pr,@-r15 / mov r15,r2 (a frame)
    a.op(mov_i(1, 4)); a.op(0x31FC); a.op(0x6112); a.op(0x2142)                 # mov #4,r1 / add r15,r1 / mov.l @r1,r1 / mov.l r4,@r1
    a.op(LDS_PR); a.op(RTS); a.op(NOP)
    return a


def fn_twostruct():
    # twoptfn(a, b) with two 12-byte points by value (cpuLineXAtZ's callers, Virtua Tennis): SHC copies b to the outgoing area first, then
    # a below it. Only the last copy was kept as the call's structure argument, so b was dropped and the check compared its words
    a = Asm()
    a.op(STS_PR); a.op(0x7FE8)                                                  # sts.l pr,@-r15 / add #-24,r15: a at sp, b at sp+12
    a.op(0x62F3); a.op(0x720C); a.op(0xE00C); a.op(0x3F08)                      # r2 = b / mov #12,r0 / sub r0,r15
    a.load(3, 'm'); a.op(jsr(3)); a.op(0x61F3)                                  # _quick_odd_mvn(12, sp, b)
    a.op(0x62F3); a.op(0x720C); a.op(0xE00C); a.op(0x3F08)                      # r2 = a (now at sp+12) / sub #12 again
    a.load(3, 'm'); a.op(jsr(3)); a.op(0x61F3)                                  # _quick_odd_mvn(12, sp, a)
    a.load(1, 'f'); a.op(jsr(1)); a.op(NOP)
    a.op(0x7F18); a.op(0x7F18); a.op(LDS_PR); a.op(RTS); a.op(NOP)              # add #24,r15 twice
    a.pool('m', ADDR['_quick_odd_mvn']); a.pool('f', ADDR['twoptfn'])
    return a


def fn_pushstruct():
    # ptintfn(1, 2, 3, 4, a point by value, 5): r4-r7 full, so the point and the int go on the stack; SHC pushes the int first, then
    # copies the point below it (winDrawA -> winPartsPut, Virtua Tennis: the push was taken as a spill, a callee with four integer
    # registers and no cleanup the reader saw, and dropped: the callee's fourth stack word was compared on a leftover)
    a = Asm()
    a.op(STS_PR); a.op(0x7FF4)                                                  # sts.l pr,@-r15 / add #-12,r15: a local point at sp
    a.op(0x62F3); a.op(mov_i(1, 5)); a.op(0x2F16)                               # mov r15,r2 (the point) / mov #5,r1 / mov.l r1,@-r15
    a.op(0xE00C); a.op(0x3F08)                                                  # mov #12,r0 / sub r0,r15
    a.load(3, 'm'); a.op(jsr(3)); a.op(0x61F3)                                  # _quick_odd_mvn(12, sp, the point)
    a.op(mov_i(4, 1)); a.op(mov_i(5, 2)); a.op(mov_i(6, 3)); a.op(mov_i(7, 4))  # r4-r7 = 1, 2, 3, 4
    a.load(1, 'f'); a.op(jsr(1)); a.op(NOP)                                     # ptintfn(1, 2, 3, 4, the point, 5)
    a.op(0x7F10); a.op(0x7F0C); a.op(LDS_PR); a.op(RTS); a.op(NOP)              # add #16,r15 / add #12,r15
    a.pool('m', ADDR['_quick_odd_mvn']); a.pool('f', ADDR['ptintfn'])
    return a


def fn_retptrpush():
    # retvecfn(Stk4: the result pointer, then a point): the point copied to SP, the result pointer pushed in the call's delay slot
    # (hudFadeNearPlayers -> camWorldToView, footMarkCheck -> vecSub, Virtua Tennis): a callee reading no register takes the push for a
    # spill, and the C read the structure from a frame slot the push never reached: word 0 was 0, the original's a pointer
    a = Asm()
    a.op(STS_PR); a.op(0x7FE8)                                                  # sts.l pr,@-r15 / add #-24,r15: result at sp, point at sp+12
    a.op(0x62F3); a.op(0x720C); a.op(0xE00C); a.op(0x3F08)                      # r2 = the point / mov #12,r0 / sub r0,r15
    a.load(3, 'm'); a.op(jsr(3)); a.op(0x61F3)                                  # _quick_odd_mvn(12, sp, the point)
    a.op(0x6EF3); a.op(0x7E0C)                                                  # mov r15,r14 / add #12,r14: the result
    a.load(1, 'f'); a.op(jsr(1)); a.op(0x2FE6)                                  # retvecfn(...) with mov.l r14,@-r15 in the delay slot
    a.op(0x7F10); a.op(0x7F18); a.op(LDS_PR); a.op(RTS); a.op(NOP)              # add #16,r15 / add #24,r15
    a.pool('m', ADDR['_quick_odd_mvn']); a.pool('f', ADDR['retvecfn'])
    return a


def fn_retptrpush2():
    # the same with the point's destination not read as SP (a loop's register variable in hudFadeNearPlayers, Virtua Tennis): the call
    # reads its structure from the frame at SP, where the pushed word must be too
    a = Asm()
    a.op(STS_PR); a.op(0x7FE8)                                                  # sts.l pr,@-r15 / add #-24,r15
    a.op(0x62F3); a.op(0x720C); a.op(0xE00C); a.op(0x3F08)                      # r2 = the point / mov #12,r0 / sub r0,r15
    a.op(0x61F3); a.op(0x7100)                                                  # mov r15,r1 / add #0,r1
    a.load(3, 'm'); a.op(jsr(3)); a.op(NOP)                                     # _quick_odd_mvn(12, r1, the point)
    a.op(0x6EF3); a.op(0x7E0C)                                                  # mov r15,r14 / add #12,r14: the result
    a.load(1, 'f'); a.op(jsr(1)); a.op(0x2FE6)                                  # retvecfn(...) with mov.l r14,@-r15 in the delay slot
    a.op(0x7F10); a.op(0x7F18); a.op(LDS_PR); a.op(RTS); a.op(NOP)
    a.pool('m', ADDR['_quick_odd_mvn']); a.pool('f', ADDR['retvecfn'])
    return a


def fn_intstackmix():
    # bodyfn(1, 2, 3, 4, a8..a11) with fr4 set: its four stack words, taken as plain ints past a7, are a pointer pushed in the call's
    # delay slot below a point copied to SP (miniTargetInit -> bodyCreate, Virtua Tennis: the C passed the pointer alone and
    # left the other words to chance, since the frame path refused a call with a word pushed, a copy to SP or a float register set)
    a = Asm()
    a.op(STS_PR); a.op(0x7FE8)                                                  # sts.l pr,@-r15 / add #-24,r15: a point at sp+12
    a.op(0x62F3); a.op(0x720C); a.op(0xE00C); a.op(0x3F08)                      # r2 = the point / mov #12,r0 / sub r0,r15
    a.load(3, 'm'); a.op(jsr(3)); a.op(0x61F3)                                  # _quick_odd_mvn(12, sp, the point)
    a.op(mov_i(4, 1)); a.op(mov_i(5, 2)); a.op(mov_i(6, 3)); a.op(mov_i(7, 4))  # r4-r7 = 1, 2, 3, 4
    a.op(0xF48D)                                                                # fldi0 fr4
    a.op(0x6EF3); a.op(0x7E0C)                                                  # mov r15,r14 / add #12,r14
    a.load(1, 'f'); a.op(jsr(1)); a.op(0x2FE6)                                  # bodyfn(...) with mov.l r14,@-r15 in the delay slot
    a.op(0x7F10); a.op(0x7F18); a.op(LDS_PR); a.op(RTS); a.op(NOP)
    a.pool('m', ADDR['_quick_odd_mvn']); a.pool('f', ADDR['bodyfn'])
    return a


def fn_intstackshort():
    # body3fn(1, 2, 3, 4, a8, a9, a10): a pointer pushed in the delay slot below three shorts copied to SP with the byte mover (6
    # bytes, 8 reserved: r0 = 8 - 2), miniTargetInit -> bodyCreate. A copy of less than 8 bytes, or of part of a word, was not taken
    # for a structure at SP, so the words at SP did not add up to what the definition takes and the C passed the pointer alone
    a = Asm()
    a.op(STS_PR); a.op(0x7FF8)                                                  # sts.l pr,@-r15 / add #-8,r15: the shorts at sp
    a.op(0x62F3); a.op(0xE008); a.op(0x3F08)                                    # mov r15,r2 / mov #8,r0 / sub r0,r15
    a.load(3, 's'); a.op(0x70FE); a.op(jsr(3)); a.op(0x61F3)                    # add #-2,r0 / _slow_mvn(6, sp, the shorts)
    a.op(mov_i(4, 1)); a.op(mov_i(5, 2)); a.op(mov_i(6, 3)); a.op(mov_i(7, 4))  # r4-r7 = 1, 2, 3, 4
    a.op(0x6EF3); a.op(0x7E08)                                                  # mov r15,r14 / add #8,r14
    a.load(1, 'f'); a.op(jsr(1)); a.op(0x2FE6)                                  # body3fn(...) with mov.l r14,@-r15 in the delay slot
    a.op(0x7F0C); a.op(0x7F08); a.op(LDS_PR); a.op(RTS); a.op(NOP)
    a.pool('s', ADDR['_slow_mvn']); a.pool('f', ADDR['body3fn'])
    return a


def fn_selfcall():
    # selfcallfn(p, a, b) calls voidfn, then itself with p->next only (fr4 and fr5 are the earlier call's leftovers): the definition
    # (int, float, float) is the call's prototype in the same file, so the shorter call did not compile ("Scalar required", Virtua
    # Tennis sklDrawNodeTrnsl, playerSolveArmReach, playerDrawNodeFacing). The call goes through a cast with the arguments it set, as
    # for a callee declared two ways
    a = Asm()
    a.op(STS_PR); a.op(0x6E43); a.op(0xF450); a.op(0x2448); a.op(0x8906)       # sts.l pr / mov r4,r14 / fadd fr5,fr4 / tst r4,r4 / bt end
    a.load(3, 'v'); a.op(jsr(3)); a.op(NOP)                                     # voidfn()
    a.op(0x54E1)                                                                # mov.l @(4,r14),r4
    a.load(1, 'f'); a.op(jsr(1)); a.op(NOP)                                     # selfcallfn(p->next)
    a.op(LDS_PR); a.op(RTS); a.op(NOP)                                          # end
    a.pool('v', ADDR['voidfn']); a.pool('f', ADDR['selfcallfn'])
    return a

def fn_phantomstk():
    # a callee that reads r4 and three words its caller left on the stack, and not r5-r7 (sprPutAtAlpha, Virtua Tennis: a sprite and a
    # point by value). Declared int a4, a5, a6, a7, a8, a9, a10, its callers were compared on phantom r5-r7 and had to set them (decoNumDraw
    # was never drawn: "arg gap"). The stack words are one structure by value after the registers read: (int a4, Stk3 s)
    a = Asm()
    a.load(3, 'p'); a.op(movl_st(4, 3))                                         # *p = a4
    a.op(0x62F2); a.op(movl_st(2, 3)); a.op(0x52F1); a.op(movl_st(2, 3))        # the stack words at @r15, @(4,r15), @(8,r15)
    a.op(0x52F2); a.op(movl_st(2, 3)); a.op(RTS); a.op(NOP); a.pool('p', STORE)
    return a


def fn_phantomstkf():
    # the same in a frame of its own (sts.l pr, add #-4): the words are read above the frame
    a = Asm()
    a.op(STS_PR); a.op(0x7FFC)                                                  # sts.l pr,@-r15 / add #-4,r15
    a.load(3, 'p'); a.op(movl_st(4, 3))
    a.op(0x52F2); a.op(movl_st(2, 3)); a.op(0x52F3); a.op(movl_st(2, 3)); a.op(0x52F4); a.op(movl_st(2, 3))   # @(8..16,r15): the caller's words
    a.op(0x7F04); a.op(LDS_PR); a.op(RTS); a.op(NOP); a.pool('p', STORE)
    return a


def fn_varreads1():
    # a variadic print's body: reads only its first stack word (the format) directly, the rest through a pointer
    a = Asm()
    a.op(0x60F2); a.op(RTS); a.op(NOP)                                          # mov.l @r15,r0 / rts / nop
    return a


def fn_varpush3():
    # varpdef(fmt, x, y) with three words pushed (ADXT_StartAfs -> ADXERR_CallErrFunc, Virtua Tennis): the callee's code reads one word
    # directly, its definition in src/ takes three (Stk3). The pushed words were cut to the one the code reads, so x and y were dropped
    a = Asm()
    a.op(STS_PR)
    a.op(mov_i(1, 3)); a.op(0x2F16); a.op(mov_i(1, 2)); a.op(0x2F16)            # push 3, push 2
    a.load(3, 'f'); a.op(jsr(3)); a.op(0x2F16)                                  # jsr varpdef / mov.l r1,@-r15 (r1 = 2 again: the format word)
    a.op(0x7F0C); a.op(LDS_PR); a.op(RTS); a.op(NOP)                            # add #12,r15
    a.pool('f', ADDR['varpdef'])
    return a


def fn_fmerge():
    # fr15 (saved by the prologue) set in one arm only and stored after the merge (uiPanelPut, cursorBoxPut, Virtua Tennis): a C local
    # assigned in some branches and read after them. The reader stopped with "read fr15"; integer registers already became such a local
    a = Asm()
    a.op(0xFFFB); a.load(3, 'p'); a.op(tst(4, 4)); a.jump('bt', 'skip')        # fmov.s fr15,@-r15 / r3 = the store / tst r4,r4 / bt skip
    a.op(0xFF9D)                                                                # fldi1 fr15
    a.label('skip'); a.op(0xF3FA)                                               # fmov.s fr15,@r3
    a.op(0xFFF9); a.op(RTS); a.op(NOP); a.pool('p', STORE)                      # fmov.s @r15+,fr15 / rts / nop
    return a


def fn_fcarry():
    # fr15 set in one round of a loop and read in the next (uiPanelPut: r12 == 1 keeps a value in fr15, r12 == 2 uses it): on the path that
    # reads it first nothing wrote it. An integer register there became an uninitialised local; a float one stopped the reader
    a = Asm()
    a.op(0xFFFB); a.load(3, 'p'); a.op(mov_i(1, 2))                             # save fr15 / r3 = the store / mov #2,r1
    a.label('top'); a.op(0x6013); a.op(0x8802); a.jump('bf', 'second')          # mov r1,r0 / cmp/eq #2,r0 / bf second
    a.op(0xFF9D); a.jump('bra', 'next'); a.op(NOP)                              # fldi1 fr15 / bra next
    a.label('second'); a.op(0xF3FA)                                             # fmov.s fr15,@r3
    a.label('next'); a.op(0x4110); a.jump('bf', 'top')                          # dt r1 / bf top
    a.op(0xFFF9); a.op(RTS); a.op(NOP); a.pool('p', STORE)
    return a


def fn_fslot():
    # writes 1.0f into its own first stack-argument slot on one arm only, then reads the slot back as a float (sprPutCropH, Virtua Tennis:
    # "float stack argument slot written in one arm"): the integer form of this was a variable already, the float one stopped the reader
    a = Asm()
    a.load(3, 'p'); a.op(tst(4, 4)); a.jump('bt', 'skip')
    a.op(0xF39D); a.op(0xFF3A)                                                  # fldi1 fr3 / fmov.s fr3,@r15 (the first stack-argument slot)
    a.label('skip'); a.op(0xF2F8); a.op(0xF32A)                                 # fmov.s @r15,fr2 / fmov.s fr2,@r3
    a.op(RTS); a.op(NOP); a.pool('p', STORE)
    return a


def fn_fspill():
    # a float pushed, then a call that takes a pushed hidden pointer, then the float popped (cpuDblReceivePos, Virtua Tennis: fmov.s
    # fr0,@-r15, a struct-returning call through r11 with r15 pushed, add #4, fmov.s @r15+,fr1): the call took the pending pushes and the
    # pop found nothing. The value popped must be the one pushed, read back from its frame slot, not an uninitialised local
    a = Asm()
    a.op(STS_PR); a.op(0x62F3); a.op(0xF09D); a.op(0xFF0B)                      # sts.l pr / mov r15,r2 (a frame) / fldi1 fr0 / fmov.s fr0,@-r15
    a.op(0x7FF4); a.load(1, 'f'); a.op(jsr(1)); a.op(0x2FF6)                    # add #-12,r15 / jsr / mov.l r15,@-r15 (a hidden pointer)
    a.op(0x7F04); a.op(0x7F0C)                                                  # add #4,r15 / add #12,r15
    a.op(0xF1F9); a.load(3, 'p'); a.op(0xF31A)                                  # fmov.s @r15+,fr1 / r3 = the store / fmov.s fr1,@r3
    a.op(LDS_PR); a.op(RTS); a.op(NOP)
    a.pool('f', ADDR['readstack1']); a.pool('p', STORE)
    return a


def fn_stkreads2():
    # a callee that reads only two words from the stack, no r4-r7 (courtDrawStageModels)
    a = Asm()
    a.load(3, 'p'); a.op(0x62F2); a.op(movl_st(2, 3)); a.op(0x52F1); a.op(movl_st(2, 3)); a.op(RTS); a.op(NOP); a.pool('p', STORE)
    return a


def fn_framestk():
    # a call whose stack words are written through the frame (no push) to a callee that reads only stack words, with r4 and r5 set
    # (FUN_8c0c486c and 15 others -> courtDrawStageModels, Virtua Tennis): r4-r7 come before the stack words, so they are the first
    # arguments as set. They were trimmed to the registers the callee's code reads (none) and passed as 0
    a = Asm()
    a.op(STS_PR); a.op(0x7FF8)
    a.load(2, 'g'); a.op(jsr(2)); a.op(NOP)                                     # an earlier call (the real caller made two)
    a.op(mov_i(1, 7)); a.op(0x2F12); a.op(0x1F11)                               # mov #7,r1 / mov.l r1,@r15 / mov.l r1,@(4,r15)
    a.op(mov_i(4, 5)); a.op(mov_i(5, 6))                                        # r4 = 5, r5 = 6
    a.load(3, 'f'); a.op(jsr(3)); a.op(NOP)
    a.op(0x7F08); a.op(LDS_PR); a.op(RTS); a.op(NOP)
    a.pool('f', ADDR['stkreads2']); a.pool('g', ADDR['onefn'])
    return a


def fn_deferred():
    # two calls whose pushed words are dropped together after the second (SHC defers the stack adjustment: motionSet then motionRootFirst in
    # playerInit, Virtua Tennis): rs2(1, 2, 3, 4, 8, 9) pushes two words, rs1(5, 6, 7, 8, 7) pushes one, then one add #12,r15
    a = Asm()
    a.op(STS_PR); a.load(1, 'two'); a.load(13, 'one')
    a.op(mov_i(3, 9)); a.op(0x2F36); a.op(mov_i(3, 8)); a.op(0x2F36)             # push 9, push 8 (8 is the first stack argument)
    a.op(mov_i(4, 1)); a.op(mov_i(5, 2)); a.op(mov_i(6, 3)); a.op(mov_i(7, 4))
    a.op(jsr(1)); a.op(NOP)
    a.op(mov_i(3, 7)); a.op(0x2F36)
    a.op(mov_i(4, 5)); a.op(mov_i(5, 6)); a.op(mov_i(6, 7)); a.op(mov_i(7, 8))
    a.op(jsr(13)); a.op(NOP)
    a.op(0x7F0C); a.op(LDS_PR); a.op(RTS); a.op(NOP)                             # add #12,r15
    a.pool('two', ADDR['readstack2']); a.pool('one', ADDR['readstack1'])
    return a


def fn_spsteploop():
    # structargfn inside a counted loop (hudFontNumPut, crowdAnimModel, shopDrawPrice, Virtua Tennis: "stack pointer step"): a 12-byte point is
    # copied to the outgoing area by `mov #12,r0 / sub r0,r15`, the register holding a constant that the loop's join may have made unknown
    a = Asm()
    a.op(0x2FE6); a.op(STS_PR); a.op(0x7FF4)                     # mov.l r14,@-r15 / sts.l pr,@-r15 / add #-12,r15: the point
    a.op(mov_i(14, 2)); a.op(mov_i(0, 0))                        # two rounds; r0 is read at the top of the loop, so the loop carries it
    a.label('top')
    a.op(0x2F02)                                                 # mov.l r0,@r15: the carried r0 (it is 12 from the second round on)
    a.op(0x2F42); a.op(0x1F51); a.op(0x1F62)                     # mov.l r4,@r15 / r5,@(4,r15) / r6,@(8,r15)
    a.op(0x62F3); a.op(0xE00C); a.op(0x3F08)                     # mov r15,r2 / mov #12,r0 / sub r0,r15: the outgoing area
    a.load(3, 'm'); a.op(jsr(3)); a.op(0x61F3)                   # _slow_mvn(r0 = 12, r1 = sp, r2 = the point)
    a.load(1, 'f'); a.op(jsr(1)); a.op(0xE405)                   # ptfn(5, the point), mov #5,r4 in the delay slot
    a.op(0x7F0C)                                                 # add #12,r15: the outgoing area is dropped
    a.op(dt(14)); a.jump('bf', 'top')
    a.op(0x7F0C); a.op(LDS_PR); a.op(RTS); a.op(0x6EF6)          # add #12,r15 / lds.l @r15+,pr / rts / mov.l @r15+,r14
    a.pool('m', ADDR['_slow_mvn']); a.pool('f', ADDR['ptfn'])
    return a


def fn_structreuse():
    # spsteploopfn with the copy's source register reused for the call target, as SHC does (hudFontNumPut, Virtua Tennis): the byte mover
    # takes the point from r2, then `mov.l @(pool),r2 / jsr @r2` calls ptfn through the same register. In the loop form the registers are
    # C variables, and the structure argument was written as *(Stk3 *)(<r2's variable>) at the call, by which time it held ptfn's address:
    # the call passed ptfn's own code bytes as the point. The structure passed is the copy in the outgoing area, not whatever r2 holds later
    a = Asm()
    a.op(0x2FE6); a.op(STS_PR); a.op(0x7FF4)                     # mov.l r14,@-r15 / sts.l pr,@-r15 / add #-12,r15: the point
    a.op(0x6EF3)                                                 # mov r15,r14: the point's address, kept in a saved register (SHC: r14 = sp + 60)
    a.op(mov_i(13, 2)); a.op(mov_i(0, 0)); a.op(mov_i(2, 0))
    a.label('top')
    a.op(0x2F02)
    a.load(7, 'p'); a.op(movl_st(2, 7))                          # r2 read at the top of the loop: the loop carries it, so it is a C variable
    a.op(0x2F42); a.op(0x1F51); a.op(0x1F62)                     # the point from r4-r6
    a.op(0x62E3); a.op(0xE00C); a.op(0x3F08)                     # mov r14,r2 / mov #12,r0 / sub r0,r15
    a.load(3, 'm'); a.op(jsr(3)); a.op(0x61F3)                   # _slow_mvn(r0 = 12, r1 = sp, r2 = the point)
    a.load(2, 'f'); a.op(jsr(2)); a.op(0xE405)                   # mov.l @(pool),r2 / jsr @r2: ptfn through r2, mov #5,r4 in the slot
    a.op(0x7F0C)
    a.op(dt(13)); a.jump('bf', 'top')
    a.op(0x7F0C); a.op(LDS_PR); a.op(RTS); a.op(0x6EF6)
    a.pool('m', ADDR['_quick_odd_mvn']); a.pool('f', ADDR['ptfn']); a.pool('p', STORE)
    return a


def fn_floatstack():
    # reads the float the caller left on the stack as its first stack argument (cpuInRange, Virtua Tennis: "stack argument read"): two
    # registers saved, so the word is at @(8,r15), loaded with r0 as the offset, then stored through r5
    a = Asm()
    a.op(0x2FE6); a.op(0x2FD6)                                   # mov.l r14,@-r15 / mov.l r13,@-r15
    a.op(mov_i(0, 8)); a.op(0xF4F6)                              # mov #8,r0 / fmov.s @(r0,r15),fr4
    a.op(0xF54A)                                                 # fmov.s fr4,@r5
    a.op(0x6DF6); a.op(RTS); a.op(0x6EF6)                        # mov.l @r15+,r13 / rts / mov.l @r15+,r14
    return a


def fn_varcall():
    # printfn(0x33, 5, 7), a variadic call as SHC writes it (nlPrintf in replayChangeControl, Crazy Taxi): every argument pushed,
    # the last one first and the format in the delay slot, nothing in r4-r7; the caller pops 12 bytes afterwards
    a = Asm()
    a.op(STS_PR); a.load(1, 'p')
    a.op(mov_i(3, 7)); a.op(0x2F36)                              # mov #7,r3 / mov.l r3,@-r15
    a.op(mov_i(3, 5)); a.op(0x2F36)                              # mov #5,r3 / mov.l r3,@-r15
    a.op(mov_i(2, 0x33)); a.op(jsr(1)); a.op(0x2F26)             # mov #0x33,r2 / jsr printfn / mov.l r2,@-r15 (the format)
    a.op(0x7F0C); a.op(LDS_PR); a.op(RTS); a.op(NOP)             # add #12,r15
    a.pool('p', ADDR['printfn'])
    return a


def fn_varcall4():
    # printfn(0x33, a4, 5) as ADXERR_CallErrFunc is called in adxt_stat_decinfo (Crazy Taxi): the same pushed variadic call, but r4
    # holds the function's own incoming value, which is one of the pushed words and not a register argument
    a = Asm()
    a.op(STS_PR); a.load(1, 'p')
    a.op(mov_i(0, 5)); a.op(mov_i(3, 0x33))
    a.op(0x2F06); a.op(0x2F46)                                   # mov.l r0,@-r15 / mov.l r4,@-r15
    a.op(jsr(1)); a.op(0x2F36)                                   # jsr printfn / mov.l r3,@-r15 (the format)
    a.op(0x7F0C); a.op(LDS_PR); a.op(RTS); a.op(NOP)
    a.pool('p', ADDR['printfn'])
    return a


def fn_floatret():
    # floatretfn(a4) calls voidfn(a4) and returns: its float result is whatever voidfn leaves in fr0 (setObjHitScatter -> KillColliObj,
    # Crazy Taxi: KillColliObj's proven definition is void, and the regenerated C dropped `u51 = KillColliObj(a4)`)
    a = Asm()
    # two paths join at one return: one sets fr0 = 1.0 (fldi1), the other ends in the void call, so on that path the result is
    # voidfn's fr0, not the 1.0 of the other path
    a.op(STS_PR); a.op(tst(4, 4)); a.jump('bt', 'call')
    a.op(0xF09D); a.jump('bra', 'end'); a.op(NOP)                # fldi1 fr0
    a.label('call'); a.load(1, 'v'); a.op(jsr(1)); a.op(NOP)
    a.label('end'); a.op(LDS_PR); a.op(RTS); a.op(NOP)
    a.pool('v', ADDR['voidfn'])
    return a


def fn_fptrdef():
    # fmov.s @r5,fr4 / fmov.s fr4,@r4: fr4 is written before it is read (a scratch register, not an argument)
    a = Asm(); a.op(0xF458); a.op(0xF44A); a.op(RTS); a.op(NOP)
    return a


def fn_fptrcaller():
    # fptrdef(1, 2, 3): its definition takes three float pointers, which are integer arguments (r4-r6), not floats
    a = Asm()
    a.op(STS_PR); a.load(1, 'f'); a.op(mov_i(4, 1)); a.op(mov_i(5, 2)); a.op(jsr(1)); a.op(mov_i(6, 3)); a.op(LDS_PR); a.op(RTS); a.op(NOP)
    a.pool('f', ADDR['fptrdef'])
    return a


def fn_twocall():
    # twoargfn(onefn(), twofn()) as the code orders it: onefn first, its result kept in r14 across twofn
    a = Asm()
    a.op(0x2FE6); a.op(STS_PR)                                   # mov.l r14,@-r15 / sts.l pr,@-r15
    a.load(1, 'a'); a.op(jsr(1)); a.op(NOP); a.op(mov(0, 14))
    a.load(1, 'b'); a.op(jsr(1)); a.op(NOP); a.op(mov(0, 5))
    a.load(1, 'c'); a.op(jsr(1)); a.op(mov(14, 4))
    a.op(LDS_PR); a.op(RTS); a.op(0x6EF6)                        # mov.l @r15+,r14 in the delay slot
    a.pool('a', ADDR['onefn']); a.pool('b', ADDR['twofn']); a.pool('c', ADDR['twoargfn'])
    return a


DEFS_C = ("typedef struct { int w[4]; } Stk4;\nint stk4fn(Stk4 s)\n{\n    return s.w[0];\n}\n"
          "typedef struct { int x, y, z; } Pt3;\nint ptfn(int a4, Pt3 p)\n{\n    return a4 + p.x;\n}\n"
          "int threearg(int a4, int a5, int a6)\n{\n    *(unsigned int *)0xC2A0000 = a4;\n    return a5 + a6;\n}\n"
          "void vsetfn(int a4, int a5, int a6, int a7, int a8)\n{\n    *(int *)a8 = a4;\n}\n"
          "void vecmk(int a4, int a5, int a6, int a7, int a8)\n{\n    *(int *)a8 = a4;\n}\n"
          "void fivefn(int a4, int a5, int a6, int a7, int a8)\n{\n    *(int *)a4 = a5 + a6 + a7 + a8;\n}\n"
          "void voidfn(int a4)\n{\n    *(int *)0xC2A0000 = a4;\n}\n"
          "void fptrdef(float *vd, float *vs, float *vt)\n{\n    *vd = *vs;\n}\n"
          "int passdef(int a4)\n{\n    return a4;\n}\n"
          "int varpdef(Stk3 s)\n{\n    return s.w[0];\n}\n"
          "int twoptfn(Stk3 a, Stk3 b)\n{\n    return a.w[0] + b.w[0];\n}\n"
          "int ptintfn(int a4, int a5, int a6, int a7, Stk3 a, int b)\n{\n    return a4 + a.w[0] + b;\n}\n"
          "void retvecfn(Stk4 s)\n{\n    *(int *)s.w[0] = s.w[1];\n}\n"
          "int bodyfn(int a4, int a5, int a6, int a7, int a8, int a9, int a10, int a11)\n{\n    return a8 + a11;\n}\n"
          "int body3fn(int a4, int a5, int a6, int a7, int a8, int a9, int a10)\n{\n    return a8 + a10;\n}\n"

          "typedef struct { int w[3]; } Stk3;\nStk3 sretdef(float f4, float f5, float f6)\n{\n    Stk3 v;\n    *(float *)&v.w[0] = f4;\n    return v;\n}\n")


FUNCS = [('storefn', fn_store), ('ifelsefn', fn_ifelse), ('earlyfn', fn_early), ('loopfn', fn_loop),
         ('whilefn', fn_whileloop), ('nestfn', fn_nest), ('nocondfn', fn_nocond), ('foreverfn', fn_forever),
         ('twoargfn', fn_twoarg), ('thunkfn', fn_thunk), ('passfn', fn_pass), ('callerfn', fn_caller),
         ('_slow_mvn', fn_slowmvn_helper), ('_quick_odd_mvn', fn_slowmvn_helper), ('copyfn', fn_copy), ('threearg', fn_onereg), ('defcallerfn', fn_defcaller),
         ('vecmk', fn_structret), ('vsetfn', fn_structret), ('structfn', fn_struct),
         ('fptrdef', fn_fptrdef), ('fptrcallerfn', fn_fptrcaller), ('onefn', fn_ret), ('twofn', fn_ret), ('twocallfn', fn_twocall), ('fivefn', fn_ret), ('fivecallfn', fn_fivecall), ('fivepassfn', fn_fivepass), ('printfn', fn_ret), ('varcallfn', fn_varcall), ('varcall4fn', fn_varcall4), ('voidfn', fn_ret), ('floatretfn', fn_floatret), ('ptfn', fn_ret), ('structargfn', fn_structarg), ('stackreadfn', fn_stackread), ('retvalfn', fn_retval), ('phantomfn', fn_phantom), ('stackpassfn', fn_stackpass), ('stackindfn', fn_stackind), ('stackspillfn', fn_stackspill), ('stackclobberfn', fn_stackclobber), ('switchfn', fn_switch), ('brafcompfn', fn_brafcomputed), ('stk4fn', fn_ret), ('stackframefn', fn_stackframe), ('stackframeintfn', fn_stackframeint), ('stackframeint2fn', fn_stackframeint2), ('readstack2', fn_readstack2), ('readstack1', fn_readstack1), ('readframe3', fn_readframe3), ('readframe3p', fn_readframe3p), ('structreusefn', fn_structreuse), ('stackonly1', fn_stackonly1), ('copyinfn', fn_copyin), ('sretfn', fn_sret), ('sretdef', fn_sret), ('sretcallfn', fn_sretcall), ('sretcallpfn', fn_sretcallp), ('argupdatefn', fn_argupdate), ('argnarrowfn', fn_argnarrow), ('fmergefn', fn_fmerge), ('fcarryfn', fn_fcarry), ('fslotfn', fn_fslot), ('fspillfn', fn_fspill), ('stkreads2', fn_stkreads2), ('framestkfn', fn_framestk), ('varpdef', fn_varreads1), ('varpush3fn', fn_varpush3), ('constfirstfn', fn_constfirst), ('twoptfn', fn_ret), ('twostructfn', fn_twostruct), ('ptintfn', fn_ret), ('pushstructfn', fn_pushstruct), ('retvecfn', fn_ret), ('retptrpushfn', fn_retptrpush), ('retptrpush2fn', fn_retptrpush2), ('bodyfn', fn_varreads1), ('intstackmixfn', fn_intstackmix), ('body3fn', fn_varreads1), ('intstackshortfn', fn_intstackshort), ('selfcallfn', fn_selfcall), ('phantomstkfn', fn_phantomstk), ('phantomstkffn', fn_phantomstkf), ('deferredfn', fn_deferred), ('spsteploopfn', fn_spsteploop), ('floatstackfn', fn_floatstack), ('passdef', fn_passdef), ('defthunkfn', fn_defthunk)]


def main():
    tmp = tempfile.mkdtemp()
    try:
        shutil.copytree(os.path.join(SKILL, "scripts", "tools"), os.path.join(tmp, "tools"),
                        ignore=shutil.ignore_patterns("__pycache__"))        # the tree a decomp gets
        data = b''
        lines = []
        for name, make in FUNCS:
            ADDR[name] = BASE + len(data)
            code = make().bytes()
            lines.append("F %08x %d %s" % (BASE + len(data), len(code), name))
            data += code
            if len(data) % 4:
                data += struct.pack('<H', 0x0009)
        open(os.path.join(tmp, "1ST_READ.BIN"), "wb").write(data)
        open(os.path.join(tmp, "BASE"), "w").write("%08X\n" % BASE)
        open(os.path.join(tmp, "functions.txt"), "w").write("\n".join(lines) + "\n")
        os.makedirs(os.path.join(tmp, "src"))
        open(os.path.join(tmp, "src", "defs.c"), "w").write(DEFS_C)        # a proven definition: its parameters count
        script = ("import sys; sys.path.insert(0, 'tools'); import toolpath, gen_core, gen_drv, gen_pipe\n"
                  "FORCE = {'floatretfn': ['fr0']}\n"      # the return kind the game has, where the first variant is another
                  "for n in sys.argv[1:]:\n"
                  "    try:\n"
                  "        v = gen_pipe.variants(n, False)\n"
                  "        v = FORCE.get(n, []) + v\n"
                  "        print('@@@@ ' + n); print(gen_drv.build(n, v[0], False)[0])\n"
                  "    except gen_core.Skip as e:\n"
                  "        print('@@@@ ' + n); print('SKIPPED ' + str(e))\n")
        out = subprocess.run([sys.executable, "-c", script] + [n for n, _ in FUNCS if not n.startswith('_') and n not in ('threearg', 'vecmk', 'vsetfn', 'fptrdef', 'onefn', 'twofn', 'fivefn', 'printfn', 'voidfn', 'passdef', 'sretdef', 'twoptfn', 'ptintfn', 'retvecfn', 'bodyfn', 'body3fn', 'varpdef', 'stkreads2')], cwd=tmp, stdout=subprocess.PIPE,
                             stderr=subprocess.STDOUT, universal_newlines=True).stdout
        flat = subprocess.run([sys.executable, "-c", script, 'phantomfn', 'spsteploopfn', 'structreusefn'], cwd=tmp, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                              universal_newlines=True, env=dict(os.environ, GEN_FORM='flat')).stdout       # the flat form, where the bug was
        out += flat.replace('@@@@ phantomfn', '@@@@ phantomfn_flat').replace('@@@@ spsteploopfn', '@@@@ spsteploopfn_flat').replace('@@@@ structreusefn', '@@@@ structreusefn_flat')
        parts = {}
        for chunk in out.split('@@@@ ')[1:]:
            name, _, text = chunk.partition('\n')
            parts[name] = text
        want = [
            ('storefn', ["*(unsigned int *)0xC2A0000 = 0x1;"]),
            ('ifelsefn', ["if (", "} else {", "= 0x1;", "= 0x2;"]),
            ('earlyfn', ["return", "= 0x7;"]),
            ('loopfn', ["for (;;) {", "break;", "+ 0x3)"]),
            ('whilefn', ["for (;;) {", "break;"]),
            ('nestfn', ["for (;;) {", "break;", "if ("]),
            ('nocondfn', ["SKIPPED"]),
            ('foreverfn', ["for (;;) {"]),
            ('thunkfn', ["(int a4, int a5)", "twoargfn(a4, a5)"]),
            ('callerfn', ["passfn(0x1, 0x7"]),
            ('copyfn', ["struct mvb16 { char b[16]; }"]),
            ('defcallerfn', ["threearg(0x1, 0x2, 0x3)"]),
            ('defthunkfn', ["(int a4)", "passdef(a4)"]),
            # both calls take five arguments, the pushed word last (open: today the pushed words are lost or misplaced)
            # a float pointer parameter is an integer argument: no float passed on, none taken (Drv_FacePsgFrame -> nlSubVector3op,
            # Crazy Taxi: three phantom floats)
            ('fptrcallerfn', ["fptrdef(0x1, 0x2, 0x3))", "not:float f4"]),
            # two calls in one statement run in an order C leaves open (SHC: right to left): each call its own statement, in the
            # code's order (Drv_FacePsgFrame: nlArcTan2(fabs(nlInnerProduct(a)), nlInnerProduct(b)) swapped the two, Crazy Taxi)
            ('twocallfn', [r"re:onefn\([^;]*;[\s\S]*twofn\(", r"not:re:onefn\([^;]*twofn\(|twofn\([^;]*onefn\("]),
            # REGRESSION, what works today: four register arguments and a fifth pushed in the delay slot are one five-argument call, and
            # a register the function never set is its own incoming argument passed on (the generator must keep doing both when it learns
            # to read stack-only calls)
            ('fivecallfn', ["fivefn(0x1, 0x2, 0x3, 0x4, 0x9)"]),
            ('fivepassfn', ["(int a4, int a5, int a6)", "fivefn(a4, 0x2, a6, 0x4, 0x9)"]),
            # FIXED, kept as a regression (replayChangeControl, gdc_CoursePointChk: "arg gap" / "stack arguments without four in registers"): a variadic call
            # with every argument on the stack is one call with the format first, then the values in order
            ('varcallfn', ["printfn(0x33, 0x5, 0x7)", "not:int a4"]),
            # FIXED, kept as a regression (adxt_stat_decinfo -> ADXERR_CallErrFunc: "stack arguments without four in registers [1 in registers, 3 ...]"): the same
            # call with r4 live, which is a pushed word and not an argument register
            ('varcall4fn', ["(int a4)", "printfn(0x33, a4, 0x5)"]),
            # FIXED, kept as a regression (setObjHitScatter -> KillColliObj, Crazy Taxi): on the path that ends in a call to a void callee the float result is the
            # callee's fr0, so the return variable must be set from that call there (or the function skipped), never left as it was
            ('floatretfn', [r"re:SKIPPED|u\d+ = [^;]*voidfn\(a4\)"]),
            ('structfn', [r"re:vecmk\((?:[^,;()]*,){4}\s*\(\(int\)stk \+ ", r"re:vsetfn\((?:[^,;()]*,){4}\s*0x9\)"]),
            # OPEN (the two halves of one bug, Crazy Taxi gdc_CourseStartLoadReq / kmiInitPAL / kmiSetVideoTimings): a structure passed
            # by value goes in the outgoing stack area. The call must carry it (ptfn takes it as its parameter in src/defs.c), and a
            # function that reads only its stack must not be given r4-r7 parameters
            ('structargfn', [r"re:ptfn\(0x5, \*\([^;]*stk[^;]*\)", "not:ptfn(0x5, a5)"]),
            ('stackreadfn', [r"not:int a4"]),
            # OPEN when it fails (LoadBackupData, Crazy Taxi): a result set in r0 before the return makes the definition int
            ('retvalfn', [r"re:int\s+retvalfn\(", r"re:return"]),
            # REGRESSION, what must not change when a pushed word makes r4-r7 positional: a word pushed earlier and not dropped after the
            # call is not an argument (voidfn takes one), and after an earlier call r5-r7 are no longer the incoming arguments: they are
            # leftovers and go as 0
            ('stackspillfn', ["voidfn(0x1)", "not:0x9"]),
            ('stackclobberfn', ["fivefn(0x1, 0x0, 0x0, 0x0, 0x9)"]),      # r5-r7 clobbered by the earlier call go as 0 (the check compares only registers the function set)
            # FIXED, kept as a regression (mwlRnaStartCopy, serveGetPos in playerInit, Virtua Tennis: "stack arguments without four in registers"): r4 set, r5-r7
            # never touched and a word pushed. The pushed word is the fifth argument, so r5-r7 are positional and are the function's own
            # incoming arguments, passed on; through a pointer the call used to be written with one argument and the pushed word dropped
            ('stackpassfn', ["fivefn(0x1, a5, a6, a7, 0x9)"]),
            ('stackindfn', [r"re:\(int \(\*\)\(int, int, int, int, int\)\)", "(0x1, a5, a6, a7, 0x9)", r"not:re:\(int \(\*\)\(int\)\)"]),
            # REGRESSION, what must not change when a braf stop falls back to the flat form: a braf that is no jump table stays skipped
            ('brafcompfn', ["SKIPPED"]),
            # FIXED, kept as a regression ("flow braf": commonLoadStep, kmySetVirticalFilterMode, kmyGetDisplayParametersInfo, Virtua Tennis): a jump table the
            # structured form cannot take is read by the flat form, which has the switch; a structured stop on braf must fall back to it
            ('switchfn', ["not:SKIPPED", "return", "0x1", "0x2"]),
            # FIXED, kept as a regression (ADXF_LoadPartition -> ADXERR_CallErrFunc, Virtua Tennis): a callee whose definition takes words from the stack, called with
            # nothing pushed, reads the caller's frame at SP: the call passes those words (the frame the C keeps holds the same values)
            ('stackframefn', [r"re:stk4fn\(\*\(Stk4 \*\)\(\(int\)stk \+ ", "not:@@F", "stk["]),
            # OPEN (adxf_read_sj32, adxf_SetFileInfo -> ADXERR_CallErrFunc, Crazy Taxi): the same with a definition that takes its stack word
            # as a plain fifth int (`int a8`), not a structure: r4-r7 are positional and the fifth word is read from the frame at SP
            ('stackframeintfn', [r"re:fivefn\(0x33, a5, a6, a7, \*\(int \*\)\(\(int\)stk \+ ", "not:@@F", "stk["]),
            ('stackframeint2fn', [r"re:fivefn\(0x33, 0x5, 0x0, 0x0, \*\(int \*\)\(\(int\)stk \+ ", "not:@@F"]),
            # FIXED, kept as a regression (motionSet then motionRootFirst in playerInit, Virtua Tennis): the stack adjustment is deferred past the next call. Each call
            # takes the words its callee reads from the stack (two, then one), the earlier ones are not the later call's arguments
            ('deferredfn', ["readstack2(0x1, 0x2, 0x3, 0x4, 0x8, 0x9)", "readstack1(0x5, 0x6, 0x7, 0x8, 0x7)"]),
            # a callee declares the stack words it reads and no more: the generator padded them to four, so a function reading one,
            # two or three words had phantom stack parameters (a8..a11), and the checker compared a caller's own local at the next
            # word as an argument (sprPutAtAlpha reads three words, declared four: 34 Virtua Tennis callers differed on a leftover)
            ('readframe3', ["(int a4, Stk3 s)", "not:a11"]),
            ('readframe3p', ["not:SKIPPED", "(int a4, Stk3 s)", "not:a11"]),
            ('stackonly1', ["not:SKIPPED", "Stk4 s"]),
            # the words a block copy reads from the caller's area count, not only its first address (hudFontNumPut, Virtua Tennis: declared
            # one stack word once the padding to four went, its point's other two words came out as zeros)
            # a store into the function's own argument area reaches the frame array a later copy of that area reads (hudSignFirstPut)
            ('constfirstfn', ["not:SKIPPED", "int a8"]),
            ('framestkfn', ["not:SKIPPED", "stkreads2(0x5, 0x6, "]),
            ('fspillfn', ["not:SKIPPED", r"re:= \(?\*\(float \*\)\(+\(int\)stk", r"not:re:float u\d+;"]),
            ('fslotfn', ["not:SKIPPED", "1.0f", "a8"]),
            ('fcarryfn', ["not:SKIPPED", r"re:float u\d+;"]),
            ('fmergefn', ["not:SKIPPED", r"re:float u\d+;", "1.0f"]),
            ('varpush3fn', ["not:SKIPPED", r"re:varpdef\([^;]*,[^;]*,[^;]*\)"]),
            # an int pushed before a structure copied for the same call: an argument after the structure (winDrawA -> winPartsPut)
            ('pushstructfn', ["not:SKIPPED", r"re:ptintfn\(0x1, 0x2, 0x3, 0x4, \*\(Stk3 \*\)\([^;]*\), 0x5\)"]),
            ('retptrpushfn', ["not:SKIPPED", r"re:\*\(int \*\)\(\(int\)stk \+ (\d+)\) = [^;]*;\s*return \(retvecfn\(\*\(Stk4 \*\)\(\(\(int\)stk \+ \1\)\)\)\)"]),
            ('retptrpush2fn', ["not:SKIPPED", r"re:\*\(int \*\)\(\(int\)stk \+ (\d+)\) = [^;]*;\s*return \(retvecfn\(\*\(Stk4 \*\)\(+\(int\)stk \+ \1\)+\)\)"]),
            ('intstackmixfn', ["not:SKIPPED", r"re:bodyfn\(0x1, 0x2, 0x3, 0x4, \*\(int \*\)\(\(int\)stk \+ \d+(?: \+ \d+)?\), \*\(int \*\)\(\(int\)stk \+ \d+(?: \+ \d+)?\), \*\(int \*\)\(\(int\)stk \+ \d+(?: \+ \d+)?\), \*\(int \*\)\(\(int\)stk \+ \d+(?: \+ \d+)?\)"]),
            ('intstackshortfn', ["not:SKIPPED", r"re:body3fn\(0x1, 0x2, 0x3, 0x4, \*\(int \*\)\(\(int\)stk \+ \d+(?: \+ \d+)?\), \*\(int \*\)\(\(int\)stk \+ \d+(?: \+ \d+)?\), \*\(int \*\)\(\(int\)stk \+ \d+(?: \+ \d+)?\)\)"]),
            ('selfcallfn', ["not:SKIPPED", r"re:\(\(\w+ \(\*\)\([^)]*\)\)\(selfcallfn\)\)\("]),
            ('phantomstkfn', ["not:SKIPPED", "(int a4, Stk3 s)", "not:a5"]),
            ('phantomstkffn', ["not:SKIPPED", "(int a4, Stk3 s)", "not:a5"]),
            ('twostructfn', ["not:SKIPPED", r"re:twoptfn\(\*\(Stk3 \*\)\([^;]*\), \*\(Stk3 \*\)\("]),
            ('argupdatefn', ["not:SKIPPED", r"re:\*\(float \*\)\(\(\(int\)stk \+ \d+\)\) = ", "ptfn(0x5, "]),
            # a short stored into its own argument area (cameraExec cases 5, 6, 9): read back as the short, copied as the merged word
            ('argnarrowfn', ["not:SKIPPED", r"re:\*\(unsigned short \*\)\(\(\(int\)stk \+ \d+\)\) = ", r"re:ptfn\(\(?\(short\)"]),
            ('copyinfn', ["not:SKIPPED", "(int a4, Stk3 s)", "not:a11"]),
            # a structure returned by value (vecMake, Virtua Tennis): written as one, not as a structure argument whose first word is the
            # destination; its callers assign the result and pass no register integers
            ('sretfn', ["not:SKIPPED", "Stk3 sretfn(float f4, float f5, float f6)", r"re:return \*\(Stk3 \*\)", "not:Stk4"]),
            # the pushed pointer is not a local's address (cameraExec, Virtua Tennis: a register the C holds as a variable; here the
            # function's own argument): it is still the hidden return pointer, and the call still an assignment of the structure
            ('sretcallpfn', ["not:SKIPPED", r"re:\*\(Stk3 \*\)\(a4\) = sretdef\(", r"not:re:sretdef\(a\d"]),
            ('sretcallfn', ["not:SKIPPED", r"re:\*\(Stk3 \*\)\([^;]*\) = sretdef\([^a;]*\);", r"not:re:sretdef\(a\d"]),
            ('readstack2', ["int a8, int a9)", "not:a10"]),
            # OPEN (hudFontNumPut and 11 more, Virtua Tennis: "stack pointer step"): the register stack-pointer step inside a loop
            ('spsteploopfn', ["not:SKIPPED", "ptfn(0x5, "]),
            # the structure argument is the copy at SP, never the source register's later value (hudFontNumPut, Virtua Tennis)
            ('structreusefn_flat', ["not:SKIPPED", r"re:ptfn\(0x5, \*\(Stk3 \*\)\(\(\(int\)stk \+ ", r"not:re:\*\(Stk3 \*\)\([RtT]\w*\)"]),
            ('spsteploopfn_flat', ["not:SKIPPED", "ptfn(0x5, "]),      # the same in the flat form, where every register is a variable
            # OPEN (cpuInRange and 12 more, Virtua Tennis: "stack argument read"): a float the caller left on the stack is read as the
            # function's stack parameter, its bits reinterpreted as a float
            ('floatstackfn', ["not:SKIPPED", "a8"]),
            # a register written before it is read, or one a callee does not take, is not a parameter (Start_Fog, Crazy Taxi)
            ('phantomfn', ["phantomfn(void)", "onefn("]),
            ('phantomfn_flat', ["phantomfn(void)", "onefn("]),
        ]
        bad = []
        for name, needles in want:
            text = parts.get(name, '')
            has = lambda x: bool(re.search(x[3:], text)) if x.startswith('re:') else x in text
            miss = [x for x in needles if (has(x[4:]) if x.startswith('not:') else not has(x))]
            if miss:
                bad.append("%s: missing %s in\n%s" % (name, miss, text))
        if 'literal pool' in out:
            bad.append('unexpected')
        if not bad:
            print("[gen_equiv] ok: store, if/else, early return, counted loop, test-at-bottom loop, nested loop written (loops as for (;;) with a break); "
                  "a loop without a condition is skipped, a loop that never ends is written as for (;;) with no break; "
                  "a thunk passes its incoming arguments on; a call passes a register its callee hands on to a pointer call; "
                  "the byte mover is one struct copy; a callee's proven definition sets how many arguments a call passes")
            return
        sys.exit("[ERROR] gen_equiv check failed:\n" + "\n".join(bad) + "\n--- all output ---\n" + out)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    main()
