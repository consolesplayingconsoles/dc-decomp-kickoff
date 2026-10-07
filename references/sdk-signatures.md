# Naming library code by signature

Two sources of names, both turned into Ghidra function-ID hashes (`scripts/ghidra/ExportSigs.java`)
and applied with `scripts/ghidra/ApplySigs.java <sigs> <out> apply` (unique matches only; ambiguous
hashes are listed, never guessed). Check a run: matched names sorted by target address should keep
the source's library order.

## From a reference decomp

A matching decomp's link script pins SDK functions by address: `define _NAME(8CADDR)`. Turn those
into a names list (`<hex addr> <name>`, no leading underscore), import the reference game's
executable at its base, run `ExportSigs.java <names.txt> <sigs.txt>`. A complete decomp gives
more: every function its linker map names (`scripts/ref_sigs.sh`).

## From another decomp's names

Any decomp whose build reproduces its game's executable is a names source, not only the reference
one: a names list from its `functions.txt` (`<hex addr> <name>` for every non-`FUN_` entry) and its
executable go through `ExportSigs.java` the same way. Games from the same developer share
libraries no SDK has (a middleware or engine library): one such decomp named a sister game's
rendering-library functions that no SDK table could. Apply it with `fill`, after the SDK tables.

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
