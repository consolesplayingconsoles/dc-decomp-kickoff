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
