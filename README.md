# local-host — unified status dashboard for all background services and timers running on this machine

An index and operations dashboard for the background processes running on this machine. Rather than hunting through individual project repos to check on services, run one script here to get a unified status view.

## Usage

```bash
./status.sh
# or from anywhere:
lh-status
```

Prints a grouped summary of every managed systemd service and timer — active state, last run time, next scheduled run, and any recent errors from the journal. A summary line at the end shows total unit count and how many are OK vs. failed.

## Processes tracked

### usb-encrypt (`../usb-encrypt`)

| Unit | Type | Purpose |
|---|---|---|
| `backup-usb.timer` | Timer | Triggers the backup service daily at midnight |
| `backup-usb.service` | Oneshot | Encrypted sync to USB drive + S3 — inactive (dead) is normal; runs only when triggered by timer |
| `backup-poller.service` | Long-running | SQS poller that listens for backup-related events |

### versionpulse (`../versionpulse`)

| Unit | Type | Purpose |
|---|---|---|
| `versionpulse.service` | Long-running | Monitors OPN production platform versions; alerts on mismatches |
| `versionpulse-autocommit.service` | Long-running (user) | Watches version log file for changes and auto-commits/pushes to GitHub |

### opn-support (`../opn-support`)

| Unit | Type | Purpose |
|---|---|---|
| `opn-support-poller.service` | Long-running | Monitors the #ops-support Slack channel for new messages |
| `opn-support-mailbox-import.timer` | Timer | Triggers mailbox import every 15 minutes |
| `opn-support-mailbox-import.service` | Oneshot | Scans Thunderbird INBOX for new support emails (by sender domain or recipient address) and saves as .eml — inactive (dead) is normal; runs only when triggered by timer |

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

### issr-non-nativ (`../issr-non-nativ`)

| Unit | Type | Purpose |
|---|---|---|
| `issr-non-nativ.timer` | Timer (user) | Triggers holdings return at 12:00, 19:00, and 23:00 daily |
| `issr-non-nativ.service` | Oneshot (user) | Returns non-native holdings to internal issuers across banking platforms |

**VPN dependency:** resolves `walletapi.bridge.opnfi.net` which is only reachable over the VPN. Boot-time failures with DNS resolution errors indicate the VPN was not yet connected.

### month-end (`../month-end`)

| Unit | Type | Purpose |
|---|---|---|
| `month-end-extract.timer` | Timer (user) | Triggers data extraction on the 1st of each month at 06:00 |
| `month-end-extract.service` | Oneshot (user) | Pulls transaction data from API — inactive (dead) is normal; runs only when triggered by timer |
| `month-end-report.timer` | Timer (user) | Triggers report generation on the 1st of each month at 07:00 |
| `month-end-report.service` | Oneshot (user) | Generates month-end Excel reports — inactive (dead) is normal; runs only when triggered by timer |

**1Password dependency:** `month-end-extract.service` resolves credentials via the 1Password desktop app. Boot-time failures with `reqwest` auth errors indicate the app was not yet open.

### analyzerouting (`../analyzerouting`)

| Unit | Type | Purpose |
|---|---|---|
| `analyzerouting-sync.timer` | Timer (user) | Triggers routing table sync every Monday at 06:00 |
| `analyzerouting-sync.service` | Oneshot (user) | Fetches FedNow, RTP, and ACH routing tables and pushes to GitHub; alerts #ops-support on failure — inactive (dead) is normal; runs only when triggered by timer |

**VPN dependency:** this service requires the `bradley-wilkes-2024` OpenVPN connection to be active. The connection is set to autoconnect (`connection.autoconnect yes`) and the service unit includes a 60-second pre-check that waits for the VPN before proceeding. If the VPN is not up within 60 seconds, the service fails cleanly.

**1Password dependency:** credentials are resolved via the 1Password desktop app (used by both the main sync script and `opn-support/notifications/notify.py` on failure). The desktop app must be running; boot-time failures with `reqwest` auth errors indicate it was not yet open.

## Adding a new process

1. Open `status.sh`
2. Add a section header if it's a new project: `echo -e "\n${BOLD}project-name${RESET}"`
3. Add one line per unit: `print_unit "<unit-name>" "<Display Label>" "<short description>"`
