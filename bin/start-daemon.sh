#!/usr/bin/env bash
set -euo pipefail

display="${DISPLAY:-:99}"
Xvfb "$display" -screen 0 1920x1080x24 -nolisten tcp &
xvfb_pid=$!

cleanup() {
  trap - TERM INT EXIT
  kill -TERM "$xvfb_pid" 2>/dev/null || true
  wait "$xvfb_pid" 2>/dev/null || true
}
trap cleanup TERM INT EXIT

export DISPLAY="$display"
python -m openoutreach.cli rundaemon
