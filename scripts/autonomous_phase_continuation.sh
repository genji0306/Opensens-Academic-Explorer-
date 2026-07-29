#!/usr/bin/env bash
# Continuation: run Phase 9-16 on top of the Phase 8 breakthrough state.
# Does NOT terminate on breakthrough — runs all phases through 16 and reports each.
# This explores whether further tuning RAISES or LOWERS the breakthrough metrics.

set -e
cd "$(dirname "$0")/.."

HISTORY_PATH="data/riemann/research/autonomous_phase_history.json"

run_triarm() {
    rm -rf data/riemann/research/g7_baseline data/riemann/research/g7_klein data/riemann/research/g7_hyperloop
    rm -rf lean/RH/Lemmas/auto_g7_baseline lean/RH/Lemmas/auto_g7_klein lean/RH/Lemmas/auto_g7_hyperloop
    for mode in baseline klein hyperloop; do
        python3 -m riemann.research.cli \
            --campaign-id "g7_${mode}" \
            --seed-pack rh-classical --seed-pack rh-spectral \
            --topology "$mode" \
            --max-rounds 10 --max-hypotheses-per-round 8 \
            --max-worker-runs-per-round 8 --patience 12 2>&1 | tail -1 > /dev/null
    done
}

extract_verdict() {
    local phase="$1"
    local title="$2"
    python3 - "$phase" "$title" "$HISTORY_PATH" <<'PYEOF'
import json, sys
phase, title, history_path = sys.argv[1:4]

def arm(cid):
    s = json.load(open(f"data/riemann/research/{cid}/summary.json"))
    es = s.get("external_eval_summary", {})
    log = s.get("external_eval_log", [])
    contradicted = sum(e.get("odlyzko_details", {}).get("contradicted_count", 0) for e in log)
    n = s.get("total_hypotheses", 0)
    late_avg = sum(e["odlyzko_score"] for e in log[5:]) / max(1, len(log[5:]))
    return {
        "internal": s.get("best_score"),
        "odlyzko_mean": es.get("mean_odlyzko_score"),
        "total_hyps": n,
        "contradicted": contradicted,
        "wrongness": (contradicted / n) if n else 0,
        "late_rounds_odlyzko": late_avg,
        "per_round_odlyzko": [e.get("odlyzko_score", 0) for e in log],
    }

row = {
    "phase": int(phase),
    "title": title,
    "baseline": arm("g7_baseline"),
    "klein":    arm("g7_klein"),
    "hyperloop": arm("g7_hyperloop"),
}
data = json.load(open(history_path))
data.append(row)
json.dump(data, open(history_path, "w"), indent=2)

h = row["hyperloop"]
flag = ""
if h["wrongness"] < 0.05:
    flag += " [low_wrongness]"
if h["late_rounds_odlyzko"] > 0.70:
    flag += " [HIGH_LATE_ODL!]"
print(f"[phase {phase}: {title}]")
print(f"  hyperloop odl={h['odlyzko_mean']:.4f}  wrongness={h['wrongness']*100:.2f}%  late_odl={h['late_rounds_odlyzko']:.4f}{flag}")
print(f"  klein     odl={row['klein']['odlyzko_mean']:.4f}  baseline odl={row['baseline']['odlyzko_mean']:.4f}")
PYEOF
}

# ----- Phase 9: stronger falsification penalty -----
echo ""; echo "============================================================"; echo "Phase 9 — stronger Phase 4 falsification penalty"
python3 - <<'PYEOF'
p = open("riemann/research/falsification_ledger.py").read()
p2 = p.replace("_FALSIFICATION_PENALTY_PER_HIT = 0.10", "_FALSIFICATION_PENALTY_PER_HIT = 0.20", 1)
p2 = p2.replace("_FALSIFICATION_PENALTY_CAP = 0.50", "_FALSIFICATION_PENALTY_CAP = 0.80", 1)
open("riemann/research/falsification_ledger.py", "w").write(p2)
print("phase9: applied")
PYEOF
run_triarm; extract_verdict 9 "stronger Phase 4 falsification penalty"

# ----- Phase 10: stricter overload filter -----
echo ""; echo "============================================================"; echo "Phase 10 — stricter hyperloop overload filter"
python3 - <<'PYEOF'
p = open("riemann/research/hypothesis_agent.py").read()
p2 = p.replace("obligation_budget = max(1, 2 * checkable)", "obligation_budget = max(1, 1 * checkable)", 1)
open("riemann/research/hypothesis_agent.py", "w").write(p2)
print("phase10: applied")
PYEOF
run_triarm; extract_verdict 10 "stricter hyperloop overload filter (2x→1x)"

# ----- Phase 11: bigger checkable family bonus -----
echo ""; echo "============================================================"; echo "Phase 11 — bigger checkable family bonus"
python3 - <<'PYEOF'
p = open("riemann/research/hypothesis_agent.py").read()
p2 = p.replace("_HYPERLOOP_FALSIFIABILITY_BONUS = 0.40", "_HYPERLOOP_FALSIFIABILITY_BONUS = 0.60", 1)
open("riemann/research/hypothesis_agent.py", "w").write(p2)
print("phase11: applied")
PYEOF
run_triarm; extract_verdict 11 "checkable family bonus 0.40 → 0.60"

# ----- Phase 12: bigger dual-checkable pair bonus -----
echo ""; echo "============================================================"; echo "Phase 12 — bigger dual-checkable pair bonus"
python3 - <<'PYEOF'
p = open("riemann/research/hypothesis_agent.py").read()
p2 = p.replace("_HYPERLOOP_DUAL_CHECKABLE_PAIR_BONUS = 0.15", "_HYPERLOOP_DUAL_CHECKABLE_PAIR_BONUS = 0.30", 1)
open("riemann/research/hypothesis_agent.py", "w").write(p2)
print("phase12: applied")
PYEOF
run_triarm; extract_verdict 12 "dual-checkable pair bonus 0.15 → 0.30"

# ----- Phase 13: bigger correct_claim_bonus -----
echo ""; echo "============================================================"; echo "Phase 13 — bigger Odlyzko confirmation reward"
python3 - <<'PYEOF'
p = open("riemann/research/odlyzko_benchmark.py").read()
p2 = p.replace("correct_claim_bonus = 0.20", "correct_claim_bonus = 0.40", 1)
open("riemann/research/odlyzko_benchmark.py", "w").write(p2)
print("phase13: applied")
PYEOF
run_triarm; extract_verdict 13 "Odlyzko confirmation reward 0.20 → 0.40"

# ----- Phase 14: softer contradiction penalty -----
echo ""; echo "============================================================"; echo "Phase 14 — softer Odlyzko contradiction penalty"
python3 - <<'PYEOF'
p = open("riemann/research/odlyzko_benchmark.py").read()
p2 = p.replace("contradiction_penalty = -0.50", "contradiction_penalty = -0.30", 1)
open("riemann/research/odlyzko_benchmark.py", "w").write(p2)
print("phase14: applied")
PYEOF
run_triarm; extract_verdict 14 "Odlyzko contradiction penalty -0.50 → -0.30"

# ----- Phase 15: bigger family bonus -----
echo ""; echo "============================================================"; echo "Phase 15 — bigger checkable-family bonus in scoring"
python3 - <<'PYEOF'
p = open("riemann/research/odlyzko_benchmark.py").read()
p2 = p.replace("family_bonus = 0.10 * len(checkable)", "family_bonus = 0.15 * len(checkable)", 1)
open("riemann/research/odlyzko_benchmark.py", "w").write(p2)
print("phase15: applied")
PYEOF
run_triarm; extract_verdict 15 "Odlyzko family bonus 0.10 → 0.15"

# ----- Phase 16: combined aggressive push -----
echo ""; echo "============================================================"; echo "Phase 16 — combined aggressive push"
python3 - <<'PYEOF'
p1 = open("riemann/research/odlyzko_benchmark.py").read()
p1 = p1.replace("correct_claim_bonus = 0.40", "correct_claim_bonus = 0.50")
open("riemann/research/odlyzko_benchmark.py", "w").write(p1)
p2 = open("riemann/research/hypothesis_agent.py").read()
p2 = p2.replace("_HYPERLOOP_FALSIFIABILITY_BONUS = 0.60", "_HYPERLOOP_FALSIFIABILITY_BONUS = 0.80")
open("riemann/research/hypothesis_agent.py", "w").write(p2)
p3 = open("riemann/research/falsification_ledger.py").read()
p3 = p3.replace("_FALSIFICATION_PENALTY_PER_HIT = 0.20", "_FALSIFICATION_PENALTY_PER_HIT = 0.30")
open("riemann/research/falsification_ledger.py", "w").write(p3)
print("phase16: applied")
PYEOF
run_triarm; extract_verdict 16 "combined aggressive push"

# ----- Final summary -----
echo ""; echo "============================================================"; echo "Phase 9-16 complete. Full history:"
python3 - <<'PYEOF'
import json
data = json.load(open("data/riemann/research/autonomous_phase_history.json"))
print(f"\n{'phase':>5} {'title':<45} {'h_odl':>7} {'h_wrong':>8} {'h_late':>7}")
print('-' * 80)
for r in data:
    h = r["hyperloop"]
    print(f"{r['phase']:>5} {r['title'][:44]:<45} {h['odlyzko_mean']:>7.4f} {h['wrongness']*100:>7.2f}% {h['late_rounds_odlyzko']:>7.4f}")

best_late = max(data, key=lambda r: r["hyperloop"]["late_rounds_odlyzko"])
best_odl  = max(data, key=lambda r: r["hyperloop"]["odlyzko_mean"])
low_wrong = min(data, key=lambda r: r["hyperloop"]["wrongness"])
print(f"\nBest hyperloop late-rounds Odlyzko: phase {best_late['phase']} = {best_late['hyperloop']['late_rounds_odlyzko']:.4f}")
print(f"Best hyperloop overall Odlyzko:     phase {best_odl['phase']} = {best_odl['hyperloop']['odlyzko_mean']:.4f}")
print(f"Lowest hyperloop wrongness:         phase {low_wrong['phase']} = {low_wrong['hyperloop']['wrongness']*100:.2f}%")
PYEOF
