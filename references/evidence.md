# Evidence: games the skill has been run on

One entry per game. The rest of the skill states rules without naming games; what each game showed,
and what changed in the skill because of it, lives here. A lesson that comes back on several games
belongs in the rules; one that stays with a single game is that game's quirk.

The skill's last step prints a run in this format: paste it here (or send it to the skill's repo
as an issue) to add a game.

## Entry format

```
### <Title> (<region>), <product number> <version>
- run: <date>, skill <version or commit>, on <OS / cloud workspace>
- executable: <size> bytes, linked at <base>; SDK by banners: <release, n/m library builds>; SDKs used: <...>
- functions: <n>; named: <n> (<n> SDK signatures, <n> reference decomp); build: MATCH (also after setup.sh)
- text map: <strings, with pointers>; file tables: <files with a table in the executable>; textures: <n decoded>
- missed functions: <n candidates>
- C units: <matched units, functions>
- what broke or surprised -> what changed in the skill
```

### Crazy Taxi (Europe)
- run: 2026-10-05 (v0.4) and later sessions, on macOS (Docker)
- executable: linked at 0x0C010000 (most Katana games use 0x8C010000: imported at the wrong base,
  Ghidra found 1,113 functions instead of 2,389); SDK by banners: R9 closest (19 of 29 known
  modules, against 11 for R10.1); SDKs used: R10.1 (Kochise, and a second copy laid out like the
  reference decomp's: same results), later R9
- functions: 2,389; named: 429 at kick-off (385 SDK R10.1, 30 reference decomp, the rest
  wrappers); an R9 table named 112 more SDK functions (SDK coverage 42% to 53%); build: MATCH
- port: Crazy Taxi Classic 6.0 for Android (`libgl2jni.so`, arm64) kept its symbols: 310 functions
  and 29 globals paired, 257 new names (functions named 20% to 31%)
- text map: 2,513 strings, 1,144 with every pointer found; 16 image files flagged (5 languages);
  textures: 1 standard texture on the disc (the art is in the game's own formats)
- missed functions: 644 candidates, about half backed by a pointer
- C units: a Naomi-library file (3 functions) and the heap/event list (9 of 12) matching; SHC 5.1
  Release 04 (R1.42J), 08 (R9) and 11 (R10.1) compiled identically on everything compared
- what broke or surprised -> what changed:
  - wrong import base -> `linkbase.py`
  - a unit swallowed a 16-byte leaf the split did not have, build 16 bytes short -> `units.py`
    refuses units whose ends are not file boundaries; `missed_funcs.py`
  - library code (`nl*`) padded with nops to 16/32 bytes -> `-align16` in the unit header
  - register allocation decided by how C is written -> the idioms tables in `matching-c.md`
  - constant data had nowhere to go -> `@data` and `D` lines
  - functions reached only through a function-pointer table were merged into a neighbour ->
    `missed_funcs.py` flags pointers into a body
  - two signature names on game code were wrong (a state entry, an angle helper) and spread as
    port seeds -> `validate.py` lists short signature names with no family nearby
  - port work: PLT stubs hid callers (`Query.java callers`), relocations pair whole pointer tables,
    32-bit Dreamcast constants line up structs (+4 per widened pointer) -> `port-symbols.md`
  - SHC runtime routines (`__modls`, `__bfslu`, `__quick_*_mvn`) never named: typed as data in the
    library map -> `map_names.py`
  - code placed in the boot block's filler gave a black screen once gameplay started -> the
    "Changing the game" note in the template

### Boku Doraemon (Japan), T-41802M V1.003
- run: 2026-10-05 (v0.4) and 2026-10-06 (v0.5, on macOS and in a claude.ai cloud workspace: same
  names)
- executable: 978,148 bytes, linked at 0x8C010000; SDK by banners: no release has all 48 library
  builds (newest Shinobi 1.75, Oct 2000), closest R11b (26/48) then R10.1 (23/48); SDKs used:
  R10.1, R11b, 1.55J
- functions: 3,034; named: 1,044 (976 from the SDK tables merged, 13 from the complete Tokyo Bus
  Guide decomp; v0.4 had 975 with R10.1 and the 176-name reference); build: MATCH, also after
  setup.sh
- text map: 2,155 strings (80 Shift-JIS, 1,962 with pointers); file tables: STORY.PAC (76 scenes,
  sector and length at 0x8C04B704), KAOGRA.PAC, STORYGRA.PAC; textures: 887 decoded, 222 not
- missed functions: 860 candidates, plus 9 merged functions reached through tables
- C units: none yet
- proof beyond the build: rewriting STORY.PAC's table let the story script grow past its slot
  (moved into the filler track, 10 KB bigger, a scene at 1.7x its budget); played through in
  Flycast and on GDEMU. The game's Catalan translation went from about 40% to 99% this way.
- what broke or surprised -> what changed:
  - the scene table was found by `file_tables.py`; tested blind on 6 other games: no false hits
    and no hits, so a missing row proves nothing
  - per-release SDK tables named twin stubs (byte-identical code under unrelated names) by which
    release has which -> SDK tables are merged into one before applying
  - the cloud workspace dropped dotfiles and execute bits from the uploaded skill, and could not
    pull Docker images -> `template/gitignore` without the dot, `DC_LOCAL` for every script

### Virtua Fighter 3tb (US), MK-51001 V1.002
- run: 2026-10-07, naming only (for another team's decomp; no repo kicked off), on macOS (Docker)
- executable: 1,179,648 bytes, linked at 0x0C010000 (16,517 pointers; 11 at 0x8C010000); SDK by
  banners: none of the game's 6 library builds (Jan 1999, GDFS 0.53 of Aug 1998) is in any
  preserved release: it sits between Katana 0.40 and 1.0B2; SDKs used: 0.40 Release.4, 1.55J, R9,
  R10.1, R11b
- functions: 1,906 at first (27% of the executable), 2,306 after seeding (32%); the other team's
  own baseline is 2,398 (37%): most of the executable is data
- named (after seeding): 126 (97 SDK, of which 0.40 added 44; 22 from the Crazy Taxi decomp's
  NAOMI library names; 3 from TBG; 4 wrappers); before seeding, 97 of 116 signature names did not
  appear anywhere in that team's repo
- what broke or surprised -> what changed:
  - 1998 libraries use another banner form -> `banners.py` / `sdk_scan.py` read both; 0.40 added
  - a sister decomp (same developer's library) named what no SDK could -> "From another decomp's
    names" in `sdk-signatures.md`
  - the other team's best SDK matches came from an SDK sample program's ELF of the exact library
    version -> "sample programs" note
  - analysis reached a quarter of the executable -> `seed_funcs.py` + `SeedFuncs.java`, coverage
    note in step 3
  - tiny collisions (a video-player function name in a fighting game) -> suspect-name note in step 4
  - PC (Sega ALLS, 2023) version: a modern host engine around the arcade original, no symbols

### Phantasy Star Online Ver. 2 (US), MK-51193 V1.004
- run: 2026-10-07, stopped at step 1
- the boot file (157 KB, Shinobi 1.757) has none of the game's text: a core that loads the game's
  code at runtime (the disc holds 129 `.BIN` and 516 `.REL` files); the big `2_DP.BIN` (2.8 MB,
  SDK R9 exact) is the bundled Dream Passport 2 browser, kicked off by mistake before checking its
  text (kept as its own local repo)
- ports checked for names: PC (no symbols, no `.pdb`), GameCube Episode I & II (no map; its extra
  `.dol`s are a web browser and its debug build), the GameCube decomp (9 game files, C++ classes
  whose names do not appear in the Dreamcast build): none carries names over automatically
- what changed: step 1 "check it is the game", runtime-loaded code named as a limit; "check for
  symbols first" in `port-symbols.md`

