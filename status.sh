#!/usr/bin/env bash
# status.sh — thin wrapper kept for the existing `lh-status` alias and the
# local-host-status Claude Code skill, both of which call this file directly.
# The real implementation lives in lh_dashboard/ (see cli.py); the terminal
# rendering behavior this used to implement in bash is unchanged.
exec /home/fewill/code/local-host/.venv/bin/lh-status "$@"
