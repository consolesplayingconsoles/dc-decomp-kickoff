# Matching C units: the header, the options, and what changes by mode

A matching unit is a file under `src/` whose first line is an `@unit` header. `build.sh` compiles it with the SDK's `shc`, lays the result out
like the original (`tools/1-2-baseline/fill.py`), assembles it and links it in place of the asm files in its range; the build must still
print `MATCH`. In a project with `MODE: matching` (`status.txt`) this is what "done" means. In an `equivalent` project it is the bonus
tier next to the cases (`tools/equiv.py`). The same tools serve both; nothing here changes a unit that does not ask for it.

## The header

```
/* @unit <start>-<end> [@data <dstart>-<dend>] [@ddata <a>-<b>] [@bdata <a>-<b>] [options] */
```

Addresses are hex. Every range starts and ends on an asm file boundary (add the address to `functions.txt`: `F <addr> 0 FUN_<addr>` for a
function start, `D <addr> 0 data_<addr>` for a data boundary).

| part | what |
|---|---|
| `@unit A-B` | the code: the asm files starting in `[A, B)` give way to `build/obj/c_<name>.obj` |
| `@data A-B` | the constant data (shc's C section: const tables, string literals) as its own piece at that range |
| `@ddata A-B`, `@bdata A-B` | initialised and zeroed variables (D and B sections) as pieces of their own; `c_<name>_ddata.obj`, `c_<name>_bdata.obj` |
| options with no `+` | go to `shc` (`-align16`, `-macsave=1`, `-speed`, ...) |
| options starting with `+` | go to `fill.py` or `build.sh` (below) |

A unit may sit in a folder of `src/` (`src/<dir>/<file>.c`): its name is then `<dir>/<file>` and its objects `c_<dir>_<file>`. A C file with no
`@unit` header is not a unit (equivalent C, checked by `equiv.py`, kept out of the build). `tools/1-2-baseline/units.py` is the one parser of
the header.

## The `+` options (all opt-in)

A unit that asks for none gets the layout every earlier unit has: `.ALIGN` as `0x0009` nops, reserved gaps `0xEE`, the tail `0xEE` to its end
(`tests/fillopts` checks it). `fill.py`'s docstring says what each does.

| option | what the original has that no compiler option produces |
|---|---|
| `+pool32` | each literal pool on a 32-byte boundary, the gap before it the word `0x0900`, the rest to the next file zero bytes |
| `+tail0900` | with `+pool32`, the tail of the unit is `0x0900` words (more code of the same file follows), not zero bytes |
| `+pool00` | the gap a literal pool reserves between its 16-bit and 32-bit entries is zero bytes, not `0xEE` (implied by `+pool32`) |
| `+poolafter=f1,f2` | a literal pool of its own right after these functions |
| `+synth16` | 16-bit constants built with `mov #hi; shll8 [; add #lo]`, and 128 to 255 with `mov #v-256; extu.b`, as a compiler that no available SHC matches does |
| `+asmfunc=f1[:end],f2` | functions whose C does not rebuild the bytes stay the original's instructions inside the unit |
| `+poolkeep=`, `+poolbra=`, `+brafpool=`, `+onepool`, `+hoist` | other places the original link put a pool |
| `+<x>flags` | another set of `shc` flags in place of `tools/1-2-baseline/shc_flags.txt`: `shc_flags.<x>.txt`, kept in the repo (a game that builds different source files with different flags) |
| `+r04` | compile with another `shc` release, from `SDK_R04_PATH` in `.env` (the folder holding its `shc.exe`); the build stops with a message when it is not set |

A difference no rewording moves is worth checking against another compiler release before writing it off; when all releases agree, it is the C.

## Tools

- `python3 tools/fcmp.py src/<file>.c [function ...] -v`: compiles the file with the build's flags and compares each function with the
  original instruction by instruction. `--score` prints the number the permuter uses.
- `python3 tools/permute.py src/<file>.c <function>`: tries rewrites that keep the meaning, kept when the score gets no worse.
- `shc` flags live in one file, `tools/1-2-baseline/shc_flags.txt`; `build.sh` and `fcmp.py` read it.

## Code overlays

A game that loads code from the disc at run time (stages, bosses, events) has overlays: `references/overlays.md`.
