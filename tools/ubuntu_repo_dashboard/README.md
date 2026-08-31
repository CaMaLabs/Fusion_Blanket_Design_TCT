# Ubuntu Repo Dashboard

Small dependency-free web dashboard for pulling the Fusion/TCT Git repo on the
Ubuntu runner and launching whitelisted validation commands.

## Start

Recommended layout:

- app repo: `/home/ubuntu/Fusion_Blanket_Design_TCT` on `agent/ubuntu-repo-dashboard`
- run repo: `/home/ubuntu/tct_external_work/dashboard_run_repo` switching among test branches

```bash
cd /home/ubuntu/Fusion_Blanket_Design_TCT
DASHBOARD_REPO=/home/ubuntu/tct_external_work/dashboard_run_repo \
DASHBOARD_APP_REPO=/home/ubuntu/Fusion_Blanket_Design_TCT \
bash tools/ubuntu_repo_dashboard/run_dashboard.sh
```

Then open:

```text
http://45.50.0.74:8770
```

For a private dashboard, bind to localhost and use an SSH tunnel:

```bash
python3 tools/ubuntu_repo_dashboard/server.py \
  --repo /home/ubuntu/tct_external_work/dashboard_run_repo \
  --app-repo /home/ubuntu/Fusion_Blanket_Design_TCT
ssh -L 8770:127.0.0.1:8770 ubuntu@45.50.0.74
```

## Optional Token

Set `DASHBOARD_TOKEN` before starting the server. Browser requests must then
send the token in the UI token field.

```bash
export DASHBOARD_TOKEN='change-me'
python3 tools/ubuntu_repo_dashboard/server.py \
  --repo /home/ubuntu/tct_external_work/dashboard_run_repo \
  --app-repo /home/ubuntu/Fusion_Blanket_Design_TCT
```

## Whitelisted Actions

- `fetch_status`: run `git fetch` and report incoming files.
- `pull_ff`: fast-forward the selected branch, creating a local tracking branch
  from `origin/<branch>` when needed.
- `self_update`: pull `agent/ubuntu-repo-dashboard` and restart the dashboard.
- `smoke`: run `python3 liquid_lithium_stability/ruzic_fiflis_2016.py`.
- `tests`: run `python3 -m pytest -q tests`.
- `explorer_tests`: run `python3 -m pytest -q tools/tct_mechanism_explorer/tests` if present.
- `control_v2b`: run `bash tools/tct_mechanism_explorer/run_control_v2b.sh` if present.

The browser cannot submit arbitrary shell commands.

## Automation

By default the dashboard:

- fetches remotes every 60 seconds so new GitHub branches appear in the branch
  selector for the run repo.
- checks `agent/ubuntu-repo-dashboard` every 120 seconds when the dashboard is
  app repo is on that branch, then restarts itself after a fast-forward update.
- auto-commits and pushes new result files produced by successful run actions.

Auto-push is restricted to result paths:

```text
validation_runs/
validation_models/
explorer_run.log
tools/tct_mechanism_explorer/explorer.json
```

Pre-existing dirty files are not staged. To disable result publishing:

```bash
export DASHBOARD_AUTO_PUSH=0
```

The Result Files panel lists files under the configured result paths and
downloads them through token-protected API requests.

## Systemd Example

```ini
[Unit]
Description=Ubuntu repo dashboard
After=network-online.target

[Service]
Type=simple
WorkingDirectory=/home/ubuntu/Fusion_Blanket_Design_TCT
Environment=DASHBOARD_REPO=/home/ubuntu/tct_external_work/dashboard_run_repo
Environment=DASHBOARD_APP_REPO=/home/ubuntu/Fusion_Blanket_Design_TCT
Environment=DASHBOARD_HOST=0.0.0.0
Environment=DASHBOARD_PORT=8770
ExecStart=/usr/bin/python3 /home/ubuntu/Fusion_Blanket_Design_TCT/tools/ubuntu_repo_dashboard/server.py
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
```
