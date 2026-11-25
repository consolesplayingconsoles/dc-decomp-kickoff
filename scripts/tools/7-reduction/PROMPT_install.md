# Prompt: take a hand version into the tree (step 7)

After `PROMPT_handshrink.md`: an agent's proven version sits in its scratch folder `build/manual/proof_<function>/`. This checks it
again and puts it into the repo. Give this to an agent with `<function>` and `<unit>` filled in.

---

Take the hand version of `<function>` (unit `<unit>`) from `build/manual/proof_<function>/` into the repo, after checking it again
yourself. Commands from the repo root, always `nice -n 19`, one compile at a time. Do not start while a build or a shrink runs in
the repo (check the processes).

1. Check it in the scratch folder, not from the agent's report: `python3 -I tools/sim/equiv.py <unit> <function>` there must say
   EQUIVALENT with at least 70-80% of the instructions run, and `sizes.unit_sizes('<unit>')` must give the size reported. The
   function must carry its `/* manual: ... */` line.
2. Compare the two units' definitions (the function names and return types defined in the repo's `<unit>` against the scratch
   copy): only `<function>` may differ. If its return type or parameters changed (`void` for an unread result, fewer parameters),
   list every other file that declares or calls it (`grep -rn <function> src`) and say whether any caller uses what was dropped.
3. Back up: copy the repo's `<unit>` and `tests/<unit stem>/<function>.json` to `build/manual/backup-before-<function>/`.
4. Copy the scratch folder's `<unit>` and case file over the repo's.
5. Prove the whole unit in the repo: `python3 -I tools/sim/equiv.py <unit>`: every function EQUIVALENT, none DIFFERS. If one
   differs, copy the backup back and stop.
6. Run `python3 -I tools/8-build/retcheck.py`: no definition returning in the wrong register, no void function whose value a caller
   reads. If the parameters changed, also `python3 -I tools/8-build/protocheck.py`.

Rules: change nothing else; no commit, no build; never kill a process you did not start.

Report: old and new size of the function, the equiv line in the repo, the retcheck line, the callers checked, the backup path.
