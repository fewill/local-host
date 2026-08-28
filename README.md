# local-host — unified status dashboard for all background services and timers running on this machine

An index and operations dashboard for the background processes running on this AWS EC2 instance. Rather than hunting through individual project repos to check on services, use this repo to get a unified status view — as a web dashboard or from the terminal.

## Usage

**Web dashboard** (always-on, installed as a systemd `--user` service): open [http://127.0.0.1:8099](http://127.0.0.1:8099) in a browser. Auto-refreshes every 15 seconds. `GET /api/status` returns the same data as JSON; `GET /health` is a liveness probe.

**Terminal**:
```bash
./status.sh
# or from anywhere:
lh-status
```

Prints a grouped summary of every managed systemd service and timer — active state, last run time, next scheduled run, and any recent errors from the journal. A summary line at the end shows total unit count and how many are OK vs. failed.

Both surfaces are built on the same Python core (`lh_dashboard/`) and read the same unit inventory (`config/units.yaml`) — see [Architecture](#architecture) below.

## How oneshot units are reported

A oneshot sits at `inactive (dead)` between runs, so its state line says nothing about whether the last run actually worked. Two adjustments make them legible:

- **`Finished:` and `Last exit:`** — the timestamp the last run ended (`InactiveEnterTimestamp`) and the code it exited with (`ExecMainStatus`), colored green for 0 and red otherwise. These only print once the unit is idle. While a run is in flight the line reads `Last run: in progress — result pending`, because systemd resets `ExecMainStatus` to 0 at start and leaves `InactiveEnterTimestamp` pointing at the *previous* run — reporting either mid-run would announce a successful run at the wrong timestamp.
- **A 24-hour journal window**, against 1 hour for long-running services. A midnight job that fails at 02:00 is invisible in a 1-hour window by the time anyone reads the dashboard over coffee. `backup-usb.service` failed at 02:27 on 2026-08-11 and the dashboard showed clean at 09:00; that is what prompted the change. This window is applied by unit type (`Type=oneshot` → 24h, everything else → 1h) regardless of whether the unit is system- or user-scoped — the original bash implementation's user-scope check hardcoded a 1h window for all user units, which silently missed this exact failure mode for user-scope oneshots; that bug is fixed in the current implementation and covered by `tests/unit/test_core_window_selection.py`.

## Architecture

Rewritten in 2026 from a single 300-line bash script into a small tested Python package, to fix a real bug (see above), eliminate drift between this file, `CLAUDE.md`, and the script's hardcoded unit list, and add a web UI.

```
lh_dashboard/
├── systemd_client.py   # the only module that shells out to systemctl/journalctl
├── core.py             # StatusChecker, oneshot classification, error-window selection, tally
├── config.py           # loads config/units.yaml
├── render_terminal.py  # terminal renderer (used by cli.py / status.sh)
├── web.py              # Flask app: HTML dashboard + JSON API
├── cli.py              # lh-status entry point
└── render_readme.py    # regenerates the tables below from config/units.yaml
config/units.yaml        # single source of truth for every tracked unit
tests/unit/, tests/functional/   # pytest suite — run with `.venv/bin/pytest tests/`
deploy/local-host-dashboard.service   # the web dashboard's own systemd --user unit
run.py                   # waitress entrypoint used by the systemd unit
status.sh                 # now a 3-line wrapper around `lh-status`, kept so the
                           # existing bashrc alias and Claude Code skill keep working
```

### Adding a new process

Edit `config/units.yaml` — add the unit under its project (or a new project header). No code changes needed; both `lh-status` and the web dashboard read this file directly. After editing, regenerate the tables below with:

```bash
.venv/bin/lh-render-readme
```

### Setup (fresh checkout)

```bash
python3 -m venv .venv
.venv/bin/pip install -e ".[test]"
.venv/bin/pytest tests/unit tests/functional   # should all pass before touching anything
```

### Install / re-install the web dashboard

```bash
cp /home/fewill/code/local-host/deploy/local-host-dashboard.service ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user enable --now local-host-dashboard.service
systemctl --user status local-host-dashboard.service
curl -s http://127.0.0.1:8099/health
```

## Processes tracked

The tables below are generated from `config/units.yaml` — do not hand-edit between the markers; run `.venv/bin/lh-render-readme` after changing the config instead.

<!-- BEGIN GENERATED UNITS -->

### usb-encrypt (`../usb-encrypt`)

| Unit | Type | Purpose |
|---|---|---|
| `backup-usb.timer` | Timer | triggers backup-usb.service daily |
| `backup-usb.service` | Service | encrypted USB + S3 sync (oneshot) — inactive (dead) is normal; runs only when triggered by timer |
| `backup-poller.service` | Service | SQS poller — always running |

### versionpulse (`../versionpulse`)

Running on EC2 (i-02e64f5c34c5b1e76) — both versionpulse.service and versionpulse-autocommit.service. SSH: versionpulse-aws

### opn-support (`../opn-support`)

| Unit | Type | Purpose |
|---|---|---|
| `opn-support-poller.service` | Service | Slack #ops-support channel monitor — always running |
| `sms_inbound_poller.service` | Service | SQS poller for Twilio inbound SMS replies — always running |
| `opn-support-mailbox-import.timer` | Timer | triggers mailbox import every 15 min |
| `opn-support-mailbox-import.service` | Service | scans Thunderbird INBOX for new support emails (oneshot) — inactive (dead) is normal; runs only when triggered by timer |
| `gh-event-poller.service` | Service | watches opn-support + TransferError repos for issue comments and state changes — always running |
| `opn-support-rtp-funding-watcher.service` | Service | inotify watch for rtp-funding-*.json drops from month-end; drafts delivery under automated-deliveries/, Slack-notifies #ops-support — always running |

### slack-notify (`../slack-notify`)

| Unit | Type | Purpose |
|---|---|---|
| `slack-notify-poller.service` | Service | OPN Assistant DM → desktop notification — always running |
| `poller-healthcheck.timer` | Timer | triggers poller health check every 15 min |
| `poller-healthcheck.service` | Service | verifies slack-notify/rfp/sms pollers are active and logging; alerts #ops-support after 1h of sustained failure (oneshot) — inactive (dead) is normal; runs only when triggered by timer |

### bank-core-config-tests (`../bank-core-config-tests`)

| Unit | Type | Purpose |
|---|---|---|
| `rfp_poller.service` | Service | SQS poller — auto-accepts inbound OPN RFPs, Slack DM on accept/update — always running |

### issr-non-nativ (`../issr-non-nativ`)

| Unit | Type | Purpose |
|---|---|---|
| `issr-non-nativ.timer` | Timer | triggers return at 12:00, 19:00, 23:00 daily |
| `issr-non-nativ.service` | Service | returns non-native holdings to internal issuers (oneshot) — inactive (dead) is normal; runs only when triggered by timer; requires VPN (DNS for walletapi.bridge.opnfi.net) |

### rcnt-xfer-anlsys (`../rcnt-xfer-anlsys`)

| Unit | Type | Purpose |
|---|---|---|
| `waiting-monitor.timer` | Timer | triggers waiting transfer scan every 15 min |
| `waiting-monitor.service` | Service | detects stuck RTP/FedNow credits, drops alert to opn-support (oneshot) — inactive (dead) is normal; runs only when triggered by timer |

### grafana-logs (`../grafana-logs`)

| Unit | Type | Purpose |
|---|---|---|
| `grafana-logs-monitor.service` | Service | polls Loki every 15 min for duplicate credit requests — always running |

### analyzerouting (`../analyzerouting`)

| Unit | Type | Purpose |
|---|---|---|
| `analyzerouting-sync.timer` | Timer | triggers fetch + commit + push every Monday at 06:00 |
| `analyzerouting-sync.service` | Service | fetches FedNow/RTP/ACH tables and pushes to GitHub (oneshot) — inactive (dead) is normal; runs only when triggered by timer; requires bradley-wilkes-2024 OpenVPN and 1Password desktop |

### month-end (`../month-end`)

| Unit | Type | Purpose |
|---|---|---|
| `month-end-extract.timer` | Timer | triggers extraction on 1st of each month at 06:00 |
| `month-end-extract.service` | Service | pulls transaction data from API (oneshot) — inactive (dead) is normal; runs only when triggered by timer; requires 1Password desktop |
| `month-end-report.timer` | Timer | triggers report generation on 1st of each month at 07:00 |
| `month-end-report.service` | Service | generates month-end Excel reports (oneshot) — inactive (dead) is normal; runs only when triggered by timer |
| `weekly-rtp-funding-report.timer` | Timer | fires Thu + Fri at 15:50 CT (2:50pm MT); wrapper gates on delivery date (holiday-aware) |
| `weekly-rtp-funding-report.service` | Service | generates NABC weekly RTP prefunding report (oneshot) — inactive (dead) is normal; runs only on delivery day |

### onboard (`../onboard`)

| Unit | Type | Purpose |
|---|---|---|
| `nabc-demo-buildup.timer` | Timer | triggers buildup run 1x/day (07:13 local) |
| `nabc-demo-buildup.service` | Service | RTNAUTO random-amount suite against opn-cust-demo pool-backed account (oneshot) — inactive (dead) is normal; runs only when triggered by timer. Temporary, remove after the NABC demo. |

### webhook (`../webhook`)

| Unit | Type | Purpose |
|---|---|---|
| `webhook.service` | Service | local HTTP sink on 127.0.0.1:8098 for OPN/WingCash sandbox webhooks — always running |

### local-host (`.`)

| Unit | Type | Purpose |
|---|---|---|
| `local-host-dashboard.service` | Service | this dashboard's own web service on 127.0.0.1:8099 — always running. A down dashboard can't render itself, so this entry is only meaningful when checked from lh-status or a secondary vantage point. |

<!-- END GENERATED UNITS -->

## Notes and install steps by project

Context that doesn't belong in `config/units.yaml` (AWS backends, VPN/1Password dependencies, per-project install steps, shared credentials) lives here instead, keyed by project name to match the generated tables above.

### opn-support

**AWS backend (account 864899860638, us-east-2):** Twilio webhook → API Gateway `sms-notify-api` (ID: `0kb5uecrik`) → Lambda `sms-notify-handler` → SQS queue `sms-notify-events`. The local `sms_inbound_poller.service` polls that queue. IAM role: `backup-lambda-role`.

#### Install / re-install (opn-support-mailbox-import)

```bash
# 1. Seed state on first install.
#    This records every current inbox message as already-seen without saving any
#    .eml files. Without this step, the first timer run would treat all existing
#    support-domain emails as new and dump them all into the repo root at once.
#    Only mail that arrives after the seed is saved going forward.
#    To reset: delete ~/.opn_mailbox_import_state and re-run --seed.
cd /home/fewill/code/opn-support
.venv/bin/python3 mailbox_import.py --seed

# 2. Copy unit files
sudo cp notifications/opn-support-mailbox-import.service /etc/systemd/system/
sudo cp notifications/opn-support-mailbox-import.timer   /etc/systemd/system/

# 3. Enable and start
sudo systemctl daemon-reload
sudo systemctl enable --now opn-support-mailbox-import.timer

# 4. Verify
sudo systemctl status opn-support-mailbox-import.timer
```

After enabling, each run drops new support emails as `.eml` files in the opn-support repo root, ready for `/opn-support` to process. A message is saved if its sender domain is in `SUPPORT_DOMAINS` or it was addressed to a monitored inbox (`support@opn.inc`, `enable@opn.inc`). Each saved message logs `Saved: <filename>  |  via <domain or address>  |  <subject>`. Unit files are kept in `../opn-support/notifications/`.

If Thunderbird is actively writing to the INBOX (`INBOX.lock` present), the run exits cleanly and logs a warning — no data is read or saved. The timer retries in 15 minutes.

### slack-notify

**AWS backend (account 864899860638, us-east-2):** The slack-notify infrastructure — SQS queues and any Lambda components — runs in AWS account 864899860638. The local systemd service polls those queues and delivers desktop notifications.

**Shared poller credentials:** `slack-notify-poller`, `rfp_poller`, and `sms_inbound_poller` all read AWS credentials from `/etc/opn-pollers.env` (`root:fewill`, mode `0640`) via `EnvironmentFile=`. The credentials belong to the `opn-poller-sqs` IAM user, scoped to `ReceiveMessage`/`DeleteMessage`/`GetQueueAttributes` on the `slack-notify-events`, `sms-notify-events`, and `opn-rfp-events` queues and nothing else. A credential failure is fatal — each poller logs `CRITICAL` and exits rather than retrying, so the unit lands in `failed` state instead of looping silently.

**Poller health check** (`../slack-notify/monitoring/poller-healthcheck.sh`, installed at `/usr/local/bin/`): checks two failure shapes per poller — unit not active, and unit active but its log has gone silent past two missed hourly heartbeats (`STALE_AFTER=7200`). Alerting is deliberately slow: a service must fail continuously for `FAIL_FOR` (1h) **and** across `MIN_CHECKS` (3) consecutive runs before one alert goes to `#ops-support` via `opn-support/notifications/notify.py`, then at most once per `REMIND_AFTER` (24h). Any healthy check silently resets the counter, so restarts and reboots produce nothing. Recovery is logged to syslog only — never announced. Every observation, including suppressed ones, is visible via `journalctl -t poller-healthcheck`. Alert state lives in `/var/lib/poller-healthcheck/<unit>`.

Because alerts route through `notify.py`, the same 1Password dependency noted under `grafana-logs` applies: if the desktop app is not running, Slack alerts fail and only the desktop notification and syslog entry remain.

### cancelmonitor

Deployed at `/opt/cancelmonitor` running as the `cancelmonitor` system user. Credentials loaded from `/etc/cancelmonitor/environment` (contains `OP_SERVICE_ACCOUNT_TOKEN`). Service file: `../cancelmonitor/deployment/cancelmonitor.service`. Not currently in `config/units.yaml` — add it there if it should be tracked by this dashboard.

### issr-non-nativ

**VPN dependency:** resolves `walletapi.bridge.opnfi.net` which is only reachable over the VPN. Boot-time failures with DNS resolution errors indicate the VPN was not yet connected.

### month-end

**1Password dependency:** `month-end-extract.service` resolves credentials via the 1Password desktop app. Boot-time failures with `reqwest` auth errors indicate the app was not yet open.

### grafana-logs

Credentials loaded from `.env` in the repo root (contains `OP_SERVICE_ACCOUNT_TOKEN`). Loki credentials resolved from 1Password at startup.

#### Install / re-install

```bash
cp /home/fewill/code/grafana-logs/grafana-logs-monitor.service ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user enable --now grafana-logs-monitor.service
systemctl --user status grafana-logs-monitor.service
```

### analyzerouting

**VPN dependency:** this service requires the `bradley-wilkes-2024` OpenVPN connection to be active. The connection is set to autoconnect (`connection.autoconnect yes`) and the service unit includes a 60-second pre-check that waits for the VPN before proceeding. If the VPN is not up within 60 seconds, the service fails cleanly.

**1Password dependency:** credentials are resolved via the 1Password desktop app (used by both the main sync script and `opn-support/notifications/notify.py` on failure). The desktop app must be running; boot-time failures with `reqwest` auth errors indicate it was not yet open.

### onboard

**Temporary — remove after the NABC demo.** Builds up multi-day pool-ledger and transaction history ahead of an NABC demo (week of 2026-07-25). Reduced from 3x/day to 1x/day on 2026-07-29. Sized to stay comfortably under the account's $250K/day `deposit_from_wallet` limit (~$22.5K/day expected at 1 run × 9 tx × ~$2,500 avg) — no longer expected to hit the limit at this cadence. Logs to `../onboard/local-notes/nabc_demo_buildup.log`. Credentials are plaintext Basic-Auth app creds embedded in the script (not `op://` — this job runs unattended and doesn't resolve 1Password refs), which is why the script lives in the gitignored `local-notes/` directory rather than the repo proper.

#### Install / re-install

```bash
cp /home/fewill/code/onboard/local-notes/systemd/nabc-demo-buildup.service ~/.config/systemd/user/
cp /home/fewill/code/onboard/local-notes/systemd/nabc-demo-buildup.timer   ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user enable --now nabc-demo-buildup.timer
systemctl --user status nabc-demo-buildup.timer
```

#### Manual run

```bash
../onboard/local-notes/run_nabc_demo_buildup.sh
```

Triggers one buildup run immediately (outside the schedule) and tails its log until it finishes.

#### Removal (after the demo)

```bash
systemctl --user disable --now nabc-demo-buildup.timer
rm ~/.config/systemd/user/nabc-demo-buildup.timer ~/.config/systemd/user/nabc-demo-buildup.service
systemctl --user daemon-reload
```

### webhook

#### Install / re-install

```bash
cp /home/fewill/code/webhook/deploy/webhook.service ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user enable --now webhook.service
systemctl --user status webhook.service
```

### local-host

This repo's own dashboard service. See [Install / re-install the web dashboard](#install--re-install-the-web-dashboard) above. Runs on 127.0.0.1:8099 via waitress (not Flask's dev server — every request does blocking `systemctl`/`journalctl` calls across 30+ units).

## Machine configuration

### VPN autoconnect (`/etc/NetworkManager/dispatcher.d/99-vpn-autoconnect`)

A NetworkManager dispatcher script that brings up the `bradley-wilkes-2024` OpenVPN connection whenever a network interface connects. This ensures the VPN is available at boot before VPN-dependent services (`issr-non-nativ`, `analyzerouting-sync`) run.

**Why it exists:** NM's built-in `connection.autoconnect yes` has a race condition at boot — the VPN sometimes comes up 3+ minutes late if the `ifstate` file isn't ready when NM first tries. The dispatcher script fires on every interface `up` event and retries cleanly.

**To reinstall after a fresh OS install:**

```bash
sudo tee /etc/NetworkManager/dispatcher.d/99-vpn-autoconnect << 'EOF'
#!/bin/bash
INTERFACE="$1"
ACTION="$2"
VPN="bradley-wilkes-2024"

[[ "$ACTION" != "up" ]] && exit 0
[[ "$INTERFACE" == tun* ]] && exit 0

if nmcli con show --active | grep -q "$VPN"; then
    exit 0
fi

nmcli con up "$VPN" &
EOF
sudo chmod 755 /etc/NetworkManager/dispatcher.d/99-vpn-autoconnect
```

### 1Password autostart (`~/.config/autostart/1password.desktop`)

An XDG autostart entry that launches 1Password silently at login. The app starts in the system tray without opening the main window; the SSH agent comes up immediately and prompts for unlock when first needed (git signing, service credentials).

**Why it exists:** `analyzerouting-sync`, `month-end-extract`, and git commit signing all depend on the 1Password SSH agent. Without autostart, a reboot leaves the agent unavailable until the app is opened manually.

**To reinstall after a fresh OS install:**

```bash
cat > ~/.config/autostart/1password.desktop << 'EOF'
[Desktop Entry]
Name=1Password
Exec=/opt/1Password/1password --silent %U
Terminal=false
Type=Application
Icon=1password
StartupWMClass=1Password
Comment=Start 1Password at login (tray, no window)
EOF
```
