#!/usr/bin/env bash
set -euo pipefail

REPO="${TCT_PIPELINE_REPO:-/home/ubuntu/work/openmc/sweep}"
BRANCH="${TCT_PIPELINE_BRANCH:-agent/tct-pulse-train-audit}"
REMOTE="${TCT_PIPELINE_REMOTE:-origin}"
INTERVAL="${TCT_PIPELINE_INTERVAL:-2min}"
UNIT_DIR="$HOME/.config/systemd/user"
SERVICE="$UNIT_DIR/tct-git-worker.service"
TIMER="$UNIT_DIR/tct-git-worker.timer"
WORKER="$REPO/tools/agent_pipeline/tct_git_worker.py"

cd "$REPO"

if [[ ! -d .git ]]; then
  echo "Not a git checkout: $REPO" >&2
  exit 2
fi

current="$(git branch --show-current)"
if [[ "$current" != "$BRANCH" ]]; then
  echo "Expected branch '$BRANCH', current branch is '$current'." >&2
  echo "Switch to the research branch before installing the worker." >&2
  exit 3
fi

if [[ ! -f "$WORKER" ]]; then
  echo "Worker not found: $WORKER" >&2
  exit 4
fi

mkdir -p "$UNIT_DIR"

cat > "$SERVICE" <<EOF
[Unit]
Description=TCT Git research pipeline worker
After=network-online.target
Wants=network-online.target

[Service]
Type=oneshot
Environment=TCT_PIPELINE_REPO=$REPO
Environment=TCT_PIPELINE_BRANCH=$BRANCH
Environment=TCT_PIPELINE_REMOTE=$REMOTE
ExecStart=/usr/bin/python3 $WORKER
WorkingDirectory=$REPO
Nice=5

[Install]
WantedBy=default.target
EOF

cat > "$TIMER" <<EOF
[Unit]
Description=Poll Git for TCT research jobs

[Timer]
OnBootSec=45s
OnUnitActiveSec=$INTERVAL
AccuracySec=15s
Persistent=true
Unit=tct-git-worker.service

[Install]
WantedBy=timers.target
EOF

systemctl --user daemon-reload
systemctl --user enable --now tct-git-worker.timer

echo
echo "Installed TCT Git research worker."
echo "Repo:     $REPO"
echo "Branch:   $BRANCH"
echo "Interval: $INTERVAL"
echo
echo "Timer status:"
systemctl --user --no-pager status tct-git-worker.timer || true

echo
echo "Testing Git push permission (dry run)..."
if git push --dry-run "$REMOTE" "HEAD:$BRANCH" >/dev/null 2>&1; then
  echo "Git push dry-run: OK"
else
  echo "WARNING: Git push dry-run failed. The worker can run jobs but cannot return results until Git push authentication works." >&2
fi

echo
echo "Run one poll immediately without waiting for the research job to finish:"
echo "  systemctl --user start --no-block tct-git-worker.service"
echo "Follow worker logs with:"
echo "  journalctl --user -u tct-git-worker.service -f"
echo "Check the active worker with:"
echo "  systemctl --user status tct-git-worker.service"
echo "List timer state with:"
echo "  systemctl --user list-timers tct-git-worker.timer"
echo
echo "Optional, if you want the user service to run before login/after logout:"
echo "  sudo loginctl enable-linger $USER"
