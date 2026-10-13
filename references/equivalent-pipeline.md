# Equivalent C at scale (the pipeline)

How to turn many small functions into Equivalent C quickly and reliably, learned from a pilot of 100 SDK
library functions written by five parallel workers (91 Equivalent on the first full run, 20 minutes in
all) and from the game's own small functions before it. The loop itself is in the repo's `AGENTS.md`;
this is what makes it fast.

## Before writing any C: the three checks (a minute each, scripted)
1. **The size is right.** `python3 tools/checksizes.py [name ...]`: a function with a literal pool in
   the middle ends at its last `rts` and delay slot, not at the pool; listings made by a linear sweep stop
   too early, and the C then "stops" or jumps to an address just past the function. Fix the `F` line
   (`functions.txt`), re-run `split_asm.py` and `build.sh` (still `MATCH`). Read the function first:
   `python3 tools/shdis.py --func <name>`.
2. **It can be C.** `python3 tools/classify.py [name ...]`: the FPU register banks (`frchg`, `fschg`,
   `ftrv`), `fsrra`/`fsca` (not in the simulator), control registers, cache and trap instructions have
   no C. `fipr` and `fmac` are fine with values that are exact in float (they round once). Classify
   first; do not spend a try on a function that cannot be done. Run `checksizes.py` first: the
   classifier reads only the listed size.
3. **Every name it uses exists.** `python3 tools/poollist.py <name>`: each literal-pool value, as a
   function (or "no F line": a function the analysis missed, add it to `functions.txt`), a RAM address
   (its name, or `MISSING`: add `<ADDR> <name>` to `symbols.txt`; a pool word that is a RAM address is the
   *address* of a global) or a plain number.

## Writing the C and the cases
- The first function of a group costs a few minutes; the rest are mechanical. Keep a generator script per
  file that writes the `tests/<file>/<function>.json` cases (helpers for pokes, floats, call returns).
- Cover every branch and edge. Write the holdout cases *after* the C passes the development ones, with
  other values (a pilot worker wrote both in one pass and said so: that is weaker evidence).
- Constants: take them from the pool bits, not from a decimal (`0x3f317217` and `0x3f317218` are different
  `ln 10`s). Compare the original's value with `struct.pack('<f', ...)`.
- A skip path that ends in a shared `rts` or a tail call returns whatever the caller left in `r0`: declare
  such a function `void`, or the check compares a leftover.
- A pool value that is a RAM address is the address of a global: pass `&g`, not `g`.
- Tail calls and calls through a table check fine: `"calls": [{}]`, with the table poked in memory.
- A callee that fills an output slot (a loop that reads a cursor it passed by pointer) is a case with
  `"poke_arg": {"r7": "<bytes>"}` on that call: the bytes are written at the address `r7` holds.
- Duplicate function names in `functions.txt` (the linker takes the first): give the copies unique names.

## What the check compares (tools/equiv.py)
Calls by target and by the arguments the callee takes, read from the prototype the C file declares for
it: registers a call leaves over are not arguments. A pointer into the simulator's stack is "the stack":
a local's address is the compiler's frame layout. The compiler's own helpers (`_divls`, `_quick_odd_mvn`,
anything named `_...` in `functions.txt`) run for real in both versions, so a division the original does
by helper and the C inlines agree, and a struct copy is compared by what it wrote. Memory writes by their
final value per address; the return register by the prototype; `-q` prints only what is not Equivalent.

## Things the second pilot (100 more functions in a second game) taught
- 16-bit pool constants (`mov.w @(...),Rn  ; =4304 (0x10d0)`) are field offsets or counts: read the decimal
  and the hex that `shdis.py` now prints; do not treat a decimal as hex.
- A pool word that is a RAM address is the address of a global; whether that global holds a pointer (a
  double dereference) is only visible in the instructions after the load.
- Stack arguments after the fourth are set with `poke` at `0DFFFF00`, `0DFFFF04`, ... (r15 starts there);
  hardware registers with `device_reads`; a call's output slot with `poke_arg`.
- A variadic callee is fine to declare `(char *fmt, ...)`: both versions leave the same registers.
  Only a function whose own definition is variadic cannot be written in C.
- A function that compiles to `_divlu` or `_modlu` needs `extern void _divlu(void); extern void _modlu(void);`
  (like `_quick_odd_mvn`) so the linker defines the helpers.
- Read each `tst` / `bf` polarity from the disassembly, not from what the code should do. A case for every
  failure branch is what shows a wrong prototype that passed by luck.
- A loop that polls millions of times cannot be covered (the mocked calls are a finite list): leave that
  path out of the cases and say so.
- `tools/shdis.py --func` on a compiled file: copy `build/equiv/<file>.bin` into a scratch dir as
  `1ST_READ.BIN` beside a `BASE` holding `0E100000` to see what the compiler made of your C.
- Pass one name to `checksizes.py`, `classify.py` and `poollist.py` per call when scripting in zsh: an
  unquoted variable holding several names is not split there.

## Carrying the C to another game
`scripts/port_equiv.py <source repo> <destination repo>` finds the source's Equivalent functions in the
destination by masked code, maps globals and callees from the aligned pools, ports the C and the cases
and lets the destination's own `equiv.py` decide. Between two NAOMI games it moved 39 library functions
(CT to VT) and 46 (VT to CT) with no hand work; what does not match is a different library version.

## Running many workers at once
- Split the candidate list into groups of about 20 (smallest, named, plain C first). One worker per group,
  its own `src/<group>.c` and `tests/<group>/`, nothing else of its own.
- Shared files are the trap: `tools/equiv.py` rewrites `tests/equivalent.txt`, `docs/equivalent.md` and
  `build/equiv/*.log`, and `functions.txt` and `symbols.txt` are edited by everyone. Run every check and every
  edit of those through one lock (a `mkdir`-based wrapper, `build/eqlock.sh <command>`), and append symbols
  only after `grep -i <address> symbols.txt globals.txt` shows no name. Use `g_<address>` for unnamed globals so
  two workers name one address the same.
- Brief each worker with the full rules (below); no git, no `build.sh`, no editing of tools. Ask for a
  table (function, state, note), the size fixes and symbols added, and the lessons.
- After they finish: re-run every group yourself (`python3 tools/equiv.py -q src/<group>.c`), re-run
  `split_asm.py` and `build.sh` (sizes changed: `MATCH`), then `progress.py`. A worker's count is a claim;
  the tool's output is the evidence.

## Worker brief (fill in the batch letter, list file and repo path)
> You are one of several parallel workers writing Equivalent C for small functions of a Dreamcast decomp.
> Your list is `<file>` (address, size, name). Run commands from `<repo>`. Read `AGENTS.md` and the
> examples `src/<example>.c` with `tests/<example>/`. Write C to `src/<group>.c` and cases to
> `tests/<group>/<function>.json` (dev first, then holdout written after the C passes dev; every branch).
> Run `python3 tools/checksizes.py <name>`, `classify.py` and `poollist.py` first. Always run the check
> through the lock: `build/eqlock.sh python3 tools/equiv.py -q src/<group>.c [function]`. Fix a wrong size
> or add a symbol only through the lock / a grep first. Never touch other files, `tools/`, `docs/`,
> `tests/equivalent.txt`, git, or `build.sh`. Blocked (the C cannot express it): say why and move on. At most
> two attempts per function, then mark it FAILED with the first DIFFERS line. Final report, under 450 words:
> a table function / address / state (EQUIVALENT n cases, BLOCKED reason, FAILED diff) / note, the size fixes
> and symbols you made, and the lessons. Report only what `equiv.py` printed.

`build/eqlock.sh`:
```sh
#!/usr/bin/env bash
cd "$(dirname "$0")/.." || exit 1
n=0; while ! mkdir build/.eqlock 2>/dev/null; do n=$((n+1)); [ $n -gt 600 ] && exit 1; sleep 2; done
trap 'rmdir build/.eqlock' EXIT
"$@"
```
