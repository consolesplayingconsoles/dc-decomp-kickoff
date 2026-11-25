# Step 6: agentic decomp

| tool | what it does |
|---|---|
| [codeaddr.py](codeaddr.py) | Addresses of the game's own functions written as numbers in the C become the functions' names. |
| [gdbsnap.py](gdbsnap.py) | RAM snapshots of the running game over Flycast's GDB server, timelines, and what changed between two snapshots: the real state frametest.py runs on. |
| [frametest.py](frametest.py) | The C against the original on a real RAM snapshot of the game (the display lists, memory, results): finds a missing stack word or a wrong argument the cases cannot. |
| [live.py](live.py) | Check names against the running game (optional): RetroArch with the Flycast core, driven over its network ports, nothing typed into the emulator's window. |
| [handcase.py](handcase.py) | Prove a function on cases written by hand, with the C the generator writes. |
| [fuzzcases.py](fuzzcases.py) | Grow a function's cases by coverage-guided mutation of the original's inputs (the original runs only). |
| [poolconst.py](poolconst.py) | Turn the C's reads of the original code's literal pools into constants. |
| [poollist.py](poollist.py) | What a function's literal pool holds, and which of it still has no name. |
| [unpoke_code.py](unpoke_code.py) | Take the code out of what a test case may change. |

## Prompts

Work to hand to another agent, with its placeholders filled in; each carries the rules it needs.

A prompt may use another prompt one level deep, by naming it; a prompt that another one uses is a leaf (it names none) and has a
fixed effort limit, so no chain of prompts can recurse or run without end.

| prompt | what it hands over |
|---|---|
| `parts.py` | An outlier function in parts: `map` cuts it along its dominator tree, `read` has the generator read each part in a scratch copy (state/parts/). |
| [PROMPT_parts.md](PROMPT_parts.md) | Write and prove an outlier function in parts: map, read, join by hand, prove. |
| [PROMPT_prove.md](PROMPT_prove.md) | Prove one function: read the original, check the C, raise its coverage with the tools above, explain a DIFFERS. |
