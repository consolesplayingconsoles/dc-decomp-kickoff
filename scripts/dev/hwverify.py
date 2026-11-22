#!/usr/bin/env python3
"""Run one function's test cases on the simulator and on the real Dreamcast, and compare. Stdlib only.

    hwverify.py REPO FUNCTION --runtime DIR [--port DEVICE] [--baud 57600] [--log FILE] [--dry-run]

REPO is a decomp repo (it has 1ST_READ.BIN, BASE, functions.txt, tests/<unit>/<FUNCTION>.json and tools/sim/sh4sim.py).
The function's own bytes, and the literal pool its pc-relative loads reach, are written into the console's RAM at
their real addresses and run there; each case sets its registers and memory words, calls the function and prints r0
and the words the case poked. The same case runs in tools/sim/sh4sim.py; the two answers are compared case by case and
every step is logged (to the screen and to --log).

What it can run: leaf functions (no calls out), integer registers r4-r7 as arguments, 4-byte pokes. A case with a
RAM dump, a call list, a float register or any other register is reported "NOT RUN" with its reason. Memory the
function writes outside the poked words is not compared.

The port is found by asking each USB serial adapter for dcload's version (its number changes when the cable is
replugged); --port forces one. --runtime DIR holds the dcload example runtime built for the Dreamcast: crt0.o, dcload-syscall.o, dcload-syscalls.o,
dcload-syscalls.h and the linker script dc4.x (or dc.x). The tool needs sh-elf-gcc and dc-tool-ser on PATH.
--dry-run writes the C program and stops: no console needed.
Exit: 0 every case matched (or --dry-run wrote the program), 1 a case differed, printed nothing or crashed the
console, 2 nothing could be run.
"""
import argparse
import glob
import json
import os
import re
import subprocess
import sys
import tempfile
import time

M32 = 0xFFFFFFFF


class SimError(Exception):
    pass


def u16(code, i):
    return code[i] | (code[i + 1] << 8)


def pool_end(code, start):
    """The address just past the last byte a pc-relative load in code (at address start) reads, or past
    the code itself when that is farther."""
    end = start + len(code)
    for i in range(0, len(code) - 1, 2):
        w = u16(code, i)
        pc = start + i
        if (w & 0xF000) == 0xD000:                   # mov.l @(disp,pc),Rn
            end = max(end, (pc & ~3) + 4 + (w & 0xFF) * 4 + 4)
        elif (w & 0xF000) == 0x9000:                 # mov.w @(disp,pc),Rn
            end = max(end, pc + 4 + (w & 0xFF) * 2 + 2)
        elif (w & 0xFF00) == 0xC700:                 # mova @(disp,pc),r0
            end = max(end, (pc & ~3) + 4 + (w & 0xFF) * 4 + 4)
    return end


_READS_RN = {0x0: (0x4, 0x5, 0x6, 0x7), 0x2: (0x0, 0x1, 0x2, 0x7, 0x8, 0xC, 0xE, 0xF), 0x3: (0x0, 0x2, 0x3, 0x5, 0x6, 0x7, 0xD)}
_READS_4N = (0x0B, 0x2B, 0x11, 0x15, 0x1B, 0x0A, 0x1A, 0x2A, 0x5A, 0x6A, 0xFA, 0x0E, 0x1E, 0x2E, 0x3E, 0x4E)


def writes_reg(w, r):
    """Whether instruction w may write general register r (it errs towards yes: a yes only stops a call target from
    being resolved, never resolves a wrong one)."""
    hi, n, m, lo = w >> 12, (w >> 8) & 0xF, (w >> 4) & 0xF, w & 0xF
    if hi in (0x8, 0xC):
        return r == 0                                # the forms with an implied r0
    if hi in (0xA, 0xB):
        return False
    if hi == 0x6 and lo in (4, 5, 6) and m == r:
        return True                                  # mov @Rm+,Rn moves Rm too
    if hi == 0xF:
        return (lo == 0xB and n == r) or (lo == 0x9 and m == r)   # fmov FRm,@-Rn / fmov @Rm+,FRn
    if n != r:
        return False
    if hi == 0x1:
        return False                                 # mov.l Rm,@(disp,Rn)
    if hi in _READS_RN:
        return not (lo in _READS_RN[hi] or (hi == 0 and (w & 0xFF) in (0x03, 0x23, 0x83, 0x93, 0xA3, 0xB3, 0xC3)))
    if hi == 0x4:
        return not ((w & 0xFF) in _READS_4N or (w & 0x8F) == 0x8E)
    return True


def call_targets(blob, start, size):
    """-> (targets, problems). The callees the function's code (its first size bytes of blob, at start) reaches: a
    bsr/bra out of the function, or a jsr/jmp through a register that a mov.l from the literal pool loaded (and nothing
    wrote since). Anything else that leaves the function (bsrf, braf, a register computed at run time) is a problem:
    its target cannot be stubbed before the run."""
    targets, problems = set(), []
    for i in range(0, size - 1, 2):
        w, pc = u16(blob, i), start + i
        r = (w >> 8) & 0xF
        if (w & 0xF0FF) in (0x400B, 0x402B):
            name = '%s @r%d at %08X' % ('jsr' if w & 0x20 == 0 else 'jmp', r, pc)
            target = None
            for j in range(i - 2, -1, -2):
                w2 = u16(blob, j)
                if (w2 & 0xF000) == 0xD000 and (w2 >> 8) & 0xF == r:
                    at = ((start + j) & ~3) + 4 + (w2 & 0xFF) * 4 - start
                    if at + 4 <= len(blob):
                        target = blob[at] | blob[at + 1] << 8 | blob[at + 2] << 16 | blob[at + 3] << 24
                    break
                if writes_reg(w2, r):
                    break
            if target is None:
                problems.append('%s: the target is computed, not stubbed yet' % name)
            else:
                targets.add(target)
        elif (w & 0xF0FF) in (0x0003, 0x0023):
            problems.append('%s r%d at %08X: the target is computed, not stubbed yet'
                            % ('bsrf' if w & 0x20 == 0 else 'braf', r, pc))
        elif (w & 0xE000) == 0xA000:
            d = w & 0xFFF
            target = pc + 4 + (d - 0x1000 if d & 0x800 else d) * 2
            if not start <= target < start + size:
                targets.add(target)
    return sorted(targets), problems


def stub_code(target):
    """-> (halfwords, offset of the two literal words). The stub at a callee's address: mov.l r1,@-r15; mova lit,r0;
    mov.l @(4,r0),r1; jmp @r1; mov.l @r0,r0 (delay slot), then nops up to the literal words: the callee's address and
    the shared recorder's (the program fills both). The recorder gets r0 = the callee's address and r1 on the stack."""
    lit = 10 + (-(target + 10) % 4)
    disp = (target + lit - (((target + 2) & ~3) + 4)) // 4
    return [0x2F16, 0xC700 | disp, 0x5101, 0x412B, 0x6002] + [0x0009] * ((lit - 10) // 2), lit


def stub_problems(targets, start, end):
    """Callees whose stub cannot go in: an odd address, or a stub (up to 20 bytes) over the function's own bytes
    and pool (start..end) or over another stub."""
    out, spans = [], []
    for t in targets:
        if t & 1:
            out.append('%08X: an odd callee address' % t)
            continue
        size = stub_code(t)[1] + 8
        lo, hi = t & 0x1FFFFFFF, (t & 0x1FFFFFFF) + size
        if lo < (end & 0x1FFFFFFF) and (start & 0x1FFFFFFF) < hi:
            out.append('%08X: its stub would overwrite the function' % t)
        for a, b, u in spans:
            if lo < b and a < hi:
                out.append('%08X: its stub would overwrite the one at %08X' % (t, u))
        spans.append((lo, hi, t))
    return out


def as_int(v):
    return v if isinstance(v, int) else int(str(v), 16)


def parse_case(case):
    """-> {regs: {n: value}, pokes: [(addr, word)], rets: [r0 per call], unsupported: reason or None}. A call's
    scripted answer is its r0 (0 when the case gives none, as the simulator does); any other answer is not
    stubbed on the console yet."""
    out = {'regs': {}, 'pokes': [], 'rets': [], 'unsupported': None}
    if case.get('dump'):
        out['unsupported'] = 'dump: a RAM dump is not loaded on the console'
        return out
    for call in case.get('calls') or []:
        other = sorted(k for k in call if k != 'r0')
        if other:
            out['unsupported'] = 'calls: %s in a call\'s answer (only r0 is answered on the console)' % ', '.join(other)
            return out
        out['rets'].append(as_int(call.get('r0', 0)) & M32)
    for name, val in sorted((case.get('regs') or {}).items()):
        m = re.match(r'^r([4-7])$', name)
        if not m:
            out['unsupported'] = '%s: only r4-r7 are set on the console' % name
            return out
        out['regs'][int(m.group(1))] = as_int(val) & M32
    if case.get('sr'):
        out['unsupported'] = 'sr: the status register is not set on the console'
        return out
    for addr, data in sorted((case.get('poke') or {}).items()):
        raw = bytes.fromhex(data) if isinstance(data, str) else bytes(data)
        if len(raw) != 4:
            out['unsupported'] = 'poke: %d bytes at %s (only whole words)' % (len(raw), addr)
            return out
        out['pokes'].append((int(addr, 16), raw[0] | (raw[1] << 8) | (raw[2] << 16) | (raw[3] << 24)))
    return out


def sim_result(sim, pokes):
    """The simulator's answer as what the console can be asked: r0, the word at each poked address, and the calls in
    order (target, r4-r7, the word at the stack pointer, and which of those were set for the call)."""
    if sim.get('error'):
        raise SimError(str(sim['error']))
    mem = dict((a, v) for a, v in pokes)
    by_phys = dict((a & 0x1FFFFFFF, a) for a, _ in pokes)   # the simulator names a write by one mirror, the case by another
    for addr, size, value in sim.get('writes') or []:
        a = by_phys.get(int(addr, 16) & 0x1FFFFFFF)
        if size == 4 and a is not None:
            mem[a] = int(value, 16)
    calls = [{'to': int(c['to'], 16), 'args': [int(x, 16) for x in c['r4-r7']], 'chg': [bool(x) for x in c['chg']],
              'stack': int(c['stack'], 16), 'stackchg': bool((c.get('stackchg') or [False])[0])}
             for c in sim.get('calls') or []]
    return {'r0': int(sim['out']['r0'], 16), 'mem': mem, 'calls': calls}


def p2(addr):
    """The uncached mirror of a RAM address."""
    return (addr & 0x1FFFFFFF) | 0xA0000000


MAX_CALLS = 512
PROGRAM_AT = 0x8CF00000          # where the program is linked: above the game's code and data, under the stack (8D000000)
SIM_SP0 = 0x0DFFFF00             # the simulator's stack pointer at the function's entry (sh4sim: STACK_TOP - 0x100)
SIM_STACK = (0x0DFF0000, 0x0E000000)


def outside_ram(reads):
    """The first address the original read outside RAM and the simulator's stack ('' for none), as text. The simulator
    answers 0 there (the boot ROM, open bus); the console gives the real bytes, and a function that walks what it read
    there can loop for ever (a list header read at 00000018 through a null pointer hung the console)."""
    for a in reads:
        p = a & 0x1FFFFFFF
        if not (0x0C000000 <= p < 0x0D000000 or SIM_STACK[0] <= p < SIM_STACK[1]):
            return '%08X' % a
    return ''


def moved_script(text):
    """The loader's linker script with the program moved from 8C010000 (where the game's code is) to PROGRAM_AT."""
    return text.replace('0x8c010000', '0x%08x' % PROGRAM_AT)


def data_words(reads, image):
    """{cached address: value} for every RAM word the original read in the simulator: what the simulator had there at
    the start, the executable's bytes inside the image (base, bytes) and 0 in the rest of RAM. The stack, hardware
    registers, the loader (below 8C010000) and the program's own area (PROGRAM_AT up) are left out."""
    base, exe = image[0] & 0x1FFFFFFF, image[1]
    out = {}
    for a in reads:
        p = a & 0x1FFFFFFF
        if not 0x0C010000 <= p < (PROGRAM_AT & 0x1FFFFFFF):      # below 8C010000: the loader
            continue
        w = p & ~3
        off = w - base
        v = int.from_bytes(exe[off:off + 4], 'little') if 0 <= off and off + 4 <= len(exe) else 0
        out[w | 0x80000000] = v
    return out


# the shared recorder the stubs jump to (r0 = the callee's address, r1 pushed by the stub): records the callee,
# r4-r7 and the word at the caller's stack pointer, answers r0 = the case's next scripted result (0 past them) and
# fr0 = 0, and leaves every other register and T as they were, as the simulator's mocked callee does
RECORDER = r'''
__asm__(
"  .text\n  .align 2\n  .global _hw_stub_common\n_hw_stub_common:\n"
"  mov.l r2,@-r15\n  mov.l r3,@-r15\n  movt r2\n  mov.l r2,@-r15\n"
"  mov.l .Lcp,r1\n  mov.l @r1,r2\n  mov.l .Lce,r3\n  mov.l @r3,r3\n  cmp/hs r3,r2\n  bt 1f\n"
"  mov.l r0,@r2\n  mov.l r4,@(4,r2)\n  mov.l r5,@(8,r2)\n  mov.l r6,@(12,r2)\n  mov.l r7,@(16,r2)\n"
"  mov.l @(16,r15),r3\n  mov.l r3,@(20,r2)\n  add #24,r2\n  mov.l r2,@r1\n"
"1:\n  mov.l .Lrp,r1\n  mov.l @r1,r2\n  mov.l .Lre,r3\n  mov.l @r3,r3\n  mov #0,r0\n  cmp/hs r3,r2\n  bt 2f\n"
"  mov.l @r2,r0\n  add #4,r2\n  mov.l r2,@r1\n"
"2:\n  fldi0 fr0\n  mov.l @r15+,r2\n  shlr r2\n  mov.l @r15+,r3\n  mov.l @r15+,r2\n  rts\n  mov.l @r15+,r1\n"
"  .align 2\n.Lcp: .long _hw_callp\n.Lce: .long _hw_calle\n.Lrp: .long _hw_retp\n.Lre: .long _hw_rete\n");
'''

# the way into the function, for every function: it starts as in the simulator -- the 4 KB of stack below it zeroed (the
# simulator's stack is a fresh page: a local read before it is written reads 0), T, r0-r3 clear -- and the stack pointer
# it starts with is kept (hw_sp0), for arguments that point into its frame
ENTER = r'''
__asm__(
"  .text\n  .align 2\n  .global _hw_enter\n_hw_enter:\n"
"  mov r15,r1\n  mov #0,r0\n  mov.l .Lzc,r2\n"
"0:\n  mov.l r0,@-r1\n  dt r2\n  bf 0b\n"
"  mov.l .Lsp,r1\n  mov.l r15,@r1\n  mov.l .Lfn,r0\n  mov.l @r0,r0\n  mov #0,r1\n  mov #0,r3\n  clrt\n  jmp @r0\n  mov #0,r0\n"
"  .align 2\n.Lzc: .long 1024\n.Lsp: .long _hw_sp0\n.Lfn: .long _hw_entry\n");
'''


def render_harness(blob, base, entry, cases, check_addrs, stubs=(), data=None):
    """The C program for the console. The code is written and run through the uncached mirror; data is touched
    at the address the function itself uses (the cached one), so a stale cache line can never answer for it.
    The cases are tables walked by one loop, every message is a whole line in one write, and the program says
    how far it got (start, done) so a console that stops answering still leaves a trail."""
    n, m = len(cases), len(check_addrs)
    rows = max(n, 1)
    cols = max(m, 1)
    args, vals, masks = [], [], []
    for c in cases:
        args.append('{%s}' % ','.join('0x%08Xu' % c['regs'].get(r, 0) for r in (4, 5, 6, 7)))
        by = dict(c['pokes'])
        vals.append('{%s}' % ','.join('0x%08Xu' % by.get(a, 0) for a in check_addrs) if m else '{0}')
        masks.append('0x%08Xu' % sum(1 << j for j, a in enumerate(check_addrs) if a in by))
    if not cases:
        args, vals, masks = ['{0,0,0,0}'], ['{0}'], ['0x00000000u']
    stub_decl, stub_install, before, after = [], [], [], []
    call = '        r = hw_enter(args[n][0], args[n][1], args[n][2], args[n][3]);'
    enter_decl = [ENTER,
                  'extern unsigned int hw_enter(unsigned int, unsigned int, unsigned int, unsigned int);',
                  'unsigned int hw_entry = 0x%08Xu;' % p2(entry),
                  'unsigned int hw_sp0;', '']
    sp_out = ['        p = cat(line, p, " S ");',
              '        hex8(hw_sp0, line + p); p += 8;']
    data = sorted((data or {}).items())
    data_decl = ['static const unsigned int dataa[%d] = {%s};' % (max(len(data), 1), ','.join('0x%08Xu' % a for a, _ in data) or '0'),
                 'static const unsigned int datav[%d] = {%s};' % (max(len(data), 1), ','.join('0x%08Xu' % v for _, v in data) or '0'),
                 ''] if data else []
    data_poke = (['        for (j = 0; j < %d; j++) *(volatile unsigned int *)dataa[j] = datav[j];' % len(data)]
                 if data else [])
    if stubs:
        retv, offs, lens = [], [], []
        for c in cases:
            offs.append(len(retv))
            lens.append(len(c.get('rets') or []))
            retv += c.get('rets') or []
        stub_decl = [RECORDER,
                     'extern void hw_stub_common(void);',
                     'unsigned int hw_calls[%d * 6];' % MAX_CALLS,
                     'unsigned int *hw_callp, *hw_calle;',
                     'const unsigned int *hw_retp, *hw_rete;',
                     'static const unsigned int retv[%d] = {%s};' % (max(len(retv), 1), ','.join('0x%08Xu' % v for v in retv) or '0'),
                     'static const unsigned int retoff[%d] = {%s};' % (rows, ','.join(str(v) for v in offs) or '0'),
                     'static const unsigned int retlen[%d] = {%s};' % (rows, ','.join(str(v) for v in lens) or '0'), '']
        for t in stubs:
            words, lit = stub_code(t)
            s = p2(t)
            stub_install.append('    { volatile unsigned short *s = (volatile unsigned short *)0x%08Xu;' % s)
            stub_install += ['      s[%d] = 0x%04X;' % (i, w) for i, w in enumerate(words)]
            stub_install += ['      *(volatile unsigned int *)0x%08Xu = 0x%08Xu;' % (s + lit, t),
                             '      *(volatile unsigned int *)0x%08Xu = (unsigned int)hw_stub_common; }' % (s + lit + 4)]
        before = ['        hw_callp = hw_calls; hw_calle = hw_calls + %d * 6;' % MAX_CALLS,
                  '        hw_retp = retv + retoff[n]; hw_rete = hw_retp + retlen[n];']
        after = ['        if (hw_callp >= hw_calle) p = cat(line, p, " C OVERFLOW");',
                 '        else for (k = 0; k < (hw_callp - hw_calls); k++) {',
                 '            if (k % 6 == 0) p = cat(line, p, " C");',
                 '            line[p++] = \' \';',
                 '            hex8(hw_calls[k], line + p); p += 8;',
                 '        }']
    lines = ['#include "dcload-syscalls.h"', '',
             'static const unsigned char blob[%d] = {' % len(blob),
             ','.join('0x%02x' % b for b in blob), '};', '',
             '/* the loader\'s startup code clears the BSS with 4-byte stores from _edata: one word of .data keeps',
             '   _edata on a word whatever the size of the read-only data before it */',
             'int hwverify_edata_word = 1;', '',
             '#define CODE  0x%08Xu' % p2(base),
             '#define ENTRY 0x%08Xu' % p2(entry), '',
             'static const unsigned int chk[%d] = {%s};' % (cols, ','.join('0x%08Xu' % x for x in check_addrs) or '0'),
             'static const unsigned int args[%d][4] = {%s};' % (rows, ','.join(args)),
             'static const unsigned int pokev[%d][%d] = {%s};' % (rows, cols, ','.join(vals) if cases else '{0}'),
             'static const unsigned int pokem[%d] = {%s};' % (rows, ','.join(masks)), ''] + data_decl + enter_decl + stub_decl + [
             'static void hex8(unsigned int v, char *o) {',
             '    int i;',
             '    for (i = 7; i >= 0; i--) { o[i] = "0123456789ABCDEF"[v & 15]; v >>= 4; }',
             '}', '',
             'static int cat(char *o, int p, const char *s) {',
             '    while (*s) o[p++] = *s++;',
             '    return p;',
             '}', '',
             'int main(void) {',
             '    volatile unsigned char *dst = (volatile unsigned char *)CODE;',
             '    unsigned int r;',
             '    char line[%d];' % (19 + 20 * m + 2 + 11 + ((MAX_CALLS * 56 + 12) if stubs else 0)),
             '    int n, j, k, p;', '',
             '    for (k = 0; k < %d; k++) dst[k] = blob[k];' % len(blob)] + stub_install + [
             '    write(1, "hwverify start\\n", 15);',
             '    for (n = 0; n < %d; n++) {' % n] + data_poke + [
             '        for (j = 0; j < %d; j++)' % m,
             '            if (pokem[n] & (1u << j)) *(volatile unsigned int *)chk[j] = pokev[n][j];'] + before + [
             call,
             '        p = 0;',
             '        p = cat(line, p, "CASE ");',
             '        line[p++] = (char)(\'0\' + (n / 10) % 10);',
             '        line[p++] = (char)(\'0\' + n % 10);',
             '        p = cat(line, p, " R0 ");',
             '        hex8(r, line + p); p += 8;',
             '        for (j = 0; j < %d; j++) {' % m,
             '            p = cat(line, p, " M ");',
             '            hex8(chk[j], line + p); p += 8;',
             '            line[p++] = \'=\';',
             '            hex8(*(volatile unsigned int *)chk[j], line + p); p += 8;',
             '        }'] + sp_out + after + [
             '        line[p++] = \'\\n\';',
             '        write(1, line, p);',
             '    }',
             '    write(1, "hwverify done\\n", 14);',
             '    exit(0);',
             '}', '']
    return '\n'.join(lines)


def edata_from_nm(text):
    """_edata's address from `nm` output, or None."""
    for line in text.splitlines():
        parts = line.split()
        if len(parts) == 3 and parts[2] == '_edata':
            return int(parts[0], 16)
    return None


def edata_problem(edata):
    """'' when _edata is on a 4-byte boundary, else why the program must not be uploaded."""
    if edata is None:
        return 'no _edata in the linked program: cannot check where the startup code clears the BSS'
    if edata % 4:
        return ('_edata is %08X, not on a 4-byte boundary: the startup code\'s first BSS store would be an address '
                'error and the console would stop answering' % edata)
    return ''


def parse_output(text):
    """{case number: {'r0', 'mem', 'calls'}} from the console's CASE lines; any other text is ignored. A call is
    " C <target> <r4> <r5> <r6> <r7> <word at the stack pointer>"; " C OVERFLOW" is more calls than the program keeps;
    " S <stack pointer at the function's entry>" comes before them."""
    out = {}
    h = '[0-9A-F]{8}'
    for line in text.splitlines():
        m = re.match(r'^CASE (\d+) R0 (%s)((?: M %s=%s)*)(?: S (%s))?((?: C (?:OVERFLOW|%s(?: %s){5}))*)\s*$' % (h, h, h, h, h, h), line)
        if not m:
            continue
        mem = {}
        for a, v in re.findall(r' M (%s)=(%s)' % (h, h), m.group(3)):
            mem[int(a, 16)] = int(v, 16)
        if 'OVERFLOW' in m.group(5):
            calls = 'OVERFLOW'
        else:
            calls = [{'to': int(c[0], 16), 'args': [int(x, 16) for x in c[1:5]], 'stack': int(c[5], 16)}
                     for c in (g.split() for g in m.group(5).split(' C ') if g.strip())]
        out[int(m.group(1))] = {'r0': int(m.group(2), 16), 'mem': mem, 'calls': calls}
        if m.group(4):
            out[int(m.group(1))]['sp'] = int(m.group(4), 16)
    return out


def parse_crash(text):
    """The EXCEPTION line dc-tool-ser prints when the loader reports a crash (dcload-serial 1.0.7-cpc), or None."""
    for line in text.splitlines():
        if line.startswith('EXCEPTION '):
            return line.strip()
    return None


def same_value(s, h, hw_sp0, code=None):
    """Whether the simulator's value s and the console's h agree. A value in the simulator's stack is an address in the
    caller's frame: it agrees when it is the same offset from each side's stack pointer at the function's entry. A value
    in the function's own code (code = (start, end)) agrees through any mirror: the console runs the code uncached."""
    if hw_sp0 is not None and SIM_STACK[0] <= (s & 0x1FFFFFFF) < SIM_STACK[1]:
        return (s - SIM_SP0) & M32 == (h - hw_sp0) & M32
    if code and (code[0] & 0x1FFFFFFF) <= (s & 0x1FFFFFFF) < (code[1] & 0x1FFFFFFF):
        return (s & 0x1FFFFFFF) == (h & 0x1FFFFFFF)
    return s == h


def compare_calls(sim, hw, hw_sp0=None, code=None):
    """The differences between the simulator's calls and the console's, in order: the count, each target, and each
    argument the simulator saw set for the call (a register or stack word not set for it is a leftover, not an
    argument, and is not compared). Stack addresses are compared as offsets (same_value)."""
    if hw == 'OVERFLOW':
        return ['calls: the console made more calls than the program keeps (simulator %d)' % len(sim)]
    why = []
    if len(sim) != len(hw):
        why.append('calls: simulator %d, console %d' % (len(sim), len(hw)))
    for i, (s, h) in enumerate(zip(sim, hw)):
        if s['to'] != h['to']:
            why.append('call %d: to simulator %08X, console %08X' % (i + 1, s['to'], h['to']))
            continue
        for k in range(4):
            if s['chg'][k] and not same_value(s['args'][k], h['args'][k], hw_sp0, code):
                why.append('call %d r%d: simulator %08X, console %08X' % (i + 1, 4 + k, s['args'][k], h['args'][k]))
        if s['stackchg'] and not same_value(s['stack'], h['stack'], hw_sp0, code):
            why.append('call %d stack: simulator %08X, console %08X' % (i + 1, s['stack'], h['stack']))
    return why


def compare(sim, hw, code=None):
    """-> (status, why). Only the words the case set are compared (the program prints every word any case checks);
    code = (start, end) of the function's bytes, for addresses in it (same_value)."""
    if hw is None:
        return 'NO CONSOLE RESULT', 'the console printed nothing for this case'
    why = []
    if not same_value(sim['r0'], hw['r0'], hw.get('sp'), code):
        why.append('r0: simulator %08X, console %08X' % (sim['r0'], hw['r0']))
    for a in sorted(sim['mem']):
        s, h = sim['mem'][a], hw['mem'].get(a)
        if s != h:
            why.append('%08X: simulator %08X, console %s' % (a, s, '-' if h is None else '%08X' % h))
    why += compare_calls(sim.get('calls') or [], hw.get('calls') or [], hw.get('sp'), code)
    return ('DIFFER', '; '.join(why)) if why else ('MATCH', '')


def fmt(r):
    return 'r0=%08X ' % r['r0'] + ' '.join('%08X=%08X' % (a, v) for a, v in sorted(r['mem'].items()))


def verify(blob, base, entry, cases, sim_runner, hw_runner, log, stubs=(), image=None):
    """Run every runnable case on both sides. sim_runner(case) -> the simulator's JSON; hw_runner(c_source, info)
    -> the console's printed text. -> one row per case: {index, status, why, sim, hw}."""
    rows, runnable, data = [], [], {}
    for i, case in enumerate(cases):
        p = parse_case(case)
        row = {'index': i, 'status': None, 'why': '', 'sim': None, 'hw': None}
        rows.append(row)
        if p['unsupported']:
            row['status'], row['why'] = 'NOT RUN', p['unsupported']
            log('case %d: NOT RUN, unsupported %s' % (i + 1, p['unsupported']))
            continue
        try:
            raw = sim_runner(case)
            row['sim'] = sim_result(raw, p['pokes'])
        except SimError as e:
            row['status'], row['why'] = 'NOT RUN', 'simulator: %s' % e
            log('case %d: NOT RUN, simulator error: %s' % (i + 1, e))
            continue
        out = outside_ram(raw.get('reads') or [])
        if out:
            row['sim'] = None
            row['status'], row['why'] = 'NOT RUN', 'reads %s, outside RAM: the simulator answers 0 there, the console the real bytes' % out
            log('case %d: NOT RUN, %s' % (i + 1, row['why']))
            continue
        if image:
            data.update(data_words(raw.get('reads') or [], image))
        log('case %d: simulator  %s' % (i + 1, fmt(row['sim'])))
        runnable.append((row, p))
    if not runnable:
        return rows
    checks = sorted(set(a for _, p in runnable for a, _ in p['pokes']))
    for t in stubs:                                  # a word under a stub is the stub's, not data
        for a in [a for a in data if (t & 0x1FFFFFFF) <= (a & 0x1FFFFFFF) < (t & 0x1FFFFFFF) + 20]:
            del data[a]
    if data:
        log('data: %d word(s) the original reads, poked before every case' % len(data))
    src = render_harness(blob, base, entry, [p for _, p in runnable], checks, stubs, data)
    log('console: %d case(s) sent' % len(runnable))
    text = hw_runner(src, {'cases': len(runnable)})
    got = parse_output(text)
    crash, crashed_in = parse_crash(text), None
    for n, (row, _) in enumerate(runnable):
        row['hw'] = got.get(n)
        if row['hw'] is not None:
            log('case %d: console    %s' % (row['index'] + 1, fmt(row['hw'])))
        if row['hw'] is None and crash and crashed_in is None:
            # the cases run in order in one program: the crash is in the first one with no result
            crashed_in = row['index'] + 1
            row['status'], row['why'] = 'CONSOLE CRASH', crash
        elif row['hw'] is None and crashed_in is not None:
            row['status'], row['why'] = 'NOT RUN', 'the console crashed in case %d' % crashed_in
        else:
            row['status'], row['why'] = compare(row['sim'], row['hw'], (base, base + len(blob)))
        log('case %d: %s%s' % (row['index'] + 1, row['status'], (' - ' + row['why']) if row['why'] else ''))
    return rows


# ---- the command line: the real simulator and the real console -------------------------------------------------

class PortError(Exception):
    pass


def serial_candidates(names):
    """The USB serial adapters among device names (the call-out devices on macOS, ttyUSB on Linux), sorted."""
    return sorted(n for n in names
                  if re.match(r'^/dev/(cu\.usbserial|cu\.usbmodem|ttyUSB|ttyACM)', n))


def find_port(candidates, probe):
    """The candidate whose probe(port) text says dcload-serial. The adapter's number changes when it is replugged,
    so the port is found by asking, never named."""
    if not candidates:
        raise PortError('no USB serial adapter found (is the cable plugged in?)')
    for p in candidates:
        if 'dcload' in (probe(p) or ''):
            return p
    raise PortError('%s did not answer dcload\'s version request: the console should show "dcload-serial ... idle". '
                    'After a crash the loader keeps its state: replug the cable (and reboot the disc) to reset it'
                    % ', '.join(candidates))


EXPECTED_LOADER = '1.0.7-cpc'


def loader_version(text):
    """The version in the loader's answer to 'V' ("dcload-serial 1.0.7-cpc"), or None."""
    m = re.search(r'dcload-serial (\d+\.\d+\.\d+(?:-[a-z]+)?)', text or '')
    return m.group(1) if m else None


def loader_warning(version):
    """'' when the loader is the version this tool is built for, else what to say about it."""
    if version == EXPECTED_LOADER:
        return ''
    return 'the loader is %s, this tool is built for dcload-serial %s (host tool and loader are a pair)' % (
        version or 'of an unreadable version', EXPECTED_LOADER)


def wait_for_port(find, limit, interval, now=time.time, sleep=time.sleep):
    """find() until it returns a port or limit seconds have passed (it is asked at least once)."""
    start = now()
    while True:
        try:
            return find()
        except PortError as e:
            last = e
        if now() - start >= limit:
            raise PortError('%s (waited %d s)' % (last, limit))
        sleep(interval)


def probe_dcload(port, baud=57600, wait=1.5):
    """Send dcload's one-byte version request ('V') on port; return what comes back ('' for nothing)."""
    import select
    import termios
    try:
        fd = os.open(port, os.O_RDWR | os.O_NOCTTY | os.O_NONBLOCK)
    except OSError:
        return ''
    try:
        speed = getattr(termios, 'B%d' % int(baud))
        a = termios.tcgetattr(fd)
        a[0], a[1], a[3] = 0, 0, 0
        a[2] = termios.CS8 | termios.CREAD | termios.CLOCAL
        a[4] = a[5] = speed
        a[6][termios.VMIN], a[6][termios.VTIME] = 0, 0
        termios.tcsetattr(fd, termios.TCSANOW, a)
        termios.tcflush(fd, termios.TCIOFLUSH)
        os.write(fd, b'V')
        out, end = b'', time.time() + wait
        while time.time() < end:
            r, _, _ = select.select([fd], [], [], 0.1)
            if r:
                out += os.read(fd, 256)
        return out.decode('ascii', 'replace')
    finally:
        os.close(fd)


def simulator_path(repo):
    """The decomp repo's simulator (tools/sim/sh4sim.py)."""
    return os.path.join(repo, 'tools', 'sim', 'sh4sim.py')


def include_dirs(runtime):
    """Where the program's headers are: the loader's own target-inc beside the runtime (its types replace the
    toolchain's for the syscall header) first, then the runtime itself."""
    inc = os.path.join(os.path.dirname(os.path.abspath(runtime)), 'target-inc')
    return ([inc] if os.path.isdir(inc) else []) + [os.path.abspath(runtime)]


def read_text(path):
    with open(path) as f:
        return f.read()


def find_function(repo, name):
    for line in read_text(os.path.join(repo, 'functions.txt')).splitlines():
        parts = line.split()
        if len(parts) >= 4 and parts[0] == 'F' and parts[3] == name:
            return int(parts[1], 16), int(parts[2])
    raise SystemExit('hwverify: %s is not in functions.txt' % name)


def find_cases(repo, name):
    root = os.path.join(repo, 'tests')
    for unit in sorted(os.listdir(root)):
        p = os.path.join(root, unit, name + '.json')
        if os.path.isfile(p):
            d = json.load(open(p))
            return d if isinstance(d, list) else d.get('dev', []) + d.get('holdout', [])
    raise SystemExit('hwverify: no tests/*/%s.json' % name)


def main(argv=None):
    ap = argparse.ArgumentParser(description='Run a function\'s test cases on the simulator and on the Dreamcast.')
    ap.add_argument('repo')
    ap.add_argument('function')
    ap.add_argument('--port')
    ap.add_argument('--baud', default='57600')
    ap.add_argument('--runtime', help='folder with crt0.o dcload-syscall.o dcload-syscalls.o dcload-syscalls.h dc4.x')
    ap.add_argument('--log', help='also write the log here')
    ap.add_argument('--timeout', type=int, default=60)
    ap.add_argument('--wait', type=int, default=0, help='seconds to keep asking for the console before giving up')
    ap.add_argument('--dry-run', action='store_true', help='write the C program and stop')
    a = ap.parse_args(argv)
    repo = os.path.abspath(a.repo)

    logf = open(a.log, 'a') if a.log else None

    def log(msg):
        line = '%s  %s' % (time.strftime('%H:%M:%S'), msg)
        print(line)
        sys.stdout.flush()
        if logf:
            logf.write(line + '\n')
            logf.flush()

    start, size = find_function(repo, a.function)
    base = int(read_text(os.path.join(repo, 'BASE')).strip(), 16)
    exe = open(os.path.join(repo, '1ST_READ.BIN'), 'rb').read()
    code = exe[start - base:start - base + size]
    end = pool_end(code, start)
    blob = exe[start - base:end - base]
    cases = find_cases(repo, a.function)
    log('function %s at %08X, %d bytes, copied %d (to %08X); %d case(s)' % (a.function, start, size, len(blob), end, len(cases)))
    stubs, problems = call_targets(blob, start, size)
    problems += stub_problems(stubs, start, end)
    if problems:
        log('not run: %s' % '; '.join(problems))
        return 2
    if stubs:
        log('stubs for %d callee(s): %s' % (len(stubs), ' '.join('%08X' % t for t in stubs)))

    tmp = tempfile.mkdtemp(prefix='hwverify-')

    def sim_runner(case):
        c = dict(case, exe=os.path.join(repo, '1ST_READ.BIN'), base='%08X' % base, entry='%08X' % start,
                 end='%08X' % (start + size))
        c.pop('about', None)
        path = os.path.join(tmp, 'case.json')
        json.dump(c, open(path, 'w'))
        r = subprocess.run([sys.executable, simulator_path(repo), 'run', path],
                           stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
        try:
            return json.loads(r.stdout)
        except ValueError:
            raise SimError((r.stderr or r.stdout).strip()[:200])

    def hw_runner(src, info):
        cpath = os.path.join(tmp, 'harness.c')
        open(cpath, 'w').write(src)
        log('C program: %s' % cpath)
        if a.dry_run:
            return ''
        if not a.runtime:
            raise SystemExit('hwverify: --runtime is needed (or --dry-run)')
        port = a.port
        if not port:
            try:
                port = wait_for_port(lambda: find_port(serial_candidates(glob.glob('/dev/*')),
                                                       lambda p: probe_dcload(p, a.baud)), a.wait, 3)
            except PortError as e:
                log('console not found: %s' % e)
                raise SystemExit(2)
            log('console found on %s' % port)
            warn = loader_warning(loader_version(probe_dcload(port, a.baud)))
            if warn:
                log('WARNING: %s' % warn)
        ld = os.path.join(a.runtime, 'dc4.x')
        if not os.path.exists(ld):
            ld = os.path.join(a.runtime, 'dc.x')
        moved = os.path.join(tmp, 'harness.x')       # the program out of the game's way (moved_script)
        open(moved, 'w').write(moved_script(read_text(ld)))
        ld = moved
        elf = os.path.join(tmp, 'harness.elf')
        cc = ['sh-elf-gcc', '-O2', '-ml', '-m4-single-only'] + ['-I' + d for d in include_dirs(a.runtime)]
        for cmd in (cc + ['-c', cpath, '-o', os.path.join(tmp, 'harness.o')],
                    cc + ['-Wl,-T' + ld, '-nostartfiles', '-nostdlib',
                          os.path.join(a.runtime, 'crt0.o'), os.path.join(a.runtime, 'dcload-syscall.o'),
                          os.path.join(a.runtime, 'dcload-syscalls.o'), os.path.join(tmp, 'harness.o'),
                          '-o', elf, '-lgcc']):
            r = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, universal_newlines=True)
            if r.returncode:
                log('build failed: %s\n%s' % (' '.join(cmd[:2]), r.stdout))
                raise SystemExit(2)
        nm = subprocess.run(['sh-elf-nm', elf], stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                            universal_newlines=True).stdout
        problem = edata_problem(edata_from_nm(nm))
        if problem:
            log('not uploaded: %s' % problem)
            raise SystemExit(2)
        log('_edata %08X: aligned' % edata_from_nm(nm))
        prog_end = ([int(x.split()[0], 16) for x in nm.splitlines() if x.split()[-1:] == ['_end']] or [0])[0]
        lo = PROGRAM_AT & 0x1FFFFFFF
        over = [t for t in stubs if (t & 0x1FFFFFFF) < (prog_end & 0x1FFFFFFF) and lo <= (t & 0x1FFFFFFF) + 20]
        if over:
            log('not uploaded: the stub for %s would overwrite the program itself (%08X-%08X)'
                % (' '.join('%08X' % t for t in over), PROGRAM_AT, prog_end))
            raise SystemExit(2)
        log('uploading to the console (%s, %s baud)' % (port, a.baud))
        p = subprocess.Popen(['dc-tool-ser', '-t', port, '-b', a.baud, '-x', elf],
                             stdout=subprocess.PIPE, stderr=subprocess.STDOUT, universal_newlines=True)
        try:
            text = p.communicate(timeout=a.timeout)[0]
        except subprocess.TimeoutExpired:
            p.kill()
            text = p.communicate()[0]
            log('the console did not finish in %d s; output so far is used' % a.timeout)
        for line in text.splitlines():
            log('console> %s' % line)
        return text

    rows = verify(blob, start, start, cases, sim_runner, hw_runner, log, stubs, (base, exe))
    n = {}
    for r in rows:
        n[r['status']] = n.get(r['status'], 0) + 1
    log('result: ' + ', '.join('%d %s' % (v, k) for k, v in sorted(n.items())))
    return exit_status(rows, a.dry_run)


def exit_status(rows, dry_run):
    """0 every case matched (or --dry-run wrote the program), 1 a case did not match on the console (DIFFER, NO CONSOLE
    RESULT, CONSOLE CRASH), 2 nothing could be run."""
    if not any(r['sim'] for r in rows):
        return 2
    if dry_run:
        return 0
    return 1 if any(r['status'] in ('DIFFER', 'NO CONSOLE RESULT', 'CONSOLE CRASH') for r in rows) else 0


if __name__ == '__main__':
    sys.exit(main())
