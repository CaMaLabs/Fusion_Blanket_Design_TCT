# Ubuntu Repo Dashboard

Small dependency-free web dashboard for pulling the Fusion/TCT Git repo on the
Ubuntu runner and launching whitelisted validation commands.

## Start

```bash
cd /root/Fusion_Blanket_Design_TCT
bash tools/ubuntu_repo_dashboard/run_dashboard.sh
```

Then open:

```text
http://45.50.0.74:8765
```

For a private dashboard, bind to localhost and use an SSH tunnel:

```bash
python3 tools/ubuntu_repo_dashboard/server.py --repo /home/ubuntu/Fusion_Blanket_Design_TCT
ssh -L 8765:127.0.0.1:8765 ubuntu@45.50.0.74
```

## Optional Token

Set `DASHBOARD_TOKEN` before starting the server. Browser requests must then
send the token in the UI token field.

```bash
export DASHBOARD_TOKEN='change-me'
python3 tools/ubuntu_repo_dashboard/server.py --repo /home/ubuntu/Fusion_Blanket_Design_TCT
```

## Whitelisted Actions

- `fetch_status`: run `git fetch` and report incoming files.
- `pull_ff`: fast-forward the selected branch.
- `smoke`: run `python3 liquid_lithium_stability/ruzic_fiflis_2016.py`.
- `tests`: run `python3 -m pytest -q tests`.
- `explorer_tests`: run `python3 -m pytest -q tools/tct_mechanism_explorer/tests` if present.
- `control_v2b`: run `bash tools/tct_mechanism_explorer/run_control_v2b.sh` if present.

The browser cannot submit arbitrary shell commands.

## Systemd Example

```ini
[Unit]
Description=Ubuntu repo dashboard
After=network-online.target

[Service]
Type=simple
WorkingDirectory=/root/Fusion_Blanket_Design_TCT
Environment=DASHBOARD_REPO=/home/ubuntu/Fusion_Blanket_Design_TCT
Environment=DASHBOARD_HOST=0.0.0.0
Environment=DASHBOARD_PORT=8765
ExecStart=/usr/bin/python3 /root/Fusion_Blanket_Design_TCT/tools/ubuntu_repo_dashboard/server.py
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
```
