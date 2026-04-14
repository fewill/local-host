# CLAUDE.md — local-host

## Purpose

This repo is a lightweight operations index for the background processes running on this machine. Its only artifact right now is `status.sh`, a bash dashboard that queries systemd for the state of every managed service and timer.

## What lives here

- `status.sh` — the status dashboard script. Run it directly: `./status.sh`
- `README.md` — usage and process inventory

## Conventions

### status.sh structure

The script has two sections:

1. **Helpers** — colour variables, `print_unit` (systemd), and `print_cron` (cron jobs). `print_unit` queries `systemctl show` and `journalctl`; `print_cron` takes a schedule string, display label, and log file path and reports last log modification time and any error lines.

2. **Main** — calls `print_unit` or `print_cron` once per tracked process, grouped under bold project-name headers.

When adding a process, add the appropriate call under the correct project header (or create a new header). Do not refactor these functions to accept arrays or config files — keep it simple and explicit.

### Tracked projects

Processes come from sibling repos. Currently:
- `../usb-encrypt` — backup-usb.timer, backup-usb.service, backup-poller.service
- `../versionpulse` — versionpulse.service (system), versionpulse-autocommit.service (user)
- `../opn-support` — opn-support-poller.service
- `../issr-non-nativ` — issr-non-nativ.timer/service (user units, runs at 12:00/19:00/23:00 daily)
- `../analyzerouting` — cron job (Mondays 06:00), alerts #ops-support via opn-support/notifications/notify.py on failure
- `../month-end` — month-end-extract.timer/service and month-end-report.timer/service (user units, run 1st of each month)

When a new sibling repo has managed services, add them here and document them in README.md.

## Out of scope

This repo does not contain application code, deployment scripts, or configuration for the services it monitors. Those live in their respective project repos.
