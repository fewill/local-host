# CLAUDE.md — local-host

## Purpose

This repo is a lightweight operations index for the background processes running on this machine. Its only artifact right now is `status.sh`, a bash dashboard that queries systemd for the state of every managed service and timer.

## What lives here

- `status.sh` — the status dashboard script. Run it directly: `./status.sh`, or from anywhere via the `lh-status` alias defined in `~/.bashrc`
- `README.md` — usage and process inventory

## Conventions

### status.sh structure

The script has two sections:

1. **Helpers** — colour variables, global counters (`_TOTAL`, `_OK`, `_FAILED`), and three print functions:
   - `print_unit` — system-scope systemd units; queries `systemctl show` and `journalctl`
   - `print_user_unit` — user-scope systemd units (`--user` flag); same queries
   - `print_cron` — cron jobs; takes a schedule string, display label, and log file path; reports last log modification time and any error lines from the most recent run
   Each function increments the counters before returning.

2. **Main** — calls the appropriate print function once per tracked process, grouped under bold project-name headers. Ends with a summary bar showing total unit count and OK vs. failed.

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
