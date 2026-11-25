#!/usr/bin/env bash
# Keep the paper ledger across cloud sessions by storing it on the `paper-data` branch.
#   scripts/ledger_sync.sh pull   # restore data/trades.db before a run
#   scripts/ledger_sync.sh push   # save data/trades.db, data/report.html and the dashboard's ledger.json
set -euo pipefail
cd "$(dirname "$0")/.."
BRANCH=paper-data
WT=$(mktemp -d)
cleanup() { git worktree remove --force "$WT" >/dev/null 2>&1 || true; }
trap cleanup EXIT

if git fetch -q origin "$BRANCH" 2>/dev/null; then
  git worktree add -q -f "$WT" FETCH_HEAD
  git -C "$WT" checkout -q -B "$BRANCH"
else
  git worktree add -q --detach "$WT"
  git -C "$WT" checkout -q --orphan "$BRANCH"
  git -C "$WT" rm -rq --cached . >/dev/null 2>&1 || true
  find "$WT" -mindepth 1 -maxdepth 1 ! -name .git -exec rm -rf {} +
fi

case "${1:-}" in
  pull)
    mkdir -p data
    if [ -f "$WT/trades.db" ]; then cp "$WT/trades.db" data/trades.db; echo "restored ledger from $BRANCH"
    else echo "no saved ledger yet; starting fresh"; fi ;;
  push)
    cp data/trades.db "$WT/trades.db"
    [ -f data/report.html ] && cp data/report.html "$WT/report.html"
    python3 -m tradeagent.cli site --out "$WT/ledger.json" >/dev/null   # feeds the dashboard in site/
    git -C "$WT" add trades.db ledger.json
    [ -f "$WT/report.html" ] && git -C "$WT" add report.html
    if git -C "$WT" diff --cached --quiet; then echo "ledger unchanged"; exit 0; fi
    git -C "$WT" -c user.name="BULLSHOT paper agent" -c user.email="paper-agent@users.noreply.github.com" commit -qm "Paper ledger $(date -u +%Y-%m-%d)"
    for i in 1 2 3 4; do git -C "$WT" push -q origin "$BRANCH" && break; sleep $((2**i)); done
    echo "saved ledger to $BRANCH" ;;
  *) echo "usage: $0 pull|push" >&2; exit 2 ;;
esac
