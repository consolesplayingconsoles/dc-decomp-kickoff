# Prompt: fix the function entries the reports flag (step 2)

Give this to an agent as it is. It is self-contained; the agent needs no other briefing.

---

Fix the entries of `functions.txt` that the reports flag, so that every entry is one whole function, and the build still rebuilds the
executable byte for byte. This is step 2's output: the generator of step 5 stops on these functions ("runs off the end of its listed
size", "branch past the listed size", "calls ..., an entry functions.txt does not list") until they are right.

Run every command from the repo root, always with `nice -n 19`.

1. Collect the reports (they change nothing):
   - `python3 -I tools/1-2-baseline/missed_funcs.py --targets 1ST_READ.BIN "$(cat BASE)" functions.txt`: addresses listed code calls,
     branches or tail-jumps to that no entry starts;
   - `python3 -I tools/1-2-baseline/checksizes.py`: branches past an entry's end, and `overlap:` lines (an entry running into the next);
   - `python3 -I tools/1-2-baseline/checksizes.py --merge`: pieces of one function listed apart (a loop's entry branch listed alone
     included); `--extend`: entries whose own flow runs past their listed end.
2. Read each one before deciding: `python3 -I tools/sim/shdis.py <start> <end>` around it. Decide one of:
   - a new entry `F <address> <size> FUN_<address>`: code that starts a function (right after an rts/jmp and its delay slot, a
     prologue, or a tail-jump target), its size to its last rts or tail jump and delay slot (a literal pool after it is not code);
   - a smaller size: the entry ran past its own end into the next function or into a pool or data;
   - a merge: the pieces are one function (a `bra` into the next entry, which branches back; code that runs on into the next
     entry). Keep the first entry's name, since callers name it;
   - nothing: a target that is data (it does not decode as code) or a label inside its own function.
   A report line is a lead, not a verdict: read the code first.
3. Edit `functions.txt` (address order), delete the asm file of every entry removed by a merge, then
   `python3 -I tools/1-2-baseline/split_asm.py 1ST_READ.BIN "$(cat BASE)" functions.txt .`
4. The byte match is checked with a build, and a build is the user's to run: say exactly which entries changed and ask for
   `bash build.sh` (it must print MATCH; `cmp build/out.bin 1ST_READ.BIN` too).
5. For every entry whose range changed and had C: `python3 -I tools/sim/equiv.py <its file> <name>` (a changed size is a changed
   proof range). New entries get C by the generator or by hand (PROMPT_prove.md).

Rules: write nothing but `functions.txt` and the asm files split_asm.py writes or a merge removes. No new scripts. Never kill a process
you did not start. No build yourself, no git.

Report: a table, one row per report line: the address, the decision (new entry / size / merge / nothing) and why, in a sentence.
Then the entries changed, for the build check. Short.
