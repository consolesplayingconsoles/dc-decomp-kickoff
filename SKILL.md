---
name: dc-decomp-kickoff
description: "Kick off a decompilation of a Sega Dreamcast (Katana) game (a byte-identical build; functions done when their C behaves like the original). Use when someone has a Dreamcast disc and wants a decomp repo started: names applied from SDK signatures, the executable split into one assembly file per function, and a build that reproduces the original byte for byte, ready for agents to decompile function by function."
---

# Kicking off a Dreamcast decomp

The goal is a repo in the best automatable state: it already rebuilds the original executable
byte for byte, every function is its own file, as many as possible carry real names, and the loop
for turning a function into C is written down. Decompiling the game is the work that follows.
A function is done when its C behaves like the original (Equivalent: `tools/equiv.py` runs both
in an SH-4 interpreter on test cases and compares calls, writes and result); byte-identical C
(Matching) is the bonus tier. The repo's build keeps matching the original either way.

## Getting the tools (do this first)

This skill needs its own files (`scripts/`, `template/`, `references/`); the README's install
(a clone) brings them. If `scripts/split_asm.py` is not next to this file,
only `SKILL.md` was installed: fetch the tools yourself, without asking (they are this skill's own
public code, not third-party material), into a tools folder (default `~/dc-tools`). The tools folder always has to be
the latest version: clone it when it is absent, and when it exists update it (`git -C ~/dc-tools/dc-decomp-kickoff
pull --ff-only`; if that fails, delete the folder and clone again).

```
git clone https://github.com/consolesplayingconsoles/dc-decomp-kickoff ~/dc-tools/dc-decomp-kickoff
```

Then say one short line, "Tools ready: <version>" (the content of its `VERSION` file, or `git describe --tags --always`),
with no advice on how the user could avoid it: they cannot.

Then use that copy for every `scripts/...`, `template/...` and `references/...` path below. Do not
rewrite the tools from this text unless the clone is impossible: they encode fixes that are easy to
get wrong (multi-track discs, link address, regex blowups, linker quirks).

## Read this first: how complete this skill is

**Requirements: Docker and Python 3, on any OS (Mac, Windows, Linux).** Docker is the default:
Ghidra and the Hitachi tools run in containers, so nothing else is installed. Only if Docker is
impossible and the machine is **Linux x86_64**: `DC_LOCAL=1` (opt-in, never a default) runs the
Hitachi tools through `wibo` on PATH and Ghidra from `GHIDRA_INSTALL_DIR` (Ghidra 12.x + JDK 21).
`DC_LOCAL` does not work on macOS or Windows (`wibo` is a Linux program): there, install Docker.
**In a cloud workspace** (a Claude conversation's own Linux machine) images often cannot be pulled,
and there is no Docker: use `DC_LOCAL=1` for every script. Install what it needs with
`bash scripts/setup_tools.sh --check` (reports what is missing, installs nothing), then
`bash scripts/setup_tools.sh` (wibo, unshield, JDK 21, Ghidra: pinned and checksummed, one step per line),
then `source` the `env.sh` the script prints (`~/dc-tools/env.sh` by default) in every shell that runs a script. The user's disc and SDK are in a folder of
that machine (ask for the folder); the repo is built there, so offer to hand it back to them at the end.

**Before starting, check the machine:**
- `python3 --version` works and is 3.6 or newer (on macOS, `python3` can be Apple's stub that
  opens an install dialog: then use another Python, e.g. from python.org or Homebrew).
- `docker info` works (no Docker on Linux x86_64: `bash scripts/setup_tools.sh --check`, then install, as above). Docker Desktop and colima share **only your home folder** with containers
  by default: keep the work folder, the repo and the SDK under your home folder, or mounts arrive
  empty (a build that "can't find" files it plainly has is this).
- About 4 GB free (Docker images ~1.5 GB, the SDK, the disc copy for the game image).

**The user brings the SDK and the game image, each as a folder they pick.**
Ask for the game image's folder and, later (step 2), for the SDK's: a path to a directory on the machine
the work runs on, never a download or an upload. Never fetch an SDK yourself, and never offer to. Never
search, list or browse the user's folders to find either one: ask and wait.

**The SDK folder can have any layout** (`bin/ shc/ shinobi/` as the disc images lay it out, or a
tree with `.../Utl/Dev/Hitachi` and `Lib`): scripts find `asmsh.exe`, `lbr.exe`, `lnk.exe` and the
`.lib` files by name. Point `SDK_PATH` at the SDK's top folder (quote it when it has spaces).

**A second SDK, optional: 1.55J (1999), for more names.** List it
to the user by its disc names and ask them to provide the images themselves; never download it:
"Dreamcast SDK (Sega Library) Ver.1.55J" **Vol.1 (Common Disc)** and **Vol.2 (For SHC Users)**
(Redump discs 87866 and 87867; Vol.3, CodeWarrior, is not needed). Lay it out with
`python3 scripts/sdk_from_iso.py <out folder> <Vol.1 .iso> <Vol.2 .iso>`: it checks each image
against its Redump record, then copies `bin/` (Vol.1) and `shc/` + `shinobi/` (Vol.2), about a second.
Without it everything below still works, with fewer names.

**Run the Ghidra steps one at a time.** Each needs ~1 GB; Docker Desktop and colima often default to
2 GB, so two at once get killed ("Killed" in the log). `sdk_sigs.sh` switches to one library per run
when Docker has under 4 GB. **Every script fails loudly**: never continue past an empty table.
Ghidra projects are the costly part: `DC_GHIDRA_PROJECTS=<folder>` keeps them there instead of in
the output folder, so cleaning outputs never wipes them (ask the user where, if they have a place).

**Long steps print progress** (Ghidra analysis ~3 min, first build a few minutes, textures a
minute or two): tell the user what is running and roughly how long before starting each.

**Evidence:** what the skill did on each game it has been run on (numbers, what broke, what
changed) is in `references/evidence.md`; the steps below state rules, not games. Everything the
skill uses is in its own folder.

## Run it one step at a time

Never present the whole plan, the whole list of requirements or several questions in one message. Do one
step, say what it is and roughly how long it takes, run it, show its result, then go to the next. One
question per message, asked when its step comes: new decomp or upgrade, then the game image's folder, then
(only when a tool is missing) the install, step by step, then the SDK's folder once `sdk_scan.py` has named
the release, then each optional extra as its step reaches it. A missing tool is installed or reported at
the moment it is needed, one tool at a time, never as a list handed to the user.

Say what a step is and why it exists, in one line. When a step repeats an earlier one (the second Ghidra pass, a rebuild), say
that it is planned and what it adds. When it finishes, give the number it produced (coverage before and after, counts,
sizes), not just "done".

Never go from one long step straight into the next. When a step finishes (an install, the Ghidra analysis, a build), say
in a line what finished and how long it took, then what comes next and about how long that takes, and only then start it.
While a long step runs, run it detached with its own log, its input closed (`</dev/null`) and a time limit that fits it (a few times the step's usual duration, in
minutes: these steps are long), and give a line of state when the user asks: a message from the user interrupts a command that is still running, and then nothing
comes back. If a command comes back interrupted or rejected, say so plainly, and look at the log before saying why and
before running anything again.

Every question with a closed set of answers is a real multiple-choice question (the client's question tool,
`AskUserQuestion` in Claude Code), the recommended answer first: new or upgrade, which release
when several fit, each optional extra (provide it, or skip), continue or stop at a decision point. Ask for a folder by its path. A client with no question tool gets the options as a numbered
list and is asked for the number.

## Third-party sources

The procedure needs two kinds of material (a Katana SDK and the game's disc), both brought by the user as the folder that holds them; the rest is optional. The sources below are identified solely as
examples of where optional material has been seen, as search terms for the user: this skill never fetches an SDK. The authors of this skill have no affiliation with, and
make no representation regarding, those repositories, their contents, or their licensing. Nothing
is retrieved without the user's express confirmation. The user is solely responsible for
determining whether they are entitled to obtain and use any such material, and may substitute any
equivalent material lawfully in their possession.

| need | where it has been seen (search terms; the user brings SDKs) | used for |
|---|---|---|
| Katana SDK (libraries + Hitachi `asmsh`, `shc`, `lnk`, `lbr`, `elf2bin`) | any Katana SDK release, installed or as a disc image (the one this skill's tests build with: R10.1) | SDK signatures, the matching build |
| other Katana SDK releases, optional (disc images: 0.20 Pre 7 to R11b, 1.55J Vol.1 + Vol.2, Network 1.04; Katana 0.40 Release.4 for 1998 games; R1.42J and 2.00J come as InstallShield 3 installers, `is3_extract.py`; R2 and 0.20 Pre 7 carry GNU `ar` libraries this skill does not hash yet) | archive.org item `official-katana-sdks` (`OFFICIAL KATANA SDKs.zip`, one image per release); 1.55J is also catalogued by Redump (discs 87866, 87867); 0.40 and the Shinobi/Kamui library sources from sega-dreamcast-info.com's SDK archive page (https://www.sega-dreamcast-info.com/en/dreamcast-develppement-sdk-library-archive) | the release the game was built with (step 2), more SDK names |
| the Shinobi and Kamui library sources, optional | sega-dreamcast-info.com ("The source code of the Dreamcast Shinobi/Kamui development library") | exact C and names for the SDK part of every game: reference source for the C loop, their bundled `.LIB` files are one more signature table, and the Shinobi dump's `.LST` listings name statics (`sdk_masked.py --listings`) |
| the Sega NAOMI SDK, optional (for games built on the NAOMI library: arcade ports with `nl*` functions) | archive.org item `NaomiSDK` ("Sega Naomi SDK 001002": `archive/naomi/libwin.zip`, `libsgi.tgz`, `smpwin1-7.zip`, `doc.tgz`) | the `nl*` / `nla*` / `nlsnd*` library (math, matrices, textures, sprites, print): one more signature table (`sdk_sigs.sh`, with a Katana SDK's `lbr.exe`/`lnk.exe` beside the libraries), its sample programs (`t.map` + `t.mot`) as another, and the API pages as each function's contract |
| cheat codes, optional | gamehacking.org (per-game pages, public); the Dreamcast-Talk compiled CodeBreaker list (members' attachment, credits its code authors); the community's widescreen code lists | named variables (`scripts/cheat_leads.py`) |
| a later port, a prototype, other decomps, optional | the user's own copies (ports and prototypes), GitHub, hiddenpalace.org, tcrf.net, segaretro.org | step 2b |
| an older SDK, optional | archive.org item `dcsdk-9e` (SDK R9 Europe, Nov 1999, disc 1: SHC 5.1 Release 08) | a period compiler for games built in 1999-2000; so far it gave the same bytes as R10.1's (Release 11) |

Ask before fetching anything from them (never an SDK). Never commit the SDK, the game's files, or anything that carries their bytes or
text (assembly, hash tables, the text map) to the new repo: its `.gitignore` already excludes them. What only
describes them (addresses, offsets, sizes, names: `functions.txt`, `globals.txt`, `models.txt`, `model-map/`) is
committed: the repo shares as much as is safe.

## New decomp or upgrade (ask first)

Before anything else, ask the user one question: start a new decomp, or upgrade one this skill
started? Ask it as a real multiple-choice question (the client's question tool, `AskUserQuestion` in Claude Code) with two options, "New decomp" (recommended, first) and "Upgrade an existing decomp"; plain text only when
there is no such tool. For an upgrade, ask for the repo's folder, then follow `references/upgrade.md` (it asks for
the target version: the latest tag recommended, `main` offered as the dev version, never recommended) and skip the
procedure below.

## Procedure

0. **Name the conversation after the game.** As soon as IP.BIN gives the title (step 1), rename
   the session if your client lets you (e.g. "Dreamcast decomp kick-off: <title>"), so a user
   running several games can tell the conversations apart.
1. **Disc to executable.** Ask the user for the path of the folder that holds the game image (a `.gdi` with its track files: only `.gdi` is supported). Never ask them to attach or upload files, and never explain how to set up the client. (`scripts/gdi_read.py`). Check the
   boot file in IP.BIN; `0WINCEOS.BIN` means Windows CE: stop, this skill does not apply.
   **Check it is the game before splitting.** Look for the game's own text (menus, item or place
   names) in the executable. A big `.BIN` next to the boot file can be a bundled application
   instead (a web browser shipped for online registration: `http` strings, a perfect SDK match and
   none of the game's text). A boot file with none of the game's text may only be a core that
   loads the game's code at runtime from other files (relocatable modules): this skill handles one
   executable at a fixed address, so stop and say so (`references/evidence.md` has an example).
2. **Base and fingerprint**: `scripts/linkbase.py`, `scripts/banners.py`. Note the SDK version the game used.
   **Which SDK to ask for:** `python3 scripts/sdk_scan.py references/sdk-banners.tsv <1ST_READ.BIN>`
   (`references/sdk-releases.md` lists every release with the file names it has been seen under, as
   search terms for the user)
   ranks the publicly preserved Katana releases by how many of the game's library builds they
   contain. A full match: ask the user for the path of the folder where they keep that release, and only that. The
   library sources, a later port and a prototype are optional extras: ask each one later as its own question (step 2b).
   Say that not all games have a later port or a prototype, but where they do,
   providing them is encouraged, as they can be the strongest source of information available. Say that skipping the
   optional steps can result in a weaker kickoff output. None: say the game was built with a
   release not in the list, and to pick a close one; suggest the one or two the script names. If
   the user already has several SDKs, they can instead point at one folder holding all of them
   (images, zips or folders) and run `sdk_scan.py <that folder> <1ST_READ.BIN>`. Older releases
   ship inside InstallShield cabinets: `scripts/sdk_unpack.sh <image> <out>` lays any of them out
   as plain files (Docker, any OS) before `sdk_sigs.sh`. The 1998-1999 releases (R1.42J, 2.00J)
   are InstallShield 3 self-extractors instead: `python3 scripts/is3_extract.py <SETUP.EXE> <out>`
   (stdlib) unpacks every archive inside. Some discs also carry a samples zip with prebuilt
   sample programs and their link maps: those link the release's libraries, so hashing them
   (ELFs in `elf/`, `map_names.py` output in `names/`, then `ExportSigs.java` in folder mode as
   `sdk_sigs.sh` does) is a signature table too, with no installer to unpack.
2b. **Extra material: ask the user, one short form.** Open with: "These are optional; the
   kick-off works without them, but each one gives the decomp a stronger starting point." Then
   ask these as separate questions (a form where the client has one, a numbered list otherwise),
   each answered with a folder or file, a link, or "no". Most likely first:
   1. **Cheat codes for this game** (a saved code list in CodeBreaker/Xploder format, or a saved
      gamehacking.org page). Every code is an address with a meaning: named variables. Widescreen
      codes count too (the community's CodeBreaker/hex widescreen hacks, one or two codes per
      game): each is the game's projection or aspect value, a named global.
   2. **Other regions or revisions of the game.** Same code: names and addresses carry across.
   3. **Existing reverse-engineering notes or a partial decomp** (a repo, thread or wiki page).
      Reference names and pitfalls.
   4. **A later port** (Android `.apk`, iOS, PC, another console). The big one when it kept its
      symbol table: it can name a large share of the functions and globals.
   5. **A decomp of the same game on another console.** Structures, class names and logic;
      no bytes match.
   6. **A prototype, debug build or dev kit dump.** Pre-release discs sometimes carry the
      linker's `.ELF` or `.MAP`, or a build log inside a data file, with every name; a studio's
      dev kit dump can hold the project folder with its link maps, ELFs with debug info
      (`scripts/elf_debug_names.py`) and source. Whether one exists for the game:
      https://www.sega-dreamcast-info.com/en/releases-prototypes-sega-dreamcast-iso (about 300
      Dreamcast prototypes and the published dev kit dumps, with what each one holds) and Hidden
      Palace's Dreamcast list (https://hiddenpalace.org/Prototypes_by_system/Dreamcast). With no ELF or map, still diff
      its strings against the release: debug readouts and menus left in early builds carry their
      own labels (`printf("Act    = %d", ...)` names the field it prints).
   Record each answer in the game's evidence entry. Only 1, 4 and 6 feed a tool: 1 ->
   `scripts/cheat_leads.py` (globals candidates, step 7); 4 -> `references/port-symbols.md`,
   symbols check first; 6 -> a symbol scan before anything else, then the strings diff. 2, 3 and
   5 become references in the repo's docs, and names only when the source is itself a matching
   decomp (`ExportSigs.java`).
   Never go looking for any of it: use what the user gives (a path, or a link they provide, which you may read). Never fetch
   games, SDKs or any extra that contains IP (a later port, a prototype, other regions): the user supplies those as paths.
3. **Ghidra** (Docker; no Linux machine needed, the image builds on first use), with the
   executable in `<work>`:
   ```
   scripts/ghidra/dghidra.sh <work> /work proj -import /work/1ST_READ.BIN -overwrite \
     -loader BinaryLoader -loader-baseAddr <base> -processor SuperH4:LE:32:default \
     -scriptPath /scripts -preScript DcPre.java -postScript DcReport.java /work/report.txt
   ```
   Import at the base `linkbase.py` picked: at the wrong one Ghidra finds a fraction of the code.
   Never copy the `.java` scripts into `<work>`: Ghidra then finds two copies and fails to load them.
   **How much it finds:** compare the bytes inside functions with the executable's size. A game is
   often mostly data (models, tables), so a third can be normal; a whole region with `rts`
   instructions and no functions is code the analysis never reached. `scripts/seed_funcs.py`
   lists function starts in uncovered stretches; re-import with `-preScript SeedFuncs.java
   <seeds.txt>` after `DcPre.java` so the analysis follows them. Code reached only through switch
   tables (`braf` / `jmp @Rn` with a table of offsets) or runs of function pointers stays hidden
   to both: read those tables when a region still looks like unreached code.
4. **Names**:
   - SDK-wide: `scripts/sdk_sigs.sh <SDK folder> <out>` -> `<out>/katana-sdk.sigs`. Any SDK layout:
     the Hitachi tools and the `.lib` files are found by name. Build once per SDK and keep the table
     beside the SDK folders (not in a scratch dir): it is minutes to an hour of hashing to rebuild.
     Details and gotchas: `references/sdk-signatures.md`.
     With the 1.55J folder too, run it again into a second folder (`<out155>/katana-sdk.sigs`) and
     apply both tables.
   - **Apply every table you have, all in one Ghidra run**, then `DcReport.java`:
     all the SDK tables merged into one (`cat` them into one file), with `ApplySigs.java <sigs>
     <out> apply`: a hash that two releases name differently stays ambiguous, so twin stubs
     (byte-identical code under unrelated names) are never named by which release has which.
     Only unique matches are applied; the same tables always give the same names. A unique match
     on a tiny function (a few instructions) can still be a collision with unrelated library code:
     report short names that make no sense where they sit (a video-player function in a game that
     plays no video) as suspect, never silently trust them.
   - **Types from the SDK's headers**, once the names are in: `scripts/sdk_headers.py <SDK folder>
     <out>` copies the headers in a form Ghidra's C parser reads, then, in the same Ghidra run as
     `DcReport.java` or on its own, `ApplyHeaders.java <out>/shinobi/include
     <out>/shinobi/include/SHC <out>/shc/include <out>/stub -D__SHC__ -D_SH4`. It parses the
     release's headers into the program (R10.1: 2,372 prototypes, 423 structs such as
     `PDS_PERIPHERAL`, `NJS_OBJECT`, `KMVERTEX`), gives every named function that has a public
     prototype its real signature, and types the literal-pool words SH-4 calls through, so the
     decompiler shows `PDS_PERIPHERAL *` where it showed `undefined4`. Only the public API gets
     a prototype (one named function in five: the rest are library internals); use the headers
     of the release `sdk_scan.py` picked.
5. **The repo: ask the user where to put it.** Suggest a default (a sibling of the current folder,
   named from the IP.BIN title: lowercase, spaces to hyphens, plus `-decomp`, e.g.
   `SOME GAME` -> `<parent>/some-game-decomp`), always written as an **absolute path**. Create it,
   then confirm the resolved absolute path back to the user in one line. From here on, every path
   you show (commands, summaries, the final report) is absolute: never `cd <name>` alone.
   **Split**: `scripts/split_asm.py <1ST_READ.BIN> <base> <report> <repo>`: one `.src` per function,
   data words, exported labels, `objects.txt` in link order.
6. **Make the repo publishable and build it.** A pushed repo holds no game bytes, so it must be
   able to regenerate them from each user's own disc. Into the repo:
   - copy `template/` (`build.sh`, `setup.sh`, `disc.sh`, `textures.sh`, `models.txt`, `README.md`, `AGENTS.md`, `KICKOFF`),
     and `template/gitignore` as **`.gitignore`** (shipped without the dot: some installs drop
     dotfiles);
   - copy into `tools/`: `scripts/gdi_read.py`, `split_asm.py`, `text_map.py`, `text_dump.py`,
     `textures.py`, `model_map.py`, `find_extras.py`, `disc_patch.py`, `apply_bin.py`, `docker_check.sh`, `units.py`, `fill.py`,
     `progress.py`, `missed_funcs.py`, `shdis.py`, `live.py`, `sh4sim.py`, `equiv.py`, `checksizes.py`, `classify.py`, `poollist.py`, `port_equiv.py` with `sdk_masked.py` (which it imports), `sdk_source.py`, the `tools-image/` folder and `scripts/hooks/` as `tools/hooks/` (so a cloned repo builds its own
     tools image, nothing pulled from anyone else);
   - write `sdk.txt`: `scripts/sdk_txt.py <repo>/functions.txt <base> <1ST_READ.BIN>
     <SDK ApplySigs output>`. It marks the boot block
     and the SDK library block;
   - write the base to `BASE` (hex, no `0x`); `split_asm.py` already wrote `functions.txt`;
   - fill the placeholders: in `setup.sh` and `disc.sh` `@BOOT@` (boot file from IP.BIN) and `@SHA1@` (of that
     file); in `README.md` `@TITLE@`, `@RELEASE@` (IP.BIN: title, product number, version, date,
     region), `@BOOT@`, `@SIZE@`, `@SHA1@`, `@BASE@`, `@SDK@` (main banners), `@FUNCS@`, `@NAMED@`,
     `@NAMED_SDK@`, `@SKILL_VERSION@` (the skill version the repo came from: `v0.5` for a tagged release,
     `v0.5+1a2b3c4` for a dev version, the commit `1a2b3c4` after tag `v0.5`; in a git checkout it is
     `git describe --tags --exact-match` if that succeeds, otherwise the last tag + `+` + the short commit;
     without git, the content of this skill's `VERSION` file (the last release); also in
     `KICKOFF`, the version an upgrade starts from: `references/upgrade.md`), and `@PROGRESS@` (after the first `MATCH`: the
     output of `python3 tools/progress.py` in a ``` fence). No `@...@` may remain in those files
     (`grep -n '@[A-Z_]*@' README.md setup.sh disc.sh KICKOFF`; `tools/` has its own `@N@` tokens, ignore).
     `@NAMED@` = functions whose name is not `FUN_...` (what `split_asm.py` prints). It can exceed
     `@NAMED_SDK@`: small wrappers (thunks) inherit the name of what they call.
   - **no licence**: the repo gets no `LICENSE` file and no licence section. Its contents derive
     from the game's own code, whose rights are the publisher's: claiming ownership or granting
     others rights would overreach, and default copyright says nothing more than it should.
   - `chmod +x build.sh setup.sh tools/hooks/pre-commit` (tell the user; it is one command).
   - the pre-commit hook (`tools/hooks/pre-commit`, from `scripts/hooks/`) does two things on every commit: it keeps the README's
     Progress block current, and it refuses the commit unless `build.sh` prints `MATCH` and every staged `src/*.c` has no DIFFERS in
     `tools/equiv.py` (about 10 s; `SKIP_BUILD_CHECK=1` skips it). Enable it with `git config core.hooksPath tools/hooks`. Commit in
     batches, not change by change: the check runs every time.
   - write `.env` in the repo with `SDK_PATH="<absolute SDK folder>"` (gitignored, machine-local),
     so the user can rebuild with a plain `bash build.sh` later.
   Then put the original executable in as `1ST_READ.BIN` and run `bash build.sh`. It must print `MATCH`. First run assembles every file (minutes); later runs only
   changed ones. Always invoke scripts with `bash`/`python3`: downloads can lose execute bits.
   Finally prove the published layout works: empty `asm/`, `objects.txt`, `text-map/`, then
   `bash setup.sh <disc.gdi>` and `bash build.sh` again: `MATCH` again.
   Then the masked SDK pass, with every table folder from step 4 (and, with the Shinobi or
   Kamui source dump, `--listings <dump folder>`): `python3 scripts/sdk_masked.py <repo>
   <repo>/1ST_READ.BIN <table folder>... [--listings <folder>] --apply`, then `split_asm.py`
   and `bash build.sh` (`MATCH`). It names library code the hashes missed (internal library
   builds, twin stubs, statics, starts the split missed; `references/sdk-signatures.md`).
   With library sources from the user (step 2): `python3 tools/sdk_source.py <source folder>...` in the repo. It
   compiles them with the SDK's own shc and keeps every function whose bytes they reproduce: the exact C goes to
   `sdk-source/` (git-ignored), the names to `sdk-verified.txt`, and `progress.py` counts them in. Tell the user
   what it wrote, and that `sdk-source/` is the SDK's own code: adding it to the repo is their choice.
   Report its `suspect` lines as such. Count `@NAMED@` and `@NAMED_SDK@` after it.
   Then `python3 tools/missed_funcs.py 1ST_READ.BIN <base> functions.txt`: code the analysis did
   not make into functions (callbacks reached only through tables, getters only through literal
   pools, state handlers merged into a neighbour, whole functions in a big gap when something
   points at an entry). Expect hundreds, about half backed by a pointer. They matter for C units, whose ends must be function boundaries. Report the count
   and leave the list for review: adding an entry never changes the bytes (still `MATCH`), only
   where files split. If a sibling decomp exists (same team: games that link the same in-house
   library, an engine or maths layer no SDK table knows), `python3 scripts/sibling_names.py
   <sibling repo> <repo>` proposes its names for exact masked matches that are unique both ways
   and lists the twins; `--apply`, then `split_asm.py` and `bash build.sh` (`MATCH`).
   `python3 tools/progress.py` gives the starting state.
7. **Asset maps**: all of them, with no question to answer. **Text map** (for translators, English included: any language can be a source as well as a
   target): `scripts/text_map.py <1ST_READ.BIN> <base> <repo>/text-map <disc.gdi> [tier]`.
   - `exe_strings.tsv`: every executable string: address, offset, encoding, length and text.
   - `files.tsv`: text density per disc file.
   - **Text files:** the skill detects nothing here. A decomp lists its text files in `models.txt` (`text <disc path>`, one per line, the path as in `files.tsv`) and `setup.sh` runs `scripts/text_dump.py`, which copies exactly those files, as they are, into `text-dump/` (git-ignored: it holds the game's text). Shuriken's Text tab shows that folder, a page of lines at a time.
   - `images.tsv`: every disc file that holds images (PVR textures found in it, or an image file extension). It
     makes no guess about text in images: that is for a person to see, on the contact sheet below.
   - **Cheat codes** (when step 2b got a list): `scripts/cheat_leads.py <list.txt> <title>
     <1ST_READ.BIN> <base>` prints one line per code: address, size, write or compare, the
     cheat's name. Those are globals candidates with their meaning (health, timer, cash...). Most
     are RAM variables beyond the executable. A list for another region of the game names the
     same variables at other addresses, and not by one constant shift (one build moved its game
     state block by 0x22E0 and its option flags by 0x2358): find each by its use in the code
     before applying it. `cheat_leads.py fetch <title>` takes the list from libretro-database.
   - Textures are their **own step** (`bash textures.sh <disc.gdi>`, seconds to a minute): every
     standard (PVR) texture decoded to PNG on one page with checkboxes (`text-map/textures/`), for a
     person to look through. A game that keeps its art in its own formats gets 0 here and a
     note saying so; its textures are then in the model map's `[textures]` section, if it has one.
   - **Model map** (`scripts/model_map.py <1ST_READ.BIN> <base> <report> <disc.gdi> <repo>/model-map
     [<repo>/models.txt]`): every NAOMI-library model in the disc files (records that parse exactly), the
     address each file is loaded at (found by matching the executable's pointers to the models' starts, no
     profile needed), every pointer to a model followed back to its table, and the table named by a rule in
     `models.txt` (curated: characters, cars, a skeleton, a texture list), a data symbol, or the functions
     that use it. One file, `model-map/game.dcgs`: sections `[models]`, `[assemblies]`, `[rigs]`, `[bones]`, `[motions]`, `[images]`, `[audio]`, `[textures]`, tab-separated; its first line `# dcgs <version>` is the skill version (`KICKOFF`).
     **It is committed, unlike `text-map/`**: only the game's text and bytes are kept out of git, and this file holds
     addresses, offsets, sizes, our names and one standing pose's matrices, no bytes and no text.
     `models.txt` starts as only its syntax comments; fill it from the notes as tables are understood. A game
     whose models are in another format lists none here, and the step says so. Texture lists matter: the
     texture's real size, type and format come from the game's own list, not the model records.
   - **Audio** (the `[audio]` section of the same file): every CRI ADX / AHX stream the disc holds, inside AFS archives or
     on its own, found by its header, with channels, sample rate, samples and seconds; a DTPK sound pack inside an AFS archive is
     opened and gives one row per sample (index = entry * 10000 + sample; the rate is nominal, the pack records none),
     a loose DTPK sound bank is listed as a bank. An AFS archive counts only when at least one entry is audio (a city or model archive is skipped). The
     archives carry no entry names, so a sound is `FILE:index`, named by a `sound <file> <entry> <name>` rule in `models.txt`.
   - `setup.sh` rebuilds the text map from `functions.txt`, so a cloned repo's `files.tsv` lists
     function-level users only; the kick-off's own run (from the full Ghidra report) has more.
   - Tiers: `quick` = executable only (seconds); `standard` = plus a 2 MiB sample of every disc file
     (seconds to a minute); `deep` = whole files (minutes on a full disc).
   - Density and the Shift-JIS count are counts, not a verdict: binary data scores as text sometimes.
   - **OCR is not included, on purpose.** Finding baked text in single-language games would mean
     decoding every texture (PVR, often thousands per disc) and running OCR on each: tens of
     minutes to hours, plus an OCR engine and its Japanese data, and game fonts are stylised, so it
     misses text and flags noise. If a user wants it, warn them of that cost first. A contact sheet
     of all textures, looked at by a person, is the method this skill provides.
8. **Game build**: `bash disc.sh <original .gdi>` writes `build/disc/`: a copy of the user's disc
   with the rebuilt executable and every file under `disc/` (same path as on the disc) written in
   place, error correction recomputed, read back to verify. A smaller file is padded; a **bigger**
   one moves into free sectors (GD-ROMs often carry a whole filler track) and its directory entry is
   repointed. To change the executable from a modified copy, `tools/apply_bin.py <repo> <original>
   <modified>` writes the changes into the asm data words; then `bash build.sh` (it prints DIFFERS,
   expected; `DC_EXPECT_CHANGES=1` makes that exit 0).
9. **Hand over**: `template/AGENTS.md` is the loop (names first, then C one source file at a time).
   If the game was later ported and the user has the port (an Android `.apk`, an iOS or PC build),
   offer `references/port-symbols.md`: a port that kept its symbol table names a large share of
   the game's functions and globals by their original names.
   **Print the run as an evidence entry** (the format at the top of `references/evidence.md`:
   game, SDK by banners, counts, MATCH, text-map highlights, and what broke or surprised), and
   tell the user they can send it to the skill's repo as an issue so the next version learns from
   their game. Never write into the skill's own folder.
10. **GitHub (optional)**: print, do not run, the commands for the user:

   ```
   cd "<absolute repo path>" && git init && git config core.hooksPath tools/hooks && git add -A && git commit -m "Kick off: byte-matching split, <n> named"
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
| `scripts/ghidra/*.java` | seed + report (`DcPre`, `DcReport`), signatures (`ExportSigs`, `ApplySigs`), prototypes and structs from the SDK's headers (`ApplyHeaders`), queries (`Query`: decompiles with FPSCR's PR and SZ at 0 on entry, so float code reads as single precision instead of two branches per instruction) |
| `scripts/sdk_headers.py` | an SDK's C headers copied in a form Ghidra's C parser reads (form feeds, Shift-JIS comments, `(Void)` parameter lists, empty attribute macros) |
| `references/sdk-signatures.md` | naming library code from the SDK's libraries |
| `references/evidence.md` | each game the skill was run on: numbers, what broke, what changed |
| `references/memory-map.md` | Dreamcast addresses worth labelling on sight |
| `references/upgrade.md` | bringing a repo this skill started to a newer skill version: versions, `KICKOFF`, the steps |
| `references/matching-c.md` | getting a source file to match: units, flags, fill, idioms, compare loop |
| `references/port-symbols.md` | naming from a later port that kept its symbols (Android, iOS, PC builds) |
| `scripts/sdk_sigs.sh` | signature table for every exported function in an SDK's libraries |
| `scripts/sdk_from_iso.py` | SDK 1.55J folder from its Vol.1 + Vol.2 disc images, checked against Redump |
| `scripts/sdk_scan.py` | which SDK release built the game: its library banners against `references/sdk-banners.tsv` or a folder of SDKs |
| `scripts/is3_extract.py` | InstallShield 3 installers (SETUP.EXE / .Z) as plain files: directory + PKWARE implode, stdlib |
| `scripts/sdk_unpack.sh` | any SDK image or zip as plain files, InstallShield cabinets unpacked (`unshield-image/`) |
| `scripts/iso_extract.py` | copy every file out of a disc image or zip (Joliet or ISO9660, no mounting) |
| `references/sdk-banners.tsv` | library banners (module, version, build date) of every preserved Katana release |
| `references/sdk-releases.md` | every Katana release: date, the file names it circulates under (search terms), what it gave; prototypes and dev kit dumps as material |
| `scripts/text_map.py` | the executable's strings, text per disc file, the list of images |
| `scripts/text_dump.py` | copies the disc files `models.txt` lists as `text <path>` into `text-dump/` |
| `scripts/textures.py` | every standard texture to PNG + a contact sheet (`index.html`) |
| `scripts/disc_patch.py` | copy a GDI with files replaced in place, error correction recomputed |
| `template/disc.sh` | in the repo: build a playable disc image of the user's version |
| `template/textures.sh` | in the repo: the texture contact sheet, as its own step |
| `scripts/apply_bin.py` | write a modified executable's changes into the repo's asm data words |
| `scripts/docker_check.sh` | Docker installed vs running vs low memory, and the tools image on first use |
| `scripts/tools-image/Dockerfile` | the `dc-tools` image: small Linux + pinned, checksum-verified wibo |
| `scripts/split_asm.py` | split an executable into per-function asmsh sources + link order |
| `template/build.sh` | assemble, compile C units, link (`start P(<base>)`), `elf2bin`, compare with the original |
| `scripts/units.py` | in the repo: the link order with C units in place of the asm files they replace |
| `scripts/fill.py` | in the repo: lay a C unit out like the original (nop alignment, 0xEE fill, exact size) |
| `scripts/progress.py` | in the repo: done (equivalent C), matching C, named functions and globals, documented. "done: equivalent C" stays the first row of the first section: Pluto finds the main metric by that label |
| `scripts/sdk_txt.py` | mark the SDK's code (boot block, library block, single matches) as `sdk.txt` |
| `scripts/sdk_masked.py` | after the tables: name more SDK functions by masked instructions, library layout and source listings (statics), link order as the check (stdlib) |
| `scripts/missed_funcs.py` | list code the analysis did not make into functions |
| `scripts/sh4sim.py` | in the repo: an SH-4 interpreter (integer, single-precision FPU, delay slots) that runs one function from a case (registers, memory, a RAM dump, mocked call returns) and records its calls, writes and result (stdlib) |
| `scripts/find_extras.py` | in the repo: the `extra` rules of a character draw function, found by running its branches per character (draws behind state the run cannot know are listed as gated, not as rules) |
| `scripts/equiv.py` | in the repo: compiles a C file and checks each function against the original on its test cases (`tests/<file>/<function>.json`); the Equivalent tier, written to `tests/equivalent.txt` |
| `scripts/sdk_source.py` | in the repo: compiles the library sources the user supplied with the SDK's shc; the functions whose bytes they reproduce go to `sdk-source/` (exact C, git-ignored) and `sdk-verified.txt` (names, counted by `progress.py`) |
| `scripts/port_equiv.py` | in the repo: carries Equivalent C for shared library code from a sibling decomp into this one (masked-code match, pool-word mapping, ported cases), every function re-checked by this repo's `equiv.py` |
| `scripts/checksizes.py` | in the repo: functions whose size in `functions.txt` looks wrong (a literal pool mid-body ended the listing early), with the size that covers the code after it |
| `scripts/classify.py` | in the repo: which functions can have C at all (FPU banks, `fsrra`, control registers other than SR: blocked) |
| `scripts/poollist.py` | in the repo: a function's literal pool as functions, RAM addresses (named, or MISSING) and numbers |
| `references/equivalent-pipeline.md` | writing Equivalent C at scale: the three checks, what the check compares, the lock for parallel workers, the worker brief |
| `scripts/sibling_names.py` | names from a sibling decomp (same team, shared library): exact masked matches unique both ways, twins listed |
| `scripts/cheat_leads.py` | cheat codes (CodeBreaker/Xploder list) as named-variable leads |
| `scripts/seed_funcs.py` | function starts in stretches no function covers, seeds for `ghidra/SeedFuncs.java` |
| `scripts/shdis.py` | in the repo: SH-4 disassembly with FPU, pool values and names (stdlib) |
| `scripts/live.py` | in the repo, optional: read, watch and write the running game by address or name, screenshots, pad input (RetroArch + Flycast core over its network ports, stdlib) |
| `scripts/gdbsnap.py` | in the repo, optional: RAM snapshots of the running game over Flycast's GDB server (a build with `ENABLE_GDB_SERVER`), timelines, and what changed between two snapshots with the nearest global names; stage 5 of `references/roadmap.md` (stdlib) |
| `scripts/map_names.py` | code symbols of a linked library's map, runtime routines included |
| `scripts/elf_debug_names.py` | function names and addresses from an SHC ELF's DWARF 1 debug section (prototype or dev kit ELFs) |
| `scripts/ghidra/ExportFeatures.java` | per-function strings, constants, calls and globals, for port matching |
| `scripts/port/*.py` | pair functions and globals with a port's symbols (`references/port-symbols.md`) |
| `template/setup.sh` | in the repo: extract + verify the user's executable, regenerate `asm/` and `text-map/` |
| `template/README.md` | the repo's README, with `@PLACEHOLDERS@` to fill |
| `template/AGENTS.md` | the decompilation loop for whoever works in the repo |
| `template/gitignore` | the repo's `.gitignore`: keeps game and SDK material out of git (asm, executable, disc, build, text map) |
