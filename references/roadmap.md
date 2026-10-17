# Roadmap: from kickoff to the long tail

What to do at each stage of a decomp, which tool does it, and when the stage has run dry. Read it before
choosing the next round of work. The numbers are from Crazy Taxi and Virtua Tennis (2026-10-17); a new game
will differ, but the order holds. The evidence behind each stage is in `evidence.md`.

| Stage | Equivalent C | Tools | Done when |
|---|---|---|---|
| 1. Kickoff | 0 to 10% | the kickoff itself: banners, SDK tables, names, `build.sh` MATCH | the library is named and the build matches |
| 2. Library C | 10 to 35% | hand-written C for SDK functions, `sdk_source.py`, `equiv.py` | the small library functions are done |
| 3. Sibling ports | +5 to +15% | `port_equiv.py` from a decomp on the same SDK | a second port finds nothing new |
| 4. Generated C | +10 to +20% | `scripts/gen_equiv` on straight-line functions | a rerun passes only a handful |
| 5. Live data | the long tail | `gdbsnap.py` with a GDB build of Flycast, RAM dumps as `equiv.py` cases | not reached yet |

## Stages 1 to 4: static

- Run them in order. Each one feeds the next: names from stage 1 let stage 2 link, stage 2's library C is
  what stage 3 ports, and stage 4 needs every callee named.
- Port one way only. Once the shared library has gone from the richer decomp to the other, porting back
  finds little and its renames can break the destination's callers (see `evidence.md`). Run `build.sh` and
  the full `equiv.py` sweep after every port.
- Stage 4 stops on structure, not on instructions: loops (backward branches), forward `bra` over an else
  block, address-of-local, stack arguments. Adding instructions to the generator buys little; adding a
  structure (loops first) is the next lever.

## Stage 5: live data

Static reading runs dry where a function depends on run-time state: what a loop sees, which branch a
dispatcher takes, how a struct fills in. RAM is dynamic, so one dump is a single frozen moment; a
timeline of snapshots shows which bytes change together.

1. The user starts a Flycast built with the GDB server (release builds have none; see `gdbsnap.py`),
   with `-config config:Debug.GDBEnabled=yes`. The agent never starts or drives the emulator.
2. `gdbsnap.py timeline REGIONS --every S --count N` while the user plays the scene in question; label
   each run after the scene.
3. `gdbsnap.py diff A.json B.json` in the decomp repo: the changed words, each with the nearest global.
   Words that change together are a struct; a word that steps by one is a counter.
4. A snapshot is also an `equiv.py` case: a `"dump"` case runs the original and the C from that RAM.

Each snapshot pauses the game for the read (about 580 KB/s, so a 1.5 MB region takes under 3 s); keep the
regions to what the question needs. The port listens on every interface while that Flycast runs.

## What the agent asks the user for

Only stage 5 needs the user: to start the GDB build and to play the scene. Ask for the scene, not for a
dump: the agent takes the snapshots itself.
