# Prompt: prove one function (step 6)

Give this to an agent, with `<function>` and `<unit>` filled in. It is self-contained; the agent needs no other briefing.

---

Prove the C of ONE function of this decomp against the original code, with cases that run most of its instructions.

Function: `<function>`. Unit: `<unit>` (the C file that defines it). Run every command from the repo root, always with
`nice -n 19`, one compile at a time.

1. Read the original: `python3 -I tools/sim/shdis.py --func <function>`. Read the C. Decode every pool constant from its word (a float
   read wrong passes a check that never reaches it).
2. Check it: `python3 -I tools/sim/equiv.py <unit> <function>`. The line says `EQUIVALENT` or `DIFFERS`, and how many of the
   original's instructions the cases ran (`N of M instructions`). A pass at low coverage proves little: aim for every instruction.
3. Raise coverage with the repo's tools only:
   - `python3 -I tools/6-agentic/fuzzcases.py <function> --rounds 3000 --seed N --apply`, several seeds (the default 300 rounds
     usually keeps nothing);
   - `python3 -I tools/6-agentic/casesearch.py <function>`;
   - hand-written cases for what those cannot reach: `tests/<unit stem>/<function>.json` is `{"dev": [...], "holdout": [...]}`;
     a case has `about`, `poke` (address -> bytes as little-endian hex), `regs` (big-endian hex, `"r4": "0C600000"`), `calls`
     (mocked results). `tools/6-agentic/handcase.py` proves on such cases.
4. If it DIFFERS: print the differing call or access, read the original at that point, and say in two sentences what the C does
   wrong. Fix the C only if the step you were given says to; regenerating is `python3 -I tools/7-reduction/shrink.py --regen
   <function>`.

This prompt is a leaf: it uses no other prompt and hands no part of its work to another agent. Its effort is bounded: at most five
fuzzcases.py seeds at 3000 rounds, one casesearch.py run and twenty hand-written cases per function. When the cases still run
under the bar after that, stop and report the function as below the bar, with the instructions no case reaches; do not go on.

Rules: write nothing but the case file of this function (and the C, if told to fix it). No new scripts in the repo. Never kill a
process you did not start. No build, no git.

Report: the final equiv line, the cases added and by which tool, the instructions still not run and why (dead code, a value no
case can reach). Short.
