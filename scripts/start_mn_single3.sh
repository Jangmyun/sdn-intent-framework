#!/usr/bin/env bash
set -Eeuo pipefail

cleanup() { sudo mn -c >/dev/null 2>&1 || true; }
command -v mn >/dev/null 2>&1 || { printf 'Mininet is not installed. Run ./scripts/installation/setup.sh first.\n' >&2; exit 1; }
trap cleanup EXIT INT TERM
cleanup

sudo mn \
  --topo single,3 \
  --controller remote,ip=127.0.0.1,port=6653 \
  --switch ovsk,protocols=OpenFlow13
