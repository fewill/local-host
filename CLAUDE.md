# CLAUDE.md — local-host

## Purpose

This repo is a lightweight operations index for the background processes running on this machine. It provides two renderers over the same tested Python core:

- **Web dashboard** — `local-host-dashboard.service` (systemd `--user`), a Flask app served by waitress at `http://127.0.0.1:8099`, auto-refreshing every 15s. `GET /api/status` (JSON), `GET /health` (liveness).
- **Terminal** — `lh-status` (installed console script; `status.sh` is now a 3-line `exec` wrapper around it, kept only so the existing `~/.bashrc` alias and the `local-host-status` Claude Code skill keep working unmodified).

## Architecture (rewritten 2026 from a single bash script)

```
lh_dashboard/
├── systemd_client.py    # the ONLY module that shells out to systemctl/journalctl
├── core.py              # StatusChecker, oneshot classification, error-window selection, tally, project grouping
├── config.py             # loads and validates config/units.yaml
├── render_terminal.py   # terminal renderer
├── web.py                # Flask app factory + routes (/, /api/status, /health)
├── cli.py                # lh-status entry point
└── render_readme.py     # regenerates README.md's unit tables from config/units.yaml
config/units.yaml         # single source of truth for every tracked unit
tests/unit/, tests/functional/   # pytest — run with `.venv/bin/pytest tests/unit tests/functional`
deploy/local-host-dashboard.service   # the dashboard's own systemd --user unit
run.py                    # waitress entrypoint (not Flask's dev server — every
                           # request does blocking systemctl/journalctl I/O)
status.sh                  # thin wrapper: exec .venv/bin/lh-status "$@"
```

`SystemdClient` is the only place that touches `subprocess`; everything else depends on `SystemdClientProtocol`, which tests satisfy with `tests/fixtures/fake_systemd.py::FakeSystemdClient` — no test in this repo shells out to a real systemd.

**Important gotcha already fixed here, don't reintroduce it**: `systemctl show <unit> --property=A,B,C --value` does **not** return values in the requested order — systemd uses its own internal ordering. `get_unit_properties` deliberately omits `--value` and parses `Key=Value` lines instead. See `tests/unit/test_systemd_client.py::test_get_unit_properties_parses_key_value_lines_regardless_of_order`.

## Conventions

### `config/units.yaml` is the single source of truth for tracked units

**This supersedes an earlier version of this file, which said:** *"Do not refactor these functions to accept arrays or config files — keep it simple and explicit."* That was the right call for a 300-line bash script with no tests; it stopped being the right call once the unit list started drifting between this file, `README.md`, and the script itself (this file's own tracked-projects list had already gone stale relative to `README.md` before the rewrite). The config file is now the single source of truth read by both `lh-status` and the web dashboard — adding a unit is a data edit, not a code edit.

To add a new tracked process:
1. Add it under the right project in `config/units.yaml` (or add a new project block). Required fields: `unit`, `scope` (`system`|`user`), `label`. Optional: `note` (narrative text — e.g. "inactive (dead) is normal; runs only when triggered by timer"), `error_window` (override the auto-selected 24h/1h journal window).
2. Regenerate README's tables: `.venv/bin/lh-render-readme`.
3. Add any dependency/install-step prose (VPN, 1Password, AWS backend, install commands) to README.md's "Notes and install steps by project" section — that part is still hand-written and not generated.

A project with no locally-checkable unit (e.g. `versionpulse`, which runs on remote EC2) can have a `note` and no `units` — see the `versionpulse` entry in `config/units.yaml`.

### Oneshot semantics and error windows (core.py) — preserve exactly

- A oneshot mid-run (`ActiveState` is `active`/`activating`) must never surface `ExecMainStatus`/`InactiveEnterTimestamp` — systemd resets/stales those at the start of a run, so reporting them mid-run misreports the *previous* run's outcome as current.
- Journal error window: 24h for `Type=oneshot`, 1h otherwise, **regardless of scope** (`select_error_window` takes no scope parameter on purpose — that's what prevents the old bash bug, where the user-scope check hardcoded 1h for everything including user-scope oneshots, from being reintroduced). A per-unit `error_window` in the config always overrides this.
- Tally: a unit counts as FAILED if `ActiveState=failed` or `Result=failed`, or if it's not loaded on the machine at all. Recent journal errors are informational and don't affect the tally by themselves.

### Testing

Run before any change to `lh_dashboard/`: `.venv/bin/pytest tests/unit tests/functional`. Unit tests never touch real systemd (they use `FakeSystemdClient` or mock `subprocess.run` directly in `test_systemd_client.py`); functional tests exercise the real Flask app and CLI entry point against `FakeSystemdClient`, so they're safe to run anywhere, including CI, without depending on this machine's actual service state.

### Tracked projects

Processes come from sibling repos, enumerated in `config/units.yaml`:
- `../usb-encrypt` — backup-usb.timer, backup-usb.service, backup-poller.service; service skips silently if SSD not plugged in (ConditionPathExists on LUKS UUID); only activated by timer (WantedBy=timers.target)
- `../versionpulse` — note-only project (runs on remote EC2, nothing to check locally)
- `../opn-support` — opn-support-poller, gh-event-poller (system); opn-support-rtp-funding-watcher (user; rtp-funding-*.json and waiting-*.json drops → support.opn.inc cases); opn-support-dmarc-import.timer/service (user, every 30 min; DMARC reports from the inbox → ../dmarc-reports). sms_inbound_poller and the mailbox-import timer/service were retired 2026-09-09
- `../slack-notify` — slack-notify-poller, poller-healthcheck timer/service
- `../bank-core-config-tests` — rfp_poller
- `../issr-non-nativ` — issr-non-nativ.timer/service (user units, runs at 12:00/19:00/23:00 daily); requires VPN (DNS for walletapi.bridge.opnfi.net)
- `../rcnt-xfer-anlsys` — waiting-monitor timer/service
- `../grafana-logs` — grafana-logs-monitor.service
- `../analyzerouting` — analyzerouting-sync.timer/service (user units, runs Mondays 06:00); requires `bradley-wilkes-2024` OpenVPN (set to autoconnect, 60s pre-check in unit); requires 1Password desktop for credentials and failure notifications
- `../month-end` — month-end-extract, month-end-report, weekly-rtp-funding-report timer/service pairs; month-end-extract requires 1Password desktop for credentials
- `../onboard` — nabc-demo-buildup.timer/service (temporary, remove after the NABC demo)
- `../webhook` — webhook.service (user unit, Flask app on 127.0.0.1:8098); logs every POST /hook/<name> to logs/<name>.jsonl + logs/all.jsonl; verifies OPN's x-jwt-signature (HS256, per-name OPN_WEBHOOK_SECRET__<NAME> env var) when configured — never rejects unsigned/invalid requests; has its own `GET /health`
- this repo — `local-host-dashboard.service`, the dashboard's own web service

Full detail (purpose, dependencies, install steps) lives in `README.md`.

## Out of scope

This repo does not contain application code, deployment scripts, or configuration for the services it monitors (beyond their entries in `config/units.yaml`). Those live in their respective project repos. Unit auto-discovery (scanning `~/.config/systemd/user/` or `/etc/systemd/system/` for candidate units not yet in the config) is a deliberate non-goal for now — several tracked units' actual unit files live only in those locations with no copy in their source repo, and this machine runs many unrelated system timers that discovery would need to filter out.
