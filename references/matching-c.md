# Getting a source file to match

What the C side of a Katana decomp needs (where it was learned: `evidence.md`). The repo's `AGENTS.md`
has the short version; this is the detail.

## The unit is the original source file, not the function

The Hitachi compiler shares one literal pool among several functions of a file (a function's
`mov.l @(disp,pc)` can load a word placed after a *later* function), and `bsr` only reaches
functions of the same file. So C replaces asm one whole file at a time, and only once every
function in it matches.

Finding a unit's extent from the asm:
- it starts right after the previous file's last literal pool and its padding;
- it ends after its own last pool (pools are `.DATA.L` runs after an `rts` and its delay slot);
- every pool word it loads lies inside it, and every `bsr` target too.

Both ends must be function boundaries in `functions.txt`. The analysis misses functions
(`missed_funcs.py`); a unit that swallows a leaf the split does not have comes out short by
that leaf's size. `units.py` now refuses such a unit.

## Compiler and flags

- The flags of the reference decomp's matching build reproduce Katana game code:
  `-cpu=sh4 -endian=little -fpu=single -division=cpu -round=nearest -pic=0 -macsave=0
  -optimize=1 -size -string=const -section=p=P,c=C,d=D,b=B` (in `build.sh`).
- `-size`, `-speed` and `-optimize=1` alone gave the same code on what was tried; `-optimize=0` is
  very different (everything through the stack) and easy to recognise.
- **`-align16`**: library-style code pads every function *and*
  branch targets to 16 or 32 bytes with `nop`s. Seeing `nop` runs before function starts or
  before an isolated `rts` means `-align16` for that unit. Game code had none.
- **Compiler version**: SHC 5.1 Release 04 (SDK R1.42J), Release 08 (SDK R9, Nov 1999) and Release
  11 (SDK R10.1, May 2000) gave byte-identical output on everything compared. A difference that survives every rewording
  is still more likely the C than the compiler: check another version once, then keep rewording.

## Layout the compiler does not control

- **0xEE fill.** Gaps the compiler reserves (`.RES`, before a pool to align it) and the padding up
  to the next file were filled with `0xEE` by the original link. The SDK's `lnk` (6.0A) and
  `optlnksh` have no fill option, so `fill.py` writes them out explicitly.
- **Section alignment.** A C object declared `ALIGN=16` next to asm files declared `ALIGN=2` is
  not kept in input order by `lnk`: it is moved to the end of the program. `fill.py` therefore
  declares the section `ALIGN=2` and spells every `.ALIGN` out as `nop`s, computed from the unit's
  known start address (SH-4 instructions are all 2 bytes, so offsets are easy to count).
- **Constant data (`@data`).** Initialised local arrays, const tables and string literals go to the
  object's `C` section, which the original link put in the data area, each file's in file order,
  far from its code. A unit with any of them adds `@data <dstart>-<dend>` to its `@unit` line:
  `fill.py` splits the `C` section into its own piece laid out from `<dstart>` (alignment as zero
  bytes), `units.py` links that piece in place of the asm files in that range, and labels shared
  by the two pieces get unit-unique names. Its ends must be asm file boundaries: add them to `functions.txt` as `D <addr> 0 data_<addr>`
  (a data boundary: it splits the asm like an `F` line but is not counted as a function). The
  range is the unit's whole `C` section: find it from
  the code's literal pool (the addresses it loads) and the copy sizes; `fill.py` refuses data over
  `<dend>` and notes data short of it. Inside the range the order is source order, which also
  orders the unit's functions and statements. Writable initialised data (`D`) and zeroed data (`B`)
  are not supported yet: keep those variables in asm (`symbols.txt`).
- **The asm route.** `build.sh` compiles C to assembly (`-code=asm`), post-processes it and
  assembles it with `asmsh`, instead of taking `shc`'s object directly: that is what makes the
  fill and the alignment controllable.

## Comparing while iterating

A whole-file byte compare is misleading: the first function that is one instruction off shifts
everything after it. Compare per function, using the linker map for where each of your functions
landed, and ignore the displacement byte of `mov.l/mov.w @(disp,pc)` and of `bsr/bra` until the
layout before it matches (those only change because something moved). Fix functions in address
order: when an earlier one matches, later ones often follow.

## Idioms that changed register allocation

| the original had | written as |
|---|---|
| the call's result tested in `r0` and kept in `r5` | `if ((e = alloc(size)) != 0)` (not `e = alloc(size); if (e)`) |
| `cmp/eq r2,r14` vs `cmp/eq r14,r2` | the operand order of `==` (`e == list.next` vs `list.next == e`) |
| a value tested right after being copied, not re-read | `if ((e->prev = before->prev) == 0)` |
| the entry `mov #8,r5; cmp/hs r5,r4` with the argument kept in `r4` | a `while` loop instead of `for`, with the list head loaded before it |
| a flag test that jumps to a padded `rts` | `if (flag == 0) return;` before the work, not `if (flag) { ... }` |
| a bit field set from a call's result | `f.bit = g() ? 1 : 0;` (not `g() != 0`) |
| a store through a computed address (`mov.w off,r2; add rP,r2; mov.l rX,@r2`), not `@(r0,rP)` | a whole-word bit field, `unsigned int f : 32;` |
| flag tests with no `extu.b` | one-bit fields in a struct, not `flags & mask` on a byte |
| a global read at constant offsets (the pool holds `symbol+offset`) | the global as a struct and its members, not array indexing |
| a different block order and different stack slots | the if/else order: it decides both (the order locals are declared in changed nothing) |
| a temporary kept in a register where you got a spill | declare it in the block that uses it, not at function scope |
| a different register holding a shared constant | `unsigned` on the field or variable that uses it |

What did *not* move anything: `-speed` vs `-size`, signed vs unsigned parameters, `register`,
explicit casts on null pointers.

## Compiler runtime routines

The code calls a few routines from the compiler's own library (`sh4nlfzn.lib`): `__modls` (signed
modulo), `__bfslu` (bit-field store), `__quick_evn_mvn` / `__quick_odd_mvn` (block copies), and
others. They are hand-written assembly, typed as data in the library's link map; the kick-off's
`sdk_sigs.sh` hashes them too (code-section data symbols). In `functions.txt` they carry one
underscore less (`_modls`): `split_asm.py` exports `_<name>`, so the label is the compiler's own
name and a C unit calling them links without `symbols.txt` entries.

## Pitfalls

- Docker Desktop and colima default to 2 GB of memory: one Ghidra job at a time, and the compiler
  loop in its own container.
- Mount only folders under your home directory into containers (`/private/tmp` arrives empty).
- The compiler's temp folder (`SHC_TMP`) must exist inside the container.
- `SHC_LIB`, `SHC_INC` and `SHC_TMP` are Windows paths for `wibo`: `Z:\` is the container's `/`.
