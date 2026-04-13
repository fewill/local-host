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
| `backup-usb.service` | Oneshot | Encrypted sync to USB drive + S3 |
| `backup-poller.service` | Long-running | SQS poller that listens for backup-related events |

### versionpulse (`../versionpulse`)

| Unit | Type | Purpose |
|---|---|---|
| `versionpulse.service` | Long-running | Monitors version log files and auto-commits changes to GitHub |

### opn-support (`../opn-support`)

| Unit | Type | Purpose |
|---|---|---|
| `opn-support-poller.service` | Long-running | Monitors the #ops-support Slack channel for new messages |

### analyzerouting (`../analyzerouting`)

| Unit | Type | Purpose |
|---|---|---|
| Cron — Mondays 06:00 | Weekly | Fetches FedNow, RTP, and ACH routing tables; alerts #ops-support on failure |

## Adding a new process

1. Open `status.sh`
2. Add a section header if it's a new project: `echo -e "\n${BOLD}project-name${RESET}"`
3. Add one line per unit: `print_unit "<unit-name>" "<Display Label>" "<short description>"`
