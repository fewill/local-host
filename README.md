# local-host

An index and operations dashboard for the background processes running on this machine. Rather than hunting through individual project repos to check on services, run one script here to get a unified status view.

## Usage

```bash
./status.sh
```

Prints a grouped summary of every managed systemd service and timer — active state, last run time, next scheduled run, and any recent errors from the journal.

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

### issr-non-nativ (`../issr-non-nativ`)

| Unit | Type | Purpose |
|---|---|---|
| `issr-non-nativ.timer` | Timer (user) | Triggers holdings return at 12:00, 19:00, and 23:00 daily |
| `issr-non-nativ.service` | Oneshot (user) | Returns non-native holdings to internal issuers across banking platforms |

### month-end (`../month-end`)

| Unit | Type | Purpose |
|---|---|---|
| `month-end-extract.timer` | Timer (user) | Triggers data extraction on the 1st of each month at 06:00 |
| `month-end-extract.service` | Oneshot (user) | Pulls transaction data from API — inactive (dead) is normal; runs only when triggered by timer |
| `month-end-report.timer` | Timer (user) | Triggers report generation on the 1st of each month at 07:00 |
| `month-end-report.service` | Oneshot (user) | Generates month-end Excel reports — inactive (dead) is normal; runs only when triggered by timer |

### analyzerouting (`../analyzerouting`)

| Unit | Type | Purpose |
|---|---|---|
| Cron — Mondays 06:00 | Weekly | Fetches FedNow, RTP, and ACH routing tables; alerts #ops-support on failure |

## Adding a new process

1. Open `status.sh`
2. Add a section header if it's a new project: `echo -e "\n${BOLD}project-name${RESET}"`
3. Add one line per unit: `print_unit "<unit-name>" "<Display Label>" "<short description>"`
