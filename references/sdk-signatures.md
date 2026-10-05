# Naming library code by signature

Two sources of names, both turned into Ghidra function-ID hashes (`scripts/ghidra/ExportSigs.java`)
and applied with `scripts/ghidra/ApplySigs.java <sigs> <out> apply` (unique matches only; ambiguous
hashes are listed, never guessed). Check a run: matched names sorted by target address should keep
the source's library order.

## From a reference decomp

A matching decomp's link script pins SDK functions by address: `define _NAME(8CADDR)`. Turn those
into a names list (`<hex addr> <name>`, no leading underscore), import the reference game's
executable at its base, run `ExportSigs.java <names.txt> <sigs.txt>`. Tokyo Bus Guide: 176 names,
162 hashable; they named 30 functions in Crazy Taxi and 69 in Boku Doraemon.

## From the SDK's own libraries

The Katana SDK's `.lib` files hold every exported library function. Built once per SDK version,
the table applies to any game of that era in seconds (Crazy Taxi: 385 named, Boku Doraemon: 879).
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
