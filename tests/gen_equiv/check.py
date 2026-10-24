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
          "void fptrdef(float *vd, float *vs, float *vt)\n{\n    *vd = *vs;\n}\n")


FUNCS = [('storefn', fn_store), ('ifelsefn', fn_ifelse), ('earlyfn', fn_early), ('loopfn', fn_loop),
         ('whilefn', fn_whileloop), ('nestfn', fn_nest), ('nocondfn', fn_nocond), ('foreverfn', fn_forever),
         ('twoargfn', fn_twoarg), ('thunkfn', fn_thunk), ('passfn', fn_pass), ('callerfn', fn_caller),
         ('_slow_mvn', fn_slowmvn_helper), ('copyfn', fn_copy), ('threearg', fn_onereg), ('defcallerfn', fn_defcaller),
         ('vecmk', fn_structret), ('vsetfn', fn_structret), ('structfn', fn_struct),
         ('fptrdef', fn_fptrdef), ('fptrcallerfn', fn_fptrcaller), ('onefn', fn_ret), ('twofn', fn_ret), ('twocallfn', fn_twocall), ('fivefn', fn_ret), ('fivecallfn', fn_fivecall), ('fivepassfn', fn_fivepass), ('printfn', fn_ret), ('varcallfn', fn_varcall), ('varcall4fn', fn_varcall4), ('voidfn', fn_ret), ('floatretfn', fn_floatret), ('ptfn', fn_ret), ('structargfn', fn_structarg), ('stackreadfn', fn_stackread), ('retvalfn', fn_retval), ('phantomfn', fn_phantom), ('stackpassfn', fn_stackpass), ('stackindfn', fn_stackind), ('stackspillfn', fn_stackspill), ('stackclobberfn', fn_stackclobber), ('switchfn', fn_switch), ('brafcompfn', fn_brafcomputed), ('stk4fn', fn_ret), ('stackframefn', fn_stackframe), ('stackframeintfn', fn_stackframeint), ('stackframeint2fn', fn_stackframeint2), ('readstack2', fn_readstack2), ('readstack1', fn_readstack1), ('deferredfn', fn_deferred)]


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
        out = subprocess.run([sys.executable, "-c", script] + [n for n, _ in FUNCS if not n.startswith('_') and n not in ('threearg', 'vecmk', 'vsetfn', 'fptrdef', 'onefn', 'twofn', 'fivefn', 'printfn', 'voidfn')], cwd=tmp, stdout=subprocess.PIPE,
                             stderr=subprocess.STDOUT, universal_newlines=True).stdout
        flat = subprocess.run([sys.executable, "-c", script, 'phantomfn'], cwd=tmp, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                              universal_newlines=True, env=dict(os.environ, GEN_FORM='flat')).stdout       # the flat form, where the bug was
        out += flat.replace('@@@@ phantomfn', '@@@@ phantomfn_flat')
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
