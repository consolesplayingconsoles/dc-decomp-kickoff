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

**Requirements: Docker and Python 3, on any OS (Mac, Windows, Linux).** Docker is the default:
Ghidra and the Hitachi tools run in containers, so nothing else is installed. Only if Docker is
impossible and the machine is **Linux x86_64**: `DC_LOCAL=1` (opt-in, never a default) runs the
Hitachi tools through `wibo` on PATH and Ghidra from `GHIDRA_INSTALL_DIR` (Ghidra 12.x + JDK 21).
`DC_LOCAL` does not work on macOS or Windows (`wibo` is a Linux program): there, install Docker.

**Before starting, check the machine:**
- `python3 --version` works and is 3.6 or newer (on macOS, `python3` can be Apple's stub that
  opens an install dialog: then use another Python, e.g. from python.org or Homebrew).
- `docker info` works. Docker Desktop and colima share **only your home folder** with containers
  by default: keep the work folder, the repo and the SDK under your home folder, or mounts arrive
  empty (a build that "can't find" files it plainly has is this).
- About 4 GB free (Docker images ~1.5 GB, the SDK clone, the disc copy for the game image).

**The SDK folder can have any layout** (the reference decomp's `bin/ shc/ shinobi/`, or the
Kochise repository's `.../R10.1_000518/Utl/Dev/Hitachi` + `Lib`): scripts find `asmsh.exe`,
`lbr.exe`, `lnk.exe` and the `.lib` files by name. Point `SDK_PATH` at the SDK's top folder. In the
Kochise repository that is `SDK/EXES/INSTALL KATANA SDK/INPUT/R10.1_000518` (quote it: it has
spaces); a sparse checkout of that folder is enough (`git clone --filter=blob:none --sparse`, then
`git sparse-checkout set "SDK/EXES/INSTALL KATANA SDK/INPUT/R10.1_000518"`).

**Run the Ghidra steps one at a time.** Each needs ~1 GB; Docker Desktop and colima often default to
2 GB, so two at once get killed ("Killed" in the log). `sdk_sigs.sh` switches to one library per run
when Docker has under 4 GB. **Every script fails loudly**: never continue past an empty table.

**Long steps print progress** (Ghidra analysis ~3 min, first build a few minutes, textures a
minute or two): tell the user what is running and roughly how long before starting each.

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
| a reference decomp | `github.com/consolesplayingconsoles/tbg-decomp` at tag `kickoff-reference-1` (a fork of `lhsazevedo/tbg-decomp` whose matching build works with the Kochise R10.1 SDK) | names no SDK copy has |
| object compare tool | `github.com/lhsazevedo/sh4objtest` (MIT) | step 7 |

Ask before cloning each one. Never commit the SDK, the game's files, or anything derived from them
(hash tables included) to the new repo: its `.gitignore` already excludes them.

## Procedure

0. **Name the conversation after the game.** As soon as IP.BIN gives the title (step 1), rename
   the session if your client lets you (e.g. "Dreamcast decomp kick-off: Crazy Taxi"), so a user
   running several games can tell the conversations apart.
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
   - Reference decomp: `scripts/ref_sigs.sh <SDK folder> <out>` -> `<out>/tbg.sigs`. No game disc
     needed: it clones the decomp (ask first), builds Tokyo Bus Guide's executable from it with the
     same SDK (checked against TBG's SHA-1), and hashes the library functions its link script names
     (176, 162 hashable). These match older library versions than the SDK copy (Crazy Taxi: 6 names
     only this table finds, `ADXT_StartAfs` among them). A few minutes, once.
   - Apply both with `ApplySigs.java <sigs> <out> apply` (unique matches only), then
     `DcReport.java` for the final list.
5. **The repo: ask the user where to put it.** Suggest a default (a sibling of the current folder,
   named from the IP.BIN title: lowercase, spaces to hyphens, plus `-decomp`, e.g.
   `CRAZY TAXI` -> `<parent>/crazy-taxi-decomp`), always written as an **absolute path**. Create it,
   then confirm the resolved absolute path back to the user in one line. From here on, every path
   you show (commands, summaries, the final report) is absolute: never `cd <name>` alone.
   **Split**: `scripts/split_asm.py <1ST_READ.BIN> <base> <report> <repo>`: one `.src` per function,
   data words, exported labels, `objects.txt` in link order.
6. **Make the repo publishable and build it.** A pushed repo holds no game bytes, so it must be
   able to regenerate them from each user's own disc. Into the repo:
   - copy `template/` (`build.sh`, `setup.sh`, `disc.sh`, `textures.sh`, `README.md`, `AGENTS.md`,
     `.gitignore`);
   - copy into `tools/`: `scripts/gdi_read.py`, `split_asm.py`, `text_map.py`, `file_tables.py`,
     `textures.py`, `disc_patch.py`, `apply_bin.py`, `docker_check.sh` and the `tools-image/` folder
     (so a cloned repo builds its own tools image, nothing pulled from anyone else);
   - write the base to `BASE` (hex, no `0x`); `split_asm.py` already wrote `functions.txt`;
   - fill the placeholders: in `setup.sh` and `disc.sh` `@BOOT@` (boot file from IP.BIN) and `@SHA1@` (of that
     file); in `README.md` `@TITLE@`, `@RELEASE@` (IP.BIN: title, product number, version, date,
     region), `@BOOT@`, `@SIZE@`, `@SHA1@`, `@BASE@`, `@SDK@` (main banners), `@FUNCS@`, `@NAMED@`,
     `@NAMED_SDK@`, `@NAMED_REF@`, `@LICENSE@`. No `@...@` may remain in those three files
     (`grep -n '@[A-Z_]*@' README.md setup.sh disc.sh`; `tools/` has its own `@N@` tokens, ignore).
     `@NAMED@` = functions whose name is not `FUN_...` (what `split_asm.py` prints). It can exceed
     `@NAMED_SDK@` + `@NAMED_REF@`: small wrappers (thunks) inherit the name of what they call.
   - **ask the user for a licence** for the repo's own code and docs (suggest GPL-3.0-or-later or
     MIT) and add its text as `LICENSE`.
   - `chmod +x build.sh setup.sh` (tell the user; it is one command).
   - write `.env` in the repo with `SDK_PATH="<absolute SDK folder>"` (gitignored, machine-local),
     so the user can rebuild with a plain `bash build.sh` later.
   Then put the original executable in as `1ST_READ.BIN` and run `bash build.sh`. It must print `MATCH`. First run assembles every file (minutes); later runs only
   changed ones. Always invoke scripts with `bash`/`python3`: downloads can lose execute bits.
   Finally prove the published layout works: empty `asm/`, `objects.txt`, `text-map/`, then
   `bash setup.sh <disc.gdi>` and `bash build.sh` again: `MATCH` again.
7. **Text map** (for translators, English included: any language can be a source as well as a
   target): `scripts/text_map.py <1ST_READ.BIN> <base> <report> <repo>/text-map <disc.gdi> [tier]`.
   - `exe_strings.tsv`: every executable string, the functions using it, and every pointer to it
     (what lets a translation move text somewhere bigger instead of fitting the old bytes).
   - `files.tsv`: text density per disc file and the code that opens it (where its offsets live).
   - `font.tsv`: BIOS ROM-font callers and font-looking files.
   - `image_candidates.tsv`: files that probably hold text drawn as images, with the reason.
     **Candidates only; the user decides.** Today's signal: language variants (`SPRMENG`/`SPRMJAP`).
     A single-language game gets an explicit "no automatic signal" line, never an empty file.
   - `file_tables.tsv` (`scripts/file_tables.py`): for each disc file made of repeating records, the
     table in the executable that locates them (bytes or sectors, with or without sizes). **This is
     what lets a container grow:** repack its records, rewrite that table. Boku Doraemon: STORY.PAC,
     76 scenes, (sector, length) at 0x8C04B704; rewriting it took the Catalan from ~40% to 99% and
     the game played through. Tested blind on 6 other games: no false hits, and no hits (their data
     uses other layouts), so a missing row does not prove there is no table.
   - Textures are their **own step** (`bash textures.sh <disc.gdi>`, seconds to a minute): every
     standard (PVR) texture decoded to PNG on one page with checkboxes (`text-map/textures/`), for a
     person to mark the ones with text. A game that keeps its art in its own formats gets 0 here and a
     note saying so (Crazy Taxi: 1 texture on the disc); then `image_candidates.tsv` is the lead.
   - `setup.sh` rebuilds the text map from `functions.txt`, so a cloned repo's `files.tsv` lists
     function-level users only; the kick-off's own run (from the full Ghidra report) has more.
   - Tiers: `quick` = executable only (seconds); `standard` = plus a 2 MiB sample of every disc file
     (seconds to a minute); `deep` = whole files (minutes on a full disc).
   - Density and the Shift-JIS count are heuristics: binary data scores as text sometimes.
   - **OCR is not included, on purpose.** Finding baked text in single-language games would mean
     decoding every texture (PVR, often thousands per disc) and running OCR on each: tens of
     minutes to hours, plus an OCR engine and its Japanese data, and game fonts are stylised, so it
     misses text and flags noise. If a user wants it, warn them of that cost first, and still
     present the results as candidates. A contact sheet of all textures for a human to tick is
     often faster and is the only reliable method.
8. **Game build**: `bash disc.sh <original .gdi>` writes `build/disc/`: a copy of the user's disc
   with the rebuilt executable and every file under `disc/` (same path as on the disc) written in
   place, error correction recomputed, read back to verify. A smaller file is padded; a **bigger**
   one moves into free sectors (GD-ROMs often carry a whole filler track) and its directory entry is
   repointed. To change the executable from a modified copy, `tools/apply_bin.py <repo> <original>
   <modified>` writes the changes into the asm data words; then `bash build.sh` (it prints DIFFERS,
   expected; `DC_EXPECT_CHANGES=1` makes that exit 0). Tested on Boku Doraemon: the story script at
   1.7x a scene's budget, 10 KB bigger than the original file, played through in Flycast.
9. **Hand over**: `template/AGENTS.md` is the per-function loop (asm -> instructions -> C -> match).
10. **GitHub (optional)**: print, do not run, the commands for the user:

   ```
   cd "<absolute repo path>" && git init && git add -A && git commit -m "Kick off: byte-matching split, <n> named"
   # check first: git ls-files must show no asm/, 1ST_READ.BIN or other game files
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
| `scripts/ref_sigs.sh` | reference decomp names: build TBG's executable from the decomp, hash its named functions |
| `scripts/sdk_sigs.sh` | signature table for every exported function in an SDK's libraries |
| `scripts/text_map.py` | strings with pointers, file text density, font path, image candidates |
| `scripts/file_tables.py` | tables in the executable that locate records inside disc files |
| `scripts/textures.py` | every standard texture to PNG + a contact sheet (`index.html`) |
| `scripts/disc_patch.py` | copy a GDI with files replaced in place, error correction recomputed |
| `template/disc.sh` | in the repo: build a playable disc image of the user's version |
| `template/textures.sh` | in the repo: the texture contact sheet, as its own step |
| `scripts/apply_bin.py` | write a modified executable's changes into the repo's asm data words |
| `scripts/docker_check.sh` | Docker installed vs running vs low memory, and the tools image on first use |
| `scripts/tools-image/Dockerfile` | the `dc-tools` image: small Linux + pinned, checksum-verified wibo |
| `scripts/split_asm.py` | split an executable into per-function asmsh sources + link order |
| `template/build.sh` | assemble, link (`start P(<base>)`), `elf2bin`, compare with the original |
| `template/setup.sh` | in the repo: extract + verify the user's executable, regenerate `asm/` and `text-map/` |
| `template/README.md` | the repo's README, with `@PLACEHOLDERS@` to fill |
| `template/AGENTS.md` | the decompilation loop for whoever works in the repo |
| `template/.gitignore` | keeps game and SDK material out of git (asm, executable, disc, build, text map) |
