# Equivalent C at scale (the pipeline)

How to turn many small functions into Equivalent C quickly and reliably, learned from a pilot of 100 SDK
library functions written by five parallel workers (91 Equivalent on the first full run, 20 minutes in
all) and from the game's own small functions before it. It is organised by the steps of the run: what the check compares applies to
all of them, then the parts that belong to step 4 (boosts), step 5 (script-generated decomp) and step 6 (agentic decomp). The loop itself is
in the repo's `AGENTS.md`; this is what makes it fast.

## All steps: the check

### What the check compares (tools/equiv.py)
Calls by target and by the arguments the callee takes, read from the prototype the C file declares for
it: registers a call leaves over are not arguments. A pointer into the simulator's stack is "the stack":
a local's address is the compiler's frame layout. The compiler's own helpers (`_divls`, `_quick_odd_mvn`,
anything named `_...` in `functions.txt`) run for real in both versions, so a division the original does
by helper and the C inlines agree, and a struct copy is compared by what it wrote. Memory writes by their
final value per address; the return register by the prototype; `-q` prints only what is not Equivalent.
The final SR is compared too, without its M, Q, S and T flags (a condition flag left over is not behaviour); a
case may set the starting SR with `"sr"`, so a function that saves and restores the interrupt mask is checked
with several masks.

## Step 4: boosts

### Carrying the C to another game
`scripts/tools/4-boosts/port_equiv.py <source repo> <destination repo>` finds the source's Equivalent functions in the
destination by masked code, maps globals and callees from the aligned pools, ports the C and the cases
and lets the destination's own `equiv.py` decide. Between two NAOMI games it moved 39 library functions
(CT to VT) and 46 (VT to CT) with no hand work; what does not match is a different library version.
Port one way only: once the shared library has gone from the richer decomp to the other, porting back finds little and its renames can break the
destination's callers (see `evidence.md`). Run `build.sh` and the full `equiv.py` sweep after every port. A sibling decomp is an offer: the user
names the repo (it can be one of their own), and nothing else is read.

## Step 5: script-generated decomp

### Generated Equivalent C (scripts/tools/5-generated/gen_equiv)

Time: drawing the cases is the slow part (the original runs in the simulator for every candidate case). It prints a progress line every ten functions; run it detached and keep working. How long it takes depends on the machine, so the doc gives no figures: measure them with the try run below.

`python3 tools/5-generated/gen_equiv [max size]` writes Equivalent C for the functions that need no thinking and keeps only the ones
`equiv.py` calls Equivalent: straight-line code, constant and argument stores, getters, forward `if`/`else`/early
returns, loops, calls to named functions, single-precision floats. It writes `src/gen_<letter>.c` and
`tests/gen_<letter>/` (22 cases each: values from a fixed set plus the constants the code compares against, calls
answered with varied results).

The run is long on a big game and prints progress as it goes; it runs one round over the whole game (smallest functions first) and writes the passing functions when it ends; the functions it cannot do are not retried (retry rounds found nothing, see evidence.md). The first time, tell the user: "we'll do a short try run to be able to estimate bigger runs better", and run it on the smallest functions only (a small max size), detached. Then report what it measured (seconds per function, how many passed) and offer options based on that data: each option says its gain and its wait as ranges, not exact numbers (for example "5 to 10% more of the functions", "1 to 2 hours"; the real values come from the try run on the user's machine); a range is enough to plan and that the machine stays busy meanwhile, so the user can plan around it. Run the chosen option detached. Later runs reuse the measured seconds per function. People accept waiting when the work is done for them and they know in advance how long it takes.

How it reads control flow (`gen_cfg.py` builds the graph, `gen_core.py` writes the C): the code is followed by
execution, not top to bottom, so literal pools in the middle of a function are never read. Each conditional branch
becomes an `if` / `else` between its two arms and their nearest common successor (the immediate post-dominator); an arm
that returns, breaks or continues is written as `if (c) { ...; return; }` with the rest after it. A register the arms
leave different becomes a variable assigned in each arm. A backward branch makes a loop (natural loop of the graph): a
register that is read in the next pass and changed by the loop becomes a C variable updated where the instruction runs
(the others stay expressions), and the loop is written as `while`, `do { } while` or `for (;;)` with `break` /
`continue`. The registers that need a variable are found by a trial pass with markers on the candidates.
Skipped, with a reason: a loop with several exits that do not lead on to one another, a loop that changes a stack
local, a jump table, an indirect call, branches that share a join in a way the arms cannot nest.

`python3 tools/5-generated/gen_equiv --known` is the check of the generator itself: it writes C for functions already proven
Equivalent and tests it, restoring `tests/equivalent.txt` and `docs/equivalent.md` afterwards.

Limits: no jump table, no indirect call, no stack arguments, no address of a local; prototypes are guessed (ints and
floats from the registers set before the call); the cases are random values (in a loop function small ones, and only
those the original finishes on), so a branch they never reach can pass by luck. The C is plain (temps `t0`, hex
stores): report it apart from hand-written C, and read a generated function before building on it.

### How good "Equivalent" is: instruction coverage and the two tiers
Equivalent means the C agreed with the original on the cases, so it is only as strong as the cases. `equiv.py` prints, for each
function, how many of the original's instructions the cases ran ("212 of 220 instructions": the listed bytes without literal
pools and without the padding after the last return). An instruction no case ran is a branch nobody checked.

Measured on Crazy Taxi (2026-10-21): the cases run 82.7% of the instructions of the 2,667 functions found Equivalent (hand-written
code ran 98% of its instructions, generated code lower; random inputs cannot get through a chain of guards, so the first cases stop at
the first guard). There is **no gate**: a function that passes is done, however much the cases ran. The quality figure is the
**total test coverage**: instructions the cases ran, summed over every Equivalent function, divided by their instructions
(`tools/progress.py` prints it and the badge states it). Each function's own figure stays in `docs/equivalent.md`; a function with
nothing to compare (it returns nothing and no case showed a write, a call or a device access) passes with "0 of N" and counts as done
with no coverage.

Two kinds of effort, in this order:
1. **Script-generated C.** `gen_equiv` writes C and cases, and the check keeps what passes. Report it apart from hand-written C.
   The cases come from the draw: random candidates, growth guided by the original's own coverage (take the case that reaches the
   most code, change one memory word, register or call result to a value the code compares against, keep the case if it runs a new
   instruction), and **directed cases** that flip a branch only one side of which any case reached (found from where each value came
   from: an argument, a loaded word, a call result), with rescue chains for wait loops.
2. **Raise the coverage.** `--direct` runs the directed cases on functions under a target and `--retest` draws again for functions
   already generated. A function whose C fails on the new cases was wrong on a branch the old ones never reached: it is listed with
   the first difference, and its old cases stay.

### Where a function stands
Every function that is not done is in one of these states, each named for the first step it has not passed
(`tools/5-generated/remaining.py --table`, the same rows as the README's Progress block):

| State | Meaning |
|---|---|
| Not written C | the reader has not produced C for it yet |
| Written C with errors | the reader could not write C (the reason is listed) |
| Not drawn | no test cases yet |
| Drawn with errors | the draw found no case the original finishes on, or timed out |
| Checked with errors | the C differs from the original on the cases, or does not compile |
| Done | the check passed |

Functions the compiler has no C for (control registers the SDK headers have no intrinsic for, registers other than r4-r7 read as inputs,
double precision under `-fpu=single`) are counted apart as "No C form" and leave the denominator.

### Not losing work between runs
- `state/results.jsonl` (`tools/ledger.py`) records every outcome; a case set is archived before it is replaced.
- `state/kept/<function>.json` keeps the C, the cases and the first difference of everything that reached the check and did not pass.
  `gen_equiv --recheck [--rebuild]` checks it again in seconds after a fix to the checker or the C writer, with no new draw; cases
  are reused only while the draw is the version that made them.
- Named runs (`--run NAME --jobs N`) have their own log and report and take turns on `state/.gen.lock` for the shared steps.
  Results are checked and written in **byte batches** (`GEN_BATCH`, default 8000 bytes of original code), biggest functions first, so
  one slow function never holds the rest back and an interrupted run loses only the draws in flight. The log has one line per
  function with its bytes and seconds. Give a slow machine more time with `GEN_TIME_FACTOR`, and do not start a whole-game run
  while other work needs the machine.
- `tools/consistency.py [--fix]` reports and repairs C defined twice, cases without C, C without a recorded pass; run it after runs
  overlapped and before a commit.

Coverage is also what to raise by hand: a function under its target gets cases written for the branches that no case ran.

## Step 6: agentic decomp

### Before writing any C: the three checks (a minute each, scripted)
1. **The size is right.** `python3 tools/1-2-baseline/checksizes.py [name ...]`: a function with a literal pool in
   the middle ends at its last `rts` and delay slot, not at the pool; listings made by a linear sweep stop
   too early, and the C then "stops" or jumps to an address just past the function. Fix the `F` line
   (`functions.txt`), re-run `split_asm.py` and `build.sh` (still `MATCH`). Read the function first:
   `python3 tools/shdis.py --func <name>`.
   `python3 tools/1-2-baseline/checksizes.py --hidden` is the other direction: an entry listed longer than its code has another function inside it, which
   counts as proven with the entry though no case runs it. Split it (`functions.txt`, `split_asm.py`, build `MATCH`) before counting.

2. **It can be C.** `python3 tools/5-generated/classify.py [name ...]`: the FPU register banks (`frchg`, `fschg`,
   `ftrv`), `fsrra`/`fsca` (not in the simulator), control registers other than SR, cache and trap instructions
   have no C. Moving SR to or from a register is fine: SHC's `get_imask`/`set_imask` (`_builtin_get_imask`,
   `_builtin_set_imask`) write it in C. `fipr` and `fmac` are fine with values that are exact in float (they round once). Classify
   first; do not spend a try on a function that cannot be done. Run `checksizes.py` first: the
   classifier reads only the listed size.
3. **Every name it uses exists.** `python3 tools/6-agentic/poollist.py <name>`: each literal-pool value, as a
   function (or "no F line": a function the analysis missed, add it to `functions.txt`), a RAM address
   (its name, or `MISSING`: add `<ADDR> <name>` to `symbols.txt`; a pool word that is a RAM address is the
   *address* of a global) or a plain number.

### Writing the C and the cases

For C you write by hand, `python3 tools/5-generated/gen_equiv --draw src/<file>.c` writes the cases (an existing file is kept unless `--force`): they are drawn from the
prototype and chosen by how much of the original they run, so a small function gets full coverage without a hand-written JSON. Write cases by hand only
for what coverage shows nobody reached.
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

### Things the second pilot (100 more functions in a second game) taught
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

### Running many workers at once
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

### Worker brief (fill in the batch letter, list file and repo path)
> You are one of several parallel workers writing Equivalent C for small functions of a Dreamcast decomp.
> Your list is `<file>` (address, size, name). Run commands from `<repo>`. Read `AGENTS.md` and the
> examples `src/<example>.c` with `tests/<example>/`. Write C to `src/<group>.c` and cases to
> `tests/<group>/<function>.json` (dev first, then holdout written after the C passes dev; every branch).
> Run `python3 tools/1-2-baseline/checksizes.py <name>`, `classify.py` and `poollist.py` first. Always run the check
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
