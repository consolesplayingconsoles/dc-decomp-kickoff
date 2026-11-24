# Step 7: code size reduction

| tool | what it does |
|---|---|
| [hoist.py](hoist.py) | Hold a value the C recomputes again and again in a local, as the original held it in a register. |
| [shrink.py](shrink.py) | Write proven functions again with the current generator and keep the new C only when it is smaller and still proven; `--passes` rewrites the current C instead (over-wide callee declarations, self-copies, struct access, frame slots as locals, shared global bases, if-chains as switches, result copies merged, repeated builtins computed once, the stack array rebased, dead stack arrays dropped), unit by unit, with the same keep-if-smaller-and-proven rule. |
| [sizes.py](sizes.py) | Compiled size of every proven function's C against the original's size. |
| [permute.py](permute.py) | Try rewrites of one function that keep its meaning, kept when `fcmp.py --score` gets no worse. |
| [repeats.py](repeats.py) | The game functions whose original repeats one run of instructions many times: candidates for one loop written by hand (`PROMPT_handshrink.md`). |

## Prompts

Work to hand to another agent, with its placeholders filled in; each carries the rules it needs.

A prompt may use another prompt one level deep, by naming it; a prompt that another one uses is a leaf (it names none) and has a
fixed effort limit, so no chain of prompts can recurse or run without end.

| prompt | what it hands over |
|---|---|
| [PROMPT_handshrink.md](PROMPT_handshrink.md) | A smaller C version of one function by hand, in a scratch proof folder, proven at the coverage bar and marked `/* manual: */`. |
| [PROMPT_install.md](PROMPT_install.md) | That hand version checked again, its callers checked, put into the repo and proven there, the result registers checked. |
| [PROMPT_pass.md](PROMPT_pass.md) | A rewrite pass counted on the game's own code, tried on about 40 units in a scratch copy, judged, then run. |
