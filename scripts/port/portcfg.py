"""Shared setup for the port-symbol scripts (see references/port-symbols.md). Stdlib only.

Run the scripts in a work folder holding dc_features.jsonl and port_features.jsonl (from
ghidra/ExportFeatures.java). Settings come from the environment:
  PORT_LIB        the port's library with symbols (e.g. lib/arm64-v8a/libgame.so)          required
  DECOMP          the decomp repo (functions.txt, 1ST_READ.BIN, BASE)                      required
  GHIDRA_OFFSET   where Ghidra loaded the library, minus its ELF addresses (default 0x100000,
                  Ghidra's base for a shared object linked at 0)
  RUNTIME_SKIP    Dreamcast address ranges of compiler runtime helpers to ignore as callees
                  (division, struct copy): "0c080e00-0c081700,..." (ARM inlines them)
  DROP_GLOBALS    Dreamcast addresses never to pair as globals (buffers, not variables): "0c2ad000,..."
"""
import bisect, json, os, re, subprocess, sys

def need(k):
    v = os.environ.get(k)
    if not v:
        sys.exit('[ERROR] set %s (see portcfg.py)' % k)
    return v

PORT_LIB = need('PORT_LIB')
DECOMP = need('DECOMP')
OFF = int(os.environ.get('GHIDRA_OFFSET', '0x100000'), 0)
RUNTIME_SKIP = [tuple(int(x, 16) for x in r.split('-')) for r in os.environ.get('RUNTIME_SKIP', '').split(',') if r]
DROP_GLOBALS = {x.strip().lower() for x in os.environ.get('DROP_GLOBALS', '').split(',') if x.strip()}

def load(p):
    return [json.loads(l) for l in open(p) if l.strip()]

def run(*cmd):
    return subprocess.run(list(cmd), capture_output=True, text=True).stdout

def demangle(names):
    """C++ names -> 'name(args)'. -n: macOS c++filt otherwise expects Mach-O's extra underscore."""
    out = subprocess.run(['c++filt', '-n'], input='\n'.join(names), capture_output=True, text=True).stdout.split('\n')
    return dict(zip(names, out))

# the port's function symbols, keyed by Ghidra address
FUNC_SYMS = {}
for l in run('nm', '-D', '--defined-only', PORT_LIB).splitlines():
    p = l.split()
    if len(p) == 3 and p[1] in 'Tt':
        FUNC_SYMS['%08x' % (int(p[0], 16) + OFF)] = p[2]
_dem = demangle(list(FUNC_SYMS.values()))
SIGNATURE = {}            # plain name -> 'name(args)'
for n, d in _dem.items():
    SIGNATURE.setdefault(d.split('(')[0], d)

def is_original(mangled):
    """The original game's code: free C functions (_Z<digit>...) or plain C names, not the port's classes."""
    return mangled is not None and (re.match(r'_Z\d', mangled) is not None or not mangled.startswith('_Z'))

ORIGINAL_NAMES = {_dem[n].split('(')[0] for n in FUNC_SYMS.values() if is_original(n)}

# data symbols, and GOT slots that point at them (shared objects reach exported globals through the GOT)
_syms = []
for l in run('nm', '-D', '--defined-only', '-S', PORT_LIB).splitlines():
    p = l.split()
    if len(p) == 4 and p[2] in 'DdBbRrVv':
        _syms.append((int(p[0], 16) + OFF, max(int(p[1], 16), 1), p[3]))
_syms.sort()
_starts = [s[0] for s in _syms]
_symaddr = {n: a for a, sz, n in _syms}
_got = {}
for l in run('objdump', '--dynamic-reloc', PORT_LIB).splitlines():
    p = l.split()
    if len(p) >= 3 and p[1].endswith(('_GLOB_DAT', '_ABS64', '_ABS32')):
        _got[int(p[0], 16) + OFF] = p[2].split('+')[0]

def sym_of(addr):
    """Ghidra address in the port -> (data symbol, offset) or None."""
    if addr in _got and _got[addr] in _symaddr:
        return _got[addr], 0
    i = bisect.bisect_right(_starts, addr) - 1
    if i >= 0 and addr < _syms[i][0] + _syms[i][1]:
        return _syms[i][2], addr - _syms[i][0]
    return None

def dc_names():
    return {l.split()[1]: l.split()[3] for l in open(os.path.join(DECOMP, 'functions.txt'))}

def runtime_helper(a):
    v = int(a, 16)
    return any(s <= v < e for s, e in RUNTIME_SKIP)
