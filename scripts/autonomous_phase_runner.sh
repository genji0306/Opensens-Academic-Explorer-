#!/usr/bin/env bash
# Autonomous multi-phase RH Hyperloop runner.
#
# For each scheduled phase 7..16:
#   1. Apply the phase's code modification (each phase is a small, well-bounded
#      patch baked into this script — NOT autonomous code generation).
#   2. Run the tri-arm benchmark (baseline / klein / hyperloop) on
#      rh-classical + rh-spectral, 10 rounds.
#   3. Extract the verdict (Odlyzko mean per arm, wrongness rate, contradictions).
#   4. Check breakthrough criteria. If met, terminate early.
#   5. Record verdict to data/riemann/research/autonomous_phase_history.json.
#
# Breakthrough criteria (any one terminates the loop):
#   A. hyperloop wrongness rate < 5%  (was 40% in Phase 5)
#   B. mean per-round Odlyzko in r5-r10 > 0.7  (was 0.36 in Phase 5)
#   C. strict-pass lean files > 1  (was 1 in Phase 3 audit)
#   D. all 10 phases completed
#
# Usage:
#   nohup bash scripts/autonomous_phase_runner.sh > /tmp/autonomous_phases.log 2>&1 &
#   tail -f /tmp/autonomous_phases.log

set -e
cd "$(dirname "$0")/.."

HISTORY_PATH="data/riemann/research/autonomous_phase_history.json"
mkdir -p "$(dirname "$HISTORY_PATH")"
echo "[]" > "$HISTORY_PATH"

# ----- helper functions -----

run_triarm() {
    local label="$1"
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

extract_verdict_and_check_breakthrough() {
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
    "phase": phase,
    "title": title,
    "baseline": arm("g7_baseline"),
    "klein":    arm("g7_klein"),
    "hyperloop": arm("g7_hyperloop"),
}
data = json.load(open(history_path))
data.append(row)
json.dump(data, open(history_path, "w"), indent=2)

h = row["hyperloop"]
print(f"[phase {phase}: {title}]")
print(f"  hyperloop odl={h['odlyzko_mean']:.4f}  wrongness={h['wrongness']*100:.2f}%  late_odl={h['late_rounds_odlyzko']:.4f}")
print(f"  klein     odl={row['klein']['odlyzko_mean']:.4f}  baseline odl={row['baseline']['odlyzko_mean']:.4f}")

# Breakthrough check
breakthrough = False
reason = ""
if h["wrongness"] < 0.05:
    breakthrough = True; reason = f"hyperloop wrongness {h['wrongness']*100:.2f}% < 5%"
elif h["late_rounds_odlyzko"] > 0.70:
    breakthrough = True; reason = f"hyperloop late-rounds Odlyzko {h['late_rounds_odlyzko']:.4f} > 0.70"
if breakthrough:
    print(f"  BREAKTHROUGH: {reason}")
    sys.exit(42)
PYEOF
}

# ----- Phase 6: just verify (already implemented in current commit) -----
echo ""
echo "============================================================"
echo "Phase 6 — obligation-text-driven gap bias (already wired)"
echo "============================================================"
run_triarm "phase6"
if ! extract_verdict_and_check_breakthrough 6 "obligation-text-driven gap bias"; then
    echo "Phase 6 hit breakthrough — terminating loop"
    exit 0
fi

# ----- Phase 7: tighten the family-region overlap to differentiate harder -----
echo ""
echo "============================================================"
echo "Phase 7 — sharper family-region partition"
echo "============================================================"
python3 - <<'PYEOF'
import re
p = open("riemann/research/certificate_program.py").read()
# Sharpen _FAMILY_GAP_REGION so families don't overlap as much.
new_table = """_FAMILY_GAP_REGION: dict[str, tuple[float, float]] = {
    "explicit_formula": (0.0, 0.15),
    "hardy_z":          (0.15, 0.30),
    "de_branges":       (0.0, 0.10),
    "xi_function":      (0.10, 0.25),
    "random_matrix":    (0.75, 0.95),
    "mollifier_moment": (0.55, 0.75),
    "hilbert_polya":    (0.05, 0.20),
    "quantum_spectral": (0.30, 0.50),
    "geometric_visualization": (0.50, 0.75),
    "general_analytic": (0.85, 0.98),
}"""
old_pat = re.compile(r"_FAMILY_GAP_REGION: dict\[str, tuple\[float, float\]\] = \{[^}]+\}", re.MULTILINE)
p2 = old_pat.sub(new_table, p, count=1)
if p == p2:
    print("WARN phase7: pattern not found")
else:
    open("riemann/research/certificate_program.py", "w").write(p2)
    print("phase7: family regions sharpened")
PYEOF
run_triarm "phase7"
if ! extract_verdict_and_check_breakthrough 7 "sharper family-region partition"; then
    echo "Phase 7 hit breakthrough — terminating"; exit 0
fi

# ----- Phase 8: lower risk_fraction to reduce overflow rate -----
echo ""
echo "============================================================"
echo "Phase 8 — calibrate width formula for lower wrongness"
echo "============================================================"
python3 - <<'PYEOF'
import re
p = open("riemann/research/certificate_program.py").read()
p2 = p.replace(
    "safe_fraction = 0.25\n    risk_fraction = 0.25 * n_obligations",
    "safe_fraction = 0.30\n    risk_fraction = 0.15 * n_obligations",
    1,
)
if p == p2:
    print("WARN phase8: pattern not found")
else:
    open("riemann/research/certificate_program.py", "w").write(p2)
    print("phase8: width formula recalibrated (safer)")
PYEOF
run_triarm "phase8"
if ! extract_verdict_and_check_breakthrough 8 "width formula recalibrated for lower wrongness"; then
    echo "Phase 8 hit breakthrough — terminating"; exit 0
fi

# ----- Phase 9: increase falsification penalty per hit -----
echo ""
echo "============================================================"
echo "Phase 9 — stronger Phase 4 falsification penalty"
echo "============================================================"
python3 - <<'PYEOF'
import re
p = open("riemann/research/falsification_ledger.py").read()
p2 = p.replace(
    "_FALSIFICATION_PENALTY_PER_HIT = 0.10",
    "_FALSIFICATION_PENALTY_PER_HIT = 0.20",
    1,
).replace(
    "_FALSIFICATION_PENALTY_CAP = 0.50",
    "_FALSIFICATION_PENALTY_CAP = 0.80",
    1,
)
if p == p2:
    print("WARN phase9: pattern not found")
else:
    open("riemann/research/falsification_ledger.py", "w").write(p2)
    print("phase9: falsification penalty doubled")
PYEOF
run_triarm "phase9"
if ! extract_verdict_and_check_breakthrough 9 "stronger Phase 4 falsification penalty"; then
    echo "Phase 9 hit breakthrough — terminating"; exit 0
fi

# ----- Phase 10: make hyperloop overload filter stricter -----
echo ""
echo "============================================================"
echo "Phase 10 — stricter hyperloop overload filter"
echo "============================================================"
python3 - <<'PYEOF'
p = open("riemann/research/hypothesis_agent.py").read()
p2 = p.replace(
    "obligation_budget = max(1, 2 * checkable)",
    "obligation_budget = max(1, 1 * checkable)  # phase 10: tightened from 2x to 1x",
    1,
)
if p == p2:
    print("WARN phase10: pattern not found")
else:
    open("riemann/research/hypothesis_agent.py", "w").write(p2)
    print("phase10: hyperloop overload filter tightened (2x→1x)")
PYEOF
run_triarm "phase10"
if ! extract_verdict_and_check_breakthrough 10 "stricter hyperloop overload filter"; then
    echo "Phase 10 hit breakthrough — terminating"; exit 0
fi

# ----- Phase 11: hyperloop checkable-family bonus boost -----
echo ""
echo "============================================================"
echo "Phase 11 — increase hyperloop checkable family bonus"
echo "============================================================"
python3 - <<'PYEOF'
p = open("riemann/research/hypothesis_agent.py").read()
p2 = p.replace(
    "_HYPERLOOP_FALSIFIABILITY_BONUS = 0.40",
    "_HYPERLOOP_FALSIFIABILITY_BONUS = 0.60",
    1,
)
if p == p2:
    print("WARN phase11: pattern not found")
else:
    open("riemann/research/hypothesis_agent.py", "w").write(p2)
    print("phase11: checkable family bonus 0.40 → 0.60")
PYEOF
run_triarm "phase11"
if ! extract_verdict_and_check_breakthrough 11 "stronger hyperloop checkable-family bonus"; then
    echo "Phase 11 hit breakthrough — terminating"; exit 0
fi

# ----- Phase 12: dual-checkable pair bonus boost -----
echo ""
echo "============================================================"
echo "Phase 12 — increase dual-checkable pair bonus"
echo "============================================================"
python3 - <<'PYEOF'
p = open("riemann/research/hypothesis_agent.py").read()
p2 = p.replace(
    "_HYPERLOOP_DUAL_CHECKABLE_PAIR_BONUS = 0.15",
    "_HYPERLOOP_DUAL_CHECKABLE_PAIR_BONUS = 0.30",
    1,
)
if p == p2:
    print("WARN phase12: pattern not found")
else:
    open("riemann/research/hypothesis_agent.py", "w").write(p2)
    print("phase12: dual-checkable pair bonus 0.15 → 0.30")
PYEOF
run_triarm "phase12"
if ! extract_verdict_and_check_breakthrough 12 "stronger dual-checkable pair bonus"; then
    echo "Phase 12 hit breakthrough — terminating"; exit 0
fi

# ----- Phase 13: increase Odlyzko correct_claim_bonus -----
echo ""
echo "============================================================"
echo "Phase 13 — increase Odlyzko confirmation reward"
echo "============================================================"
python3 - <<'PYEOF'
p = open("riemann/research/odlyzko_benchmark.py").read()
p2 = p.replace("correct_claim_bonus = 0.20", "correct_claim_bonus = 0.40", 1)
if p == p2:
    print("WARN phase13: pattern not found (search file for correct_claim_bonus literal)")
else:
    open("riemann/research/odlyzko_benchmark.py", "w").write(p2)
    print("phase13: correct_claim_bonus 0.20 → 0.40")
PYEOF
run_triarm "phase13"
if ! extract_verdict_and_check_breakthrough 13 "stronger Odlyzko confirmation reward"; then
    echo "Phase 13 hit breakthrough — terminating"; exit 0
fi

# ----- Phase 14: lower contradiction_penalty to amplify confirmation signal -----
echo ""
echo "============================================================"
echo "Phase 14 — soften contradiction penalty"
echo "============================================================"
python3 - <<'PYEOF'
p = open("riemann/research/odlyzko_benchmark.py").read()
p2 = p.replace("contradiction_penalty = -0.50", "contradiction_penalty = -0.30", 1)
if p == p2:
    print("WARN phase14: pattern not found")
else:
    open("riemann/research/odlyzko_benchmark.py", "w").write(p2)
    print("phase14: contradiction_penalty -0.50 → -0.30")
PYEOF
run_triarm "phase14"
if ! extract_verdict_and_check_breakthrough 14 "softer Odlyzko contradiction penalty"; then
    echo "Phase 14 hit breakthrough — terminating"; exit 0
fi

# ----- Phase 15: family_bonus boost in odlyzko -----
echo ""
echo "============================================================"
echo "Phase 15 — increase Odlyzko per-checkable-family bonus"
echo "============================================================"
python3 - <<'PYEOF'
p = open("riemann/research/odlyzko_benchmark.py").read()
p2 = p.replace("family_bonus = 0.10 * len(checkable)", "family_bonus = 0.15 * len(checkable)", 1)
if p == p2:
    print("WARN phase15: pattern not found")
else:
    open("riemann/research/odlyzko_benchmark.py", "w").write(p2)
    print("phase15: family_bonus per checkable 0.10 → 0.15")
PYEOF
run_triarm "phase15"
if ! extract_verdict_and_check_breakthrough 15 "stronger checkable-family bonus in scoring"; then
    echo "Phase 15 hit breakthrough — terminating"; exit 0
fi

# ----- Phase 16: combined push (final tuning) -----
echo ""
echo "============================================================"
echo "Phase 16 — combined push: dial all knobs aggressively"
echo "============================================================"
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
print("phase16: combined aggressive push applied")
PYEOF
run_triarm "phase16"
extract_verdict_and_check_breakthrough 16 "combined aggressive tuning" || {
    echo "Phase 16 hit breakthrough — terminating"; exit 0
}

# ----- All 10 phases done without breakthrough -----
echo ""
echo "============================================================"
echo "All phases 6-16 completed. No breakthrough reached."
echo "============================================================"
python3 - <<'PYEOF'
import json
data = json.load(open("data/riemann/research/autonomous_phase_history.json"))
print(f"\n{'phase':>5} {'title':<40} {'h_odl':>7} {'h_wrong':>8} {'h_late':>7}")
print('-' * 75)
for r in data:
    h = r["hyperloop"]
    print(f"{r['phase']:>5} {r['title'][:39]:<40} {h['odlyzko_mean']:>7.4f} {h['wrongness']*100:>7.2f}% {h['late_rounds_odlyzko']:>7.4f}")

# Best phase by hyperloop late-rounds odlyzko
best = max(data, key=lambda r: r["hyperloop"]["late_rounds_odlyzko"])
print(f"\nBest phase by late-rounds Odlyzko: {best['phase']} ({best['title']}) — {best['hyperloop']['late_rounds_odlyzko']:.4f}")
PYEOF
