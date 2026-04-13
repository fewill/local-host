#!/usr/bin/env bash
# status.sh — machine process status dashboard

set -euo pipefail

# ── helpers ──────────────────────────────────────────────────────────────────

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
CYAN='\033[0;36m'
BOLD='\033[1m'
DIM='\033[2m'
RESET='\033[0m'

print_header() {
    echo
    echo -e "${BOLD}${CYAN}══════════════════════════════════════════════${RESET}"
    echo -e "${BOLD}${CYAN}  Machine Process Status — $(date '+%a %b %-d %H:%M %Z')${RESET}"
    echo -e "${BOLD}${CYAN}══════════════════════════════════════════════${RESET}"
}

# Print a section for one cron job.
# Usage: print_cron <schedule> <display-label> <log-file> [<extra-note>]
print_cron() {
    local schedule="$1"
    local label="$2"
    local logfile="$3"
    local extra="${4:-}"

    echo
    echo -e "${BOLD}▸ ${label}${RESET}${extra:+  ${DIM}(${extra})${RESET}}"
    printf "  %-14s %s\n" "Schedule:" "$schedule"

    if [[ -f "$logfile" ]]; then
        local last_run
        last_run=$(date -r "$logfile" '+%a %Y-%m-%d %H:%M:%S %Z' 2>/dev/null || true)
        [[ -n "$last_run" ]] && printf "  %-14s %s\n" "Log updated:" "$last_run"

        # Only show errors from the most recent run (lines dated the same day as the log mtime)
        local run_date recent_errors
        run_date=$(date -r "$logfile" '+%Y-%m-%d' 2>/dev/null || true)
        recent_errors=$(grep "^$run_date" "$logfile" 2>/dev/null | grep -i "error\|exception\|traceback" | tail -3 || true)
        if [[ -n "$recent_errors" ]]; then
            echo -e "  ${RED}Recent errors (last run):${RESET}"
            while IFS= read -r line; do
                echo -e "    ${DIM}${line}${RESET}"
            done <<< "$recent_errors"
        fi
    else
        echo -e "  ${DIM}Log file not found: ${logfile}${RESET}"
    fi
}

# Print a section for one systemd user unit (--user scope).
# Usage: print_user_unit <unit-name> <display-label> [<extra-note>]
print_user_unit() {
    local unit="$1"
    local label="$2"
    local extra="${3:-}"

    echo
    echo -e "${BOLD}▸ ${label}${RESET}${extra:+  ${DIM}(${extra})${RESET}}"

    local active sub loaded result
    active=$(systemctl --user show "$unit" --property=ActiveState --value 2>/dev/null || echo "unknown")
    sub=$(systemctl --user show "$unit" --property=SubState --value 2>/dev/null || echo "unknown")
    loaded=$(systemctl --user show "$unit" --property=LoadState --value 2>/dev/null || echo "unknown")
    result=$(systemctl --user show "$unit" --property=Result --value 2>/dev/null || echo "")

    local state_color="$RESET"
    case "$active" in
        active)   state_color="$GREEN" ;;
        failed)   state_color="$RED" ;;
        inactive) state_color="$YELLOW" ;;
    esac

    printf "  %-14s %b%s (%s)%b\n" "State:" "$state_color" "$active" "$sub" "$RESET"

    if [[ "$loaded" != "loaded" ]]; then
        echo -e "  ${RED}Unit not found / not loaded${RESET}"
        return
    fi

    local exec_main_exit active_enter
    exec_main_exit=$(systemctl --user show "$unit" --property=ExecMainExitTimestamp --value 2>/dev/null || true)
    active_enter=$(systemctl --user show "$unit" --property=ActiveEnterTimestamp --value 2>/dev/null || true)

    if [[ -n "$exec_main_exit" && "$exec_main_exit" != "n/a" && "$exec_main_exit" != "0" ]]; then
        printf "  %-14s %s\n" "Last ran:" "$exec_main_exit"
    elif [[ -n "$active_enter" && "$active_enter" != "n/a" && "$active_enter" != "0" ]]; then
        printf "  %-14s %s\n" "Active since:" "$active_enter"
    fi

    if [[ -n "$result" && "$result" != "success" && "$result" != "" ]]; then
        echo -e "  ${RED}Result: ${result}${RESET}"
    fi

    local recent_errors
    recent_errors=$(journalctl --user -u "$unit" --since "1 hour ago" -p err -o cat --no-pager 2>/dev/null \
        | tail -3 || true)
    if [[ -n "$recent_errors" ]]; then
        echo -e "  ${RED}Recent errors (last hour):${RESET}"
        while IFS= read -r line; do
            echo -e "    ${DIM}${line}${RESET}"
        done <<< "$recent_errors"
    fi
}

# Print a section for one systemd unit.
# Usage: print_unit <unit-name> <display-label> [<extra-note>]
print_unit() {
    local unit="$1"
    local label="$2"
    local extra="${3:-}"

    echo
    echo -e "${BOLD}▸ ${label}${RESET}${extra:+  ${DIM}(${extra})${RESET}}"

    # Pull the fields we care about in one pass
    local active sub loaded last_trigger next_trigger result
    active=$(systemctl show "$unit" --property=ActiveState --value 2>/dev/null || echo "unknown")
    sub=$(systemctl show "$unit" --property=SubState --value 2>/dev/null || echo "unknown")
    loaded=$(systemctl show "$unit" --property=LoadState --value 2>/dev/null || echo "unknown")
    result=$(systemctl show "$unit" --property=Result --value 2>/dev/null || echo "")

    # Colour the state
    local state_color="$RESET"
    case "$active" in
        active)   state_color="$GREEN" ;;
        failed)   state_color="$RED" ;;
        inactive) state_color="$YELLOW" ;;
    esac

    printf "  %-14s %b%s (%s)%b\n" "State:" "$state_color" "$active" "$sub" "$RESET"

    if [[ "$loaded" != "loaded" ]]; then
        echo -e "  ${RED}Unit not found / not loaded${RESET}"
        return
    fi

    # Last activation time (services)
    local exec_main_exit
    exec_main_exit=$(systemctl show "$unit" --property=ExecMainExitTimestamp --value 2>/dev/null || true)
    local active_enter
    active_enter=$(systemctl show "$unit" --property=ActiveEnterTimestamp --value 2>/dev/null || true)

    if [[ -n "$exec_main_exit" && "$exec_main_exit" != "n/a" && "$exec_main_exit" != "0" ]]; then
        printf "  %-14s %s\n" "Last ran:" "$exec_main_exit"
    elif [[ -n "$active_enter" && "$active_enter" != "n/a" && "$active_enter" != "0" ]]; then
        printf "  %-14s %s\n" "Active since:" "$active_enter"
    fi

    # Timer-specific: next trigger
    if systemctl show "$unit" --property=NextElapseUSecRealtime --value &>/dev/null; then
        next_trigger=$(systemctl list-timers "$unit" --no-legend 2>/dev/null \
            | awk '{print $1, $2, $3}' | head -1 || true)
        if [[ -n "$next_trigger" ]]; then
            printf "  %-14s %s\n" "Next run:" "$next_trigger"
        fi
    fi

    # Result code for oneshot services
    if [[ -n "$result" && "$result" != "success" && "$result" != "" ]]; then
        echo -e "  ${RED}Result: ${result}${RESET}"
    fi

    # Last few journal lines (errors preferred, else tail)
    local recent_errors
    recent_errors=$(journalctl -u "$unit" --since "1 hour ago" -p err -o cat --no-pager 2>/dev/null \
        | tail -3 || true)
    if [[ -n "$recent_errors" ]]; then
        echo -e "  ${RED}Recent errors (last hour):${RESET}"
        while IFS= read -r line; do
            echo -e "    ${DIM}${line}${RESET}"
        done <<< "$recent_errors"
    fi
}

# ── main ─────────────────────────────────────────────────────────────────────

print_header

echo -e "\n${BOLD}usb-encrypt${RESET}"
print_unit "backup-usb.timer"      "Backup Timer"   "triggers backup-usb.service daily"
print_unit "backup-usb.service"    "Backup Service" "encrypted USB + S3 sync (oneshot) — inactive (dead) is normal; runs only when triggered by timer"
print_unit "backup-poller.service" "Backup Poller"  "SQS poller — always running"

echo -e "\n${BOLD}versionpulse${RESET}"
print_unit      "versionpulse.service"            "Versionpulse"        "version monitor — always running"
print_user_unit "versionpulse-autocommit.service" "Versionpulse Commit" "watches log file, auto-commits/pushes to GitHub — always running"

echo -e "\n${BOLD}opn-support${RESET}"
print_unit "opn-support-poller.service" "Support Poller" "Slack #ops-support channel monitor — always running"

echo -e "\n${BOLD}analyzerouting${RESET}"
print_cron "Mondays at 06:00" "Routing Table Fetch" "/home/fewill/code/analyzerouting/logs/fetch_cron.log" "fetches FedNow/RTP/ACH routing tables weekly"

echo
echo -e "${DIM}── Run 'journalctl -u <unit> -f' to tail live logs ──────────────────────${RESET}"
echo
