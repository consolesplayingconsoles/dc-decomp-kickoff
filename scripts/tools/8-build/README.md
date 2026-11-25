# Step 8: build from C

| tool | what it does |
|---|---|
| [cbuild.py](cbuild.py) | A build of the game from the proven C: the game code region is the compiled C, everything else is the original. |
| [disc.py](disc.py) | `make disc`: the game built the way status.txt's MODE says (equivalent: `make c`; matching: `build.sh` and the overlays), in a copy of the disc. |
| [disc_patch.py](disc_patch.py) | Build a playable disc image: a copy of the original GDI with some files replaced. |
| [relocasm.py](relocasm.py) | Assembly pieces that can move: real instructions, labels for branches, symbols for the functions they call. |
| [relocptr.py](relocptr.py) | Pointers to game functions, in the pieces that stay where they are, follow the functions. |
| [codeconsts.py](codeconsts.py) | C that reads a constant from the original's code by its address (a literal pool the build overwrites): lists them, `--write` puts the values in. |
| [retcheck.py](retcheck.py) | Each function's result register, from the original's code before its `rts`, against its C declaration; `make c` and the pre-commit hook run it. |

## Prompts

Work to hand to another agent, with its placeholders filled in; each carries the rules it needs.

A prompt may use another prompt one level deep, by naming it; a prompt that another one uses is a leaf (it names none) and has a
fixed effort limit, so no chain of prompts can recurse or run without end.

| prompt | what it hands over |
|---|---|
| [PROMPT_triage.md](PROMPT_triage.md) | A build from C that stopped: its own message read, the cause found, the step that fixes it named; nothing changed. |
