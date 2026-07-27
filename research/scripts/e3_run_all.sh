#!/usr/bin/env bash
# Run the full E3 experiment (all three arms + scoring) and tee everything to a
# log file, so the run can be inspected afterwards without copying terminal output.
#
# Requires Linux + root + Mininet + a running ONOS. Run as:
#   sudo ./scripts/e3_run_all.sh
#
# Output:
#   logs/e3/{ground_truth,twin_nobw,twin_bw}.jsonl   per-arm results
#   logs/e3/e3_fidelity.json                          aggregate fidelity report
#   logs/e3/run.log                                   full transcript of this run
#
# By default previous results are cleared first (a stale JSONL would otherwise be
# resumed and silently mix results from different code revisions). Pass --resume
# to keep them and continue an interrupted run instead.
set -Eeuo pipefail
readonly PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
readonly OUT_DIR="${PROJECT_ROOT}/logs/e3"
readonly RUN_LOG="${OUT_DIR}/run.log"
readonly RUNNER="${PROJECT_ROOT}/experiments/e3/run_twin_fidelity.py"
readonly SCORER="${PROJECT_ROOT}/experiments/e3/score.py"

RESUME=0
[[ "${1:-}" == --resume ]] && RESUME=1

log() { printf '[e3-run] %s\n' "$*"; }
die() { printf '[e3-run] ERROR: %s\n' "$*" >&2; exit 1; }

resolve_uv() {
  if command -v uv >/dev/null 2>&1; then UV_BIN="$(command -v uv)"; return; fi
  local invoker_home
  if [[ -n "${SUDO_USER:-}" ]]; then
    invoker_home="$(getent passwd "$SUDO_USER" | cut -d: -f6)"
    [[ -x "${invoker_home}/.local/bin/uv" ]] && { UV_BIN="${invoker_home}/.local/bin/uv"; return; }
  fi
  [[ -x "${HOME}/.local/bin/uv" ]] && { UV_BIN="${HOME}/.local/bin/uv"; return; }
  die "uv not found. Run: sudo -E env \"PATH=\$PATH\" $0"
}

[[ "$(uname -s)" == Linux ]] || die "Linux only."
[[ "${EUID}" -eq 0 ]] || die "root required (run with sudo ./scripts/e3_run_all.sh)."
command -v mn >/dev/null 2>&1 || die "Mininet (mn) not found."
command -v iperf3 >/dev/null 2>&1 || die "iperf3 not found."
resolve_uv

mkdir -p "$OUT_DIR"

# Everything below is duplicated to RUN_LOG. PYTHONUNBUFFERED keeps the twin's
# progress lines in true chronological order in the file.
export PYTHONUNBUFFERED=1
exec > >(tee "$RUN_LOG") 2>&1

log "started $(date --iso-8601=seconds)"
log "uv: ${UV_BIN}"
log "git: $(git -C "$PROJECT_ROOT" rev-parse --short HEAD 2>/dev/null || echo unknown)$(git -C "$PROJECT_ROOT" diff --quiet 2>/dev/null || echo '-dirty')"

if [[ $RESUME -eq 0 ]]; then
  log "clearing previous results (pass --resume to keep them)"
  rm -f "$OUT_DIR"/ground_truth.jsonl "$OUT_DIR"/twin_nobw.jsonl \
        "$OUT_DIR"/twin_bw.jsonl "$OUT_DIR"/e3_fidelity.json
else
  log "resuming: keeping existing per-arm results"
fi

log "ensuring ONOS is running"
"$PROJECT_ROOT/scripts/onos.sh" start

for arm in ground_truth twin_nobw twin_bw; do
  log "=== arm: ${arm} ==="
  "$UV_BIN" run --project "$PROJECT_ROOT" python "$RUNNER" \
    --arm "$arm" --output "${OUT_DIR}/${arm}.jsonl"
done

log "=== scoring ==="
"$UV_BIN" run --project "$PROJECT_ROOT" python "$SCORER" \
  --output "${OUT_DIR}/e3_fidelity.json" \
  "${OUT_DIR}/ground_truth.jsonl" "${OUT_DIR}/twin_nobw.jsonl" "${OUT_DIR}/twin_bw.jsonl"

log "=== per-case summary ==="
"$UV_BIN" run --project "$PROJECT_ROOT" python - "$PROJECT_ROOT" <<'PY'
import json, sys
from pathlib import Path
root = Path(sys.argv[1])
arms = {a: {json.loads(l)["case_id"]: json.loads(l)
            for l in (root / f"logs/e3/{a}.jsonl").read_text().splitlines() if l.strip()}
        for a in ("ground_truth", "twin_nobw", "twin_bw")}
cases = [json.loads(l) for l in (root / "experiments/e3/data/cases.jsonl").read_text().splitlines() if l.strip()]
print(f"{'case':13s} {'exp':5s} {'gt':5s} {'nobw':5s} {'bw':5s} {'gt_mbps':>8s} {'bw_mbps':>8s}")
print("-" * 62)
for c in cases:
    cid = c["id"]
    exp = "PASS" if c["expected_ground_truth"] == "SHOULD_PASS" else "FAIL"
    gt, nb, bw = (arms[a][cid] for a in ("ground_truth", "twin_nobw", "twin_bw"))
    flag = "  <-- gt mismatch" if exp != gt["outcome"] else ""
    fmt = lambda v: "-" if v is None else f"{v:.2f}"
    print(f"{cid:13s} {exp:5s} {gt['outcome']:5s} {nb['outcome']:5s} {bw['outcome']:5s} "
          f"{fmt(gt.get('measured_mbps')):>8s} {fmt(bw.get('measured_mbps')):>8s}{flag}")

report = json.loads((root / "logs/e3/e3_fidelity.json").read_text())
f = report["fidelity"]
print("\nlabel mismatch:", report["ground_truth_label_mismatch"])
for arm in ("twin_nobw", "twin_bw"):
    o = f[arm]["overall"]; q = f[arm]["by_category"]["qos"]
    print(f"{arm:10s} overall acc={o['accuracy']:.3f} fpr={o['fpr']}   qos acc={q['accuracy']:.3f} fpr={q['fpr']}")
print("delta:", f["overall_delta"], "| qos:", f["by_category_delta"]["qos"])

# Surface any check that failed, so a flaky reach probe is visible in the log.
print("\nfailed checks:")
any_failed = False
for a, by_id in arms.items():
    for cid, r in by_id.items():
        bad = [k for k, v in r["checks"].items() if not v]
        if bad:
            any_failed = True
            msgs = {k: v for k, v in r["evidence"].items() if "msg" in k or "mbps" in k}
            print(f"  {a:13s} {cid:13s} failed={bad} {msgs}")
if not any_failed:
    print("  (none)")
PY

# Hand the artifacts back to the invoking user so a later non-sudo run can
# overwrite them (a root-owned e3_fidelity.json previously broke re-scoring).
if [[ -n "${SUDO_USER:-}" ]]; then
  chown -R "$(id -u "$SUDO_USER")":"$(id -g "$SUDO_USER")" "$OUT_DIR"
fi

log "done $(date --iso-8601=seconds)"
log "transcript: ${RUN_LOG}"
