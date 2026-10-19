# Step 6: Experience-driven agentic decomp

What the agent works on once the script-generated decomp has run dry, and what it needs from the user. The agent works from the repo's `AGENTS.md`;
this is the detail. The tools for writing and checking the C are in `equivalent-pipeline.md`; the evidence behind the numbers is in `evidence.md`.

## The pockets
What is left after the script-generated decomp (step 5) is a handful of pockets; split them by what blocks each and use the tool that fits:

| Pocket | What it is | How to take it |
|---|---|---|
| Library | SDK functions with no C yet | the SDK's own source where you have it (`sdk_source.py`: byte-identical = verified); hand C and the generator elsewhere |
| Game code | the game's own functions | generator, then hand-written C with cases; decomp names first |
| Compiler runtime, libm, tables | runtime routines and data counted as functions | name and size them correctly; a data table listed as a function is a `D` line, not work |

Every pocket ends with the same bar: the cases run the original's instructions (see `equivalent-pipeline.md`, instruction coverage and the two tiers).

## Live data

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

Only live data needs the user: to start the GDB build and to play the scene. Ask for the scene, not for a
dump: the agent takes the snapshots itself.
