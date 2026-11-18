# Naming library code by signature

Used in step 2 (Signature-driven baseline); the section on another decomp's names belongs to step 4 (Opportunity-driven optional boosts).

Two sources of names, both turned into Ghidra function-ID hashes (`scripts/ghidra/ExportSigs.java`)
and applied with `scripts/ghidra/ApplySigs.java <sigs> <out> apply` (unique matches only; ambiguous
hashes are listed, never guessed). Check a run: matched names sorted by target address should keep
the source's library order.

## From another decomp's names

Any decomp whose build reproduces its game's executable is a names source: a names list from its `functions.txt` (`<hex addr> <name>` for every non-`FUN_` entry) and its
executable go through `ExportSigs.java` the same way. Games from the same developer share
libraries no SDK has (a middleware or engine library): one such decomp named a sister game's
rendering-library functions that no SDK table could. Apply it with `fill`, after the SDK tables.
This is step 4 (boosts), and a sibling decomp is an offer: the user names the repo (it can be one of their own); nothing else is read.

## From the SDK's own libraries

The Katana SDK's `.lib` files hold every exported library function. Built once per SDK version,
the table applies to any game of that era in seconds.
Keep the table local: it is derived from the SDK and must not be committed.

Pipeline (all with the SDK's own Hitachi tools, run under `wibo` in a Linux container)
1. `lbr.exe`: `library <lib>` / `list` per session (one library per session) gives the module names.
2. `lnk.exe` subcommand file per library: `elf`, `print <x>.map`, `output <x>.elf`, then
   `input <lib>(<module>)` for every module, `exit`. Undefined externals (calls into other libs) are
   warnings; the ELF is written. Libraries carry no debug info, so the ELF has no symbols: names come
   from the map's EXTERNALLY DEFINED SYMBOLS list (`ENT` = code).
   - Run from the output dir: a `/` in `-subcommand=dir/x.sub` is read as an option switch.
   - Write subcommand files with `printf '%s\n'`: zsh `echo` turns `\n`, `\t`, `\a` in Windows
     paths into control characters.
3. Ghidra headless imports all ELFs (`-processor SuperH4:LE:32:default`) and `ExportSigs` in folder
   mode hashes every named function: 12,334 exported functions, 8,615 hashed (rest too short),
   4,894 distinct hashes.
4. `ApplySigs` on targets.


Only exported (non-static) functions get names. Coverage follows the SDK version: a copy from the
game's own era matches best.

## After the tables: masked comparison, position, listings (`scripts/tools/1-2-baseline/sdk_masked.py`)

Function-ID hashes need the whole function identical. A game linked with a library build no
release shipped (Sega-internal builds, a `zr` suffix in the banners) differs in a few words and
misses; short twin stubs (save-file wrappers, `set_*` command builders) hash alike and stay
ambiguous; static functions are in no map at all. Once the repo exists (`functions.txt`,
`sdk.txt`), `sdk_masked.py` runs three passes in rounds, against every `sdk_sigs.sh` table's
linked libraries (`link/*.map` and `*.elf`, kept in the table folder):
- **masked match**: the instructions compared with pc-relative load displacements, `mova`,
  branch displacements and the literal-pool words those loads reach masked (exact or a 0.85
  difflib ratio); where both sides name a pool word the names must agree; kept only when it is
  the single best and in its library's link order against the nearest named neighbours
  (16 bytes or more: tiny signature names are poor anchors); twins that tie are settled by
  that order;
- **position**: between two named neighbours as far apart in the game as in a library, every
  function the library exports between them, by offset. It names tiny functions no content
  match can, finds starts the split missed (stubs reached only through a function table), and
  shows wrong signature names on tiny thunks (Crazy Taxi: `vmsfs_ismount` where every table's
  layout has `buIsReady`);
- **listings** (`--listings <folder>`): SHC object listings (`*.lst`) print every function of a
  source file, statics included, with its offset and code. The Shinobi source dump carries 73
  (1999 builds, SHC 5.1). A file whose masked code matches the game at one of its named
  functions names all of its functions, by their source names (`search_fat_dir`, `read_dir`).
A name is used only when one source proposes it for one address and it is free; an existing
name the layout contradicts is replaced only on a function under 16 bytes, reported as suspect
otherwise. `--apply` writes `functions.txt` (renames, splits, new entries) and deletes stale
`asm/` files; re-split and build (`MATCH`: names and boundaries never change bytes).

## Games built on the NAOMI library

Arcade ports from Sega's own studios carry the NAOMI library (`nl*` maths, matrices, events,
textures, sprites, print; `nla*`, `nlsnd*`) as a block of their executable, usually between the
game's code and its data. Its signs: `nl*` names from a port or a reference, and code two games of
the same studio share byte for byte while their game code shares nothing.
- Table: the NAOMI SDK's `.lib` files through `sdk_sigs.sh` (the NAOMI dump has no `lbr.exe` or
  `lnk.exe`: copy a Katana SDK's `bin/` beside its `lib/`); its sample programs (`t.map` with a
  `t.mot` S-record image) as one more table folder (`link/<name>.map` + `<name>.mot`), which
  `sdk_masked.py` reads like a library's map and ELF.
- The block is library code: mark it in `sdk.txt` with a `range` from its first library function
  to the last code before data, or the passes (which work inside `sdk.txt`) never look at it.
  Find the ends by the matches, not by guessing: the first function the NAOMI tables name, and
  the end of the last code before data.

## When the libraries do not match: sample programs

A game built with a pre-release SDK can carry library versions no shipped `.lib` has. SDK discs
also carry compiled sample programs, often with symbols, and those link the libraries of their own
moment: a sample built with exactly the game's library version can match where every `.lib`
misses. Look for `.elf` / `.map` files under the SDK's sample folders and hash them like a decomp's
executable (names from their symbol table).

## Early (1998) SDKs

Pre-1.0 releases (Katana 0.40 and earlier) carry few banners, in an older form (`GDFS Version 0.49
1998-05-26`, which `banners.py` and `sdk_scan.py` read). Launch-era games can sit between two
releases (newer than 0.40, older than 1.0B2): expect few signature names, and look at sample
programs (above) and sister decomps.
