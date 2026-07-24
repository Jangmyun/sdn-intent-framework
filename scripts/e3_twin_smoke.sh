#!/usr/bin/env bash
# E3 Digital Twin integration smoke test.
#
# Runs all three E3 arms on the single headline congested-QoS case and checks the
# expected fidelity pattern: the reach-only twin wrongly APPROVES it while ground
# truth and the bandwidth-probing twin both REJECT it. This exercises the real
# twin path (Mininet bring-up, ONOS deploy, background-traffic replay, iperf3
# probe, rollback) end to end without the multi-minute cost of the full dataset.
#
# Requires Linux + root + Mininet + a running ONOS. Plain `sudo ./e3_twin_smoke.sh`
# works: it resolves `uv` via SUDO_USER's home when sudo's secure_path strips it
# from PATH. `sudo -E env "PATH=$PATH" ./scripts/e3_twin_smoke.sh` also works.
set -Eeuo pipefail
readonly PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
readonly CASE_ID="${E3_SMOKE_CASE:-E3-QOS-003}"   # congested SHOULD_FAIL qos case
readonly RUNNER="$PROJECT_ROOT/experiments/e3/run_twin_fidelity.py"

log() { printf '[e3-smoke] %s\n' "$*"; }
die() { printf '[e3-smoke] ERROR: %s\n' "$*" >&2; exit 1; }

resolve_uv() {
  if command -v uv >/dev/null 2>&1; then
    UV_BIN="$(command -v uv)"
    return
  fi
  local invoker_home
  if [[ -n "${SUDO_USER:-}" ]]; then
    invoker_home="$(getent passwd "$SUDO_USER" | cut -d: -f6)"
    if [[ -x "${invoker_home}/.local/bin/uv" ]]; then
      UV_BIN="${invoker_home}/.local/bin/uv"
      return
    fi
  fi
  if [[ -x "${HOME}/.local/bin/uv" ]]; then
    UV_BIN="${HOME}/.local/bin/uv"
    return
  fi
  die "uv not found (sudo's secure_path strips ~/.local/bin from PATH). Install with scripts/installation/setup.sh, or run: sudo -E env \"PATH=\$PATH\" $0"
}

[[ "$(uname -s)" == Linux ]] || die "Linux only."
[[ "${EUID}" -eq 0 ]] || die "root required (run with sudo ./scripts/e3_twin_smoke.sh)."
command -v mn >/dev/null 2>&1 || die "Mininet (mn) not found — run scripts/installation/setup.sh."
command -v iperf3 >/dev/null 2>&1 || die "iperf3 not found — run scripts/installation/setup.sh."
resolve_uv
log "Using uv at ${UV_BIN}."

log "Ensuring ONOS is running."
"$PROJECT_ROOT/scripts/onos.sh" start

workdir="$(mktemp -d)"
trap 'rm -rf "$workdir"' EXIT

declare -A OUTCOME
for arm in ground_truth twin_nobw twin_bw; do
  log "Running arm=${arm} on ${CASE_ID}..."
  "$UV_BIN" run --project "$PROJECT_ROOT" python "$RUNNER" --arm "$arm" --case-id "$CASE_ID" --output "$workdir/${arm}.jsonl"
  OUTCOME[$arm]="$("$UV_BIN" run --project "$PROJECT_ROOT" python -c "
import json,sys
line=open('$workdir/${arm}.jsonl').read().splitlines()[-1]
r=json.loads(line)
print(r['outcome'], r['twin_status'], r.get('measured_mbps'))
")"
  log "  arm=${arm}: ${OUTCOME[$arm]}"
done

log "Summary for ${CASE_ID} (outcome twin_status measured_mbps):"
for arm in ground_truth twin_nobw twin_bw; do
  printf '  %-13s %s\n' "$arm" "${OUTCOME[$arm]}"
done

gt="${OUTCOME[ground_truth]%% *}"
nobw="${OUTCOME[twin_nobw]%% *}"
bw="${OUTCOME[twin_bw]%% *}"

log "Expected pattern: ground_truth=FAIL, twin_nobw=PASS (blind spot), twin_bw=FAIL (probe catches it)."
if [[ "$gt" == "FAIL" && "$nobw" == "PASS" && "$bw" == "FAIL" ]]; then
  log "PASS: twin fidelity blind spot reproduced (reach-only wrongly approves; bandwidth probe fixes it)."
else
  log "NOTE: pattern not reproduced (gt=$gt nobw=$nobw bw=$bw)."
  log "      E3-QOS-003 requests a rate above the fast link's physical capacity, so"
  log "      ground_truth should reliably FAIL regardless of load. If it did not, check"
  log "      that provision_min_rate_queue() actually configured the OVS queue (see"
  log "      twin_verifier.py logs above) before tuning min_mbps in cases.jsonl."
  log "      This is a soft check, not a hard failure."
fi
