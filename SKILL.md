---
name: dc-decomp-kickoff
description: Kick off a matching decompilation of a Sega Dreamcast (Katana) game. Use when someone has a Dreamcast disc and wants a decomp repo started: names applied from SDK signatures and reference decomps, the executable split into one assembly file per function, and a build that reproduces the original byte for byte, ready for agents to decompile function by function.
---

# Kicking off a Dreamcast decomp

The goal is a repo in the best automatable state: it already rebuilds the original executable
byte for byte, every function is its own file, as many as possible carry real names, and the loop
for turning a function into C is written down. Decompiling the game is the work that follows.

## Getting the tools (do this first)

Installed skills often arrive as `SKILL.md` alone. This skill needs its own files (`scripts/`,
`template/`, `references/`). If `scripts/split_asm.py` is not next to this file, tell the user and
ask before cloning the skill into a tools folder (default `~/dc-tools`):

```
git clone https://github.com/consolesplayingconsoles/dc-decomp-kickoff ~/dc-tools/dc-decomp-kickoff
```

Then use that copy for every `scripts/...`, `template/...` and `references/...` path below. Do not
rewrite the tools from this text unless the clone is impossible: they encode fixes that are easy to
get wrong (multi-track discs, link address, regex blowups, linker quirks).

## Read this first: how complete this skill is

**Requirements: Docker and Python 3, on any OS.** Everything else (Ghidra, the Hitachi tools) runs
in containers. Without Docker: `DC_LOCAL=1` runs the Hitachi tools through `wibo` on your PATH
(Linux x86_64) and Ghidra from `GHIDRA_INSTALL_DIR` (Ghidra 12.x + JDK 21).

**The SDK folder can have any layout** (the reference decomp's `bin/ shc/ shinobi/`, or the
Kochise repository's `.../R10.1_000518/Utl/Dev/Hitachi` + `Lib`): scripts find `asmsh.exe`,
`lbr.exe`, `lnk.exe` and the `.lib` files by name. Point `SDK_PATH` at the SDK's top folder.

**Evidence base: one game (Crazy Taxi, Europe), tested against the suggested SDK source**
(`Kochise/dreamcast-docs`, SDK R10.1, as cloned: byte-identical build, 385 SDK names) **and a
second SDK copy laid out like the reference decomp's (same results).** Crazy Taxi: 2,389 functions, 430 named (385 from SDK
signatures, 30 from a reference decomp), 2,390 files, byte-identical rebuild with the SDK's own
assembler and linker. The C side of the loop (step 7) is described, not yet exercised here.
Everything it uses is in this skill's own folder.

## Third-party sources

The procedure needs three kinds of material. The repositories below are identified solely as
examples of the type of material required. The authors of this skill have no affiliation with, and
make no representation regarding, those repositories, their contents, or their licensing. Nothing
is retrieved without the user's express confirmation. The user is solely responsible for
determining whether they are entitled to obtain and use any such material, and may substitute any
equivalent material lawfully in their possession.

| need | example source | used for |
|---|---|---|
| Katana SDK (libraries + Hitachi `asmsh`, `shc`, `lnk`, `lbr`, `elf2bin`) | `github.com/Kochise/dreamcast-docs` (`SDK/`) | SDK signatures, the matching build |
| a reference decomp | `github.com/lhsazevedo/tbg-decomp` | extra names, the tools image (`lhsazevedo/tbg-decomp`, has `wibo`) |
| object compare tool | `github.com/lhsazevedo/sh4objtest` (MIT) | step 7 |

Ask before cloning each one. Never commit the SDK, the game's files, or anything derived from them
(hash tables included) to the new repo: its `.gitignore` already excludes them.

## Procedure

1. **Disc to executable** (`scripts/gdi_read.py`, CHD via `chdman extractcd`). Check the
   boot file in IP.BIN; `0WINCEOS.BIN` means Windows CE: stop, this skill does not apply.
2. **Base and fingerprint**: `scripts/linkbase.py`, `scripts/banners.py`. Note the SDK version the game used.
3. **Ghidra** (Docker; no Linux machine needed, the image builds on first use), with the
   executable in `<work>`:
   ```
   scripts/ghidra/dghidra.sh <work> /work proj -import /work/1ST_READ.BIN -overwrite \
     -loader BinaryLoader -loader-baseAddr <base> -processor SuperH4:LE:32:default \
     -scriptPath /scripts -preScript DcPre.java -postScript DcReport.java /work/report.txt
   ```
   Import at the base `linkbase.py` picked: at the wrong one Ghidra finds a fraction of the code.
   Never copy the `.java` scripts into `<work>`: Ghidra then finds two copies and fails to load them.
4. **Names**:
   - SDK-wide: `scripts/sdk_sigs.sh <SDK folder> <out>` -> `<out>/katana-sdk.sigs`. Any SDK layout:
     the Hitachi tools and the `.lib` files are found by name. Build once per SDK, keep it local.
     Details and gotchas: `references/sdk-signatures.md`.
   - Reference decomp: its link script's `define _NAME(ADDR)` lines -> `ExportSigs.java`.
   - Apply both with `ApplySigs.java <sigs> <out> apply` (unique matches only), then
     `DcReport.java` for the final list.
5. **The repo: ask the user where to put it.** Suggest a default (a sibling of the current folder,
   named from the IP.BIN title: lowercase, spaces to hyphens, plus `-decomp`, e.g.
   `CRAZY TAXI` -> `<parent>/crazy-taxi-decomp`), always written as an **absolute path**. Create it,
   then confirm the resolved absolute path back to the user in one line. From here on, every path
   you show (commands, summaries, the final report) is absolute: never `cd <name>` alone.
   **Split**: `scripts/split_asm.py <1ST_READ.BIN> <base> <report> <repo>`: one `.src` per function,
   data words, exported labels, `objects.txt` in link order.
6. **Build**: copy `template/` into the repo, write the base to `BASE`, put the original
   executable in as `1ST_READ.BIN`, `SDK_PATH=... ./build.sh`. It must print `MATCH`. First run
   assembles every file (minutes); later runs only changed ones.
7. **Text map** (for translators, English included: any language can be a source as well as a
   target): `scripts/text_map.py <1ST_READ.BIN> <base> <report> <repo>/text-map <disc.gdi> [tier]`.
   - `exe_strings.tsv`: every executable string, the functions using it, and every pointer to it
     (what lets a translation move text somewhere bigger instead of fitting the old bytes).
   - `files.tsv`: text density per disc file and the code that opens it (where its offsets live).
   - `font.tsv`: BIOS ROM-font callers and font-looking files.
   - `image_candidates.tsv`: files that probably hold text drawn as images, with the reason.
     **Candidates only; the user decides.** Today's signal: language variants (`SPRMENG`/`SPRMJAP`).
   - Tiers: `quick` = executable only (seconds); `standard` = plus a 2 MiB sample of every disc file
     (seconds to a minute); `deep` = whole files (minutes on a full disc).
   - Density and the Shift-JIS count are heuristics: binary data scores as text sometimes.
   - **OCR is not included, on purpose.** Finding baked text in single-language games would mean
     decoding every texture (PVR, often thousands per disc) and running OCR on each: tens of
     minutes to hours, plus an OCR engine and its Japanese data, and game fonts are stylised, so it
     misses text and flags noise. If a user wants it, warn them of that cost first, and still
     present the results as candidates. A contact sheet of all textures for a human to tick is
     often faster and is the only reliable method.
8. **Hand over**: `template/AGENTS.md` is the per-function loop (asm -> instructions -> C -> match).
9. **GitHub (optional)**: print, do not run, the commands for the user:

   ```
   cd "<absolute repo path>" && git init && git add -A && git commit -m "Kick off: byte-matching split, <n> named"
   gh repo create <owner>/<repo dir name> --public --source . --push
   ```

## Rules
- The build must match before handing over, and after every change.
- Names are only applied on unique matches; ambiguous hashes are listed, never guessed.
- Link order is address order; a file's size never changes unless its replacement matches.

## Scripts

| script | what it does |
|---|---|
| `scripts/gdi_read.py` | list / extract files from any data track of a GDI; extract IP.BIN |
| `scripts/linkbase.py` | pick the import base from self-pointer counts |
| `scripts/banners.py` | SDK module banners: name, version, build date |
| `scripts/ghidra/dghidra.sh` | headless Ghidra in Docker (image from `scripts/ghidra/Dockerfile`, built on first use) |
| `scripts/ghidra/*.java` | seed + report (`DcPre`, `DcReport`), signatures (`ExportSigs`, `ApplySigs`), queries (`Query`) |
| `references/sdk-signatures.md` | naming library code from a reference decomp or the SDK's libraries |
| `references/memory-map.md` | Dreamcast addresses worth labelling on sight |
| `scripts/sdk_sigs.sh` | signature table for every exported function in an SDK's libraries |
| `scripts/text_map.py` | strings with pointers, file text density, font path, image candidates |
| `scripts/split_asm.py` | split an executable into per-function asmsh sources + link order |
| `template/build.sh` | assemble, link (`start P(<base>)`), `elf2bin`, compare with the original |
| `template/AGENTS.md` | the decompilation loop for whoever works in the repo |
| `template/.gitignore` | keeps game and SDK material out of git |
