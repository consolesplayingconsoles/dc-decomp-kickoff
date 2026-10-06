#!/usr/bin/env bash
# zip.sh: build dist/dc-decomp-kickoff.zip, the installable skill (one folder: SKILL.md, scripts/,
# template/, references/), from every file here git does not ignore. Upload it to Claude as a skill.
set -euo pipefail
cd "$(dirname "$0")"
mkdir -p dist
python3 - <<'PY'
import subprocess, zipfile
files = [f for f in subprocess.check_output(["git", "ls-files", "-z", "--cached", "--others", "--exclude-standard"]).decode().split("\0")
         if f and not f.startswith("dist/") and f != "zip.sh"]
with zipfile.ZipFile("dist/dc-decomp-kickoff.zip", "w", zipfile.ZIP_DEFLATED) as z:
    for f in files:
        z.write(f, "dc-decomp-kickoff/" + f)
print("%d files" % len(files))
PY
echo "Upload this to Claude as a skill: $PWD/dist/dc-decomp-kickoff.zip"
