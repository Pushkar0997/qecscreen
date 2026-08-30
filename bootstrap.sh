#!/usr/bin/env bash
# Run once, from inside the unzipped qecscreen/ directory.
set -euo pipefail

git init
git add -A
git commit -m "chore: spec system and project skeleton"

echo
echo "Next:"
echo "  1. gh repo create qecscreen --public --source=. --push"
echo "     (or create the repo on github.com and: git remote add origin <url> && git push -u origin main)"
echo "  2. pip install -r requirements.txt && pytest"
echo "  3. Fill the repo URL in BRIEF.md"
echo "  4. Start at M0-SETUP-01 in spec/tasks.md"
