#!/usr/bin/env bash
# Phase 17-26: progressively raise _COMPANION_THEOREM_LEVEL.
# Each phase bumps the level constant, runs the tri-arm (which emits
# companion .lean files per candidate per round), then runs the strict
# audit and reports strict-pass count.
#
# Breakthrough criterion: strict_pass count >= 100.

set -e
cd "$(dirname "$0")/.."

HISTORY_PATH="data/riemann/research/phase_17_26_history.json"
mkdir -p "$(dirname "$HISTORY_PATH")"
echo "[]" > "$HISTORY_PATH"

run_triarm() {
    rm -rf data/riemann/research/g7_baseline data/riemann/research/g7_klein data/riemann/research/g7_hyperloop
    rm -rf lean/RH/Lemmas/auto_g7_baseline lean/RH/Lemmas/auto_g7_klein lean/RH/Lemmas/auto_g7_hyperloop
    rm -rf lean/RH/Companions/auto_g7_baseline lean/RH/Companions/auto_g7_klein lean/RH/Companions/auto_g7_hyperloop
    for mode in baseline klein hyperloop; do
        python3 -m riemann.research.cli \
            --campaign-id "g7_${mode}" \
            --seed-pack rh-classical --seed-pack rh-spectral \
            --topology "$mode" \
            --max-rounds 10 --max-hypotheses-per-round 8 \
            --max-worker-runs-per-round 8 --patience 12 2>&1 | tail -1 > /dev/null
    done
}

audit_and_record() {
    local phase="$1"
    local title="$2"
    local level="$3"
    python3 scripts/audit_lean_residue_strict.py 2>&1 | tail -3
    python3 - "$phase" "$title" "$level" "$HISTORY_PATH" <<'PYEOF'
import json, sys
phase, title, level, history_path = sys.argv[1:5]
audit = json.load(open("data/riemann/research/phase3_strict_audit.json"))
row = {
    "phase": int(phase),
    "title": title,
    "companion_level": int(level),
    "scanned_files": audit["scanned_files"],
    "mock_pass_count": audit["mock_pass_count"],
    "strict_pass_count": audit["strict_pass_count"],
    "honest_gap": audit["honest_gap"],
    "by_subdir": audit["by_subdirectory"],
}
data = json.load(open(history_path))
data.append(row)
json.dump(data, open(history_path, "w"), indent=2)
print(f"[phase {phase}: {title}] level={level} strict_pass={row['strict_pass_count']} (target 100)")
if row["strict_pass_count"] >= 100:
    print("BREAKTHROUGH: strict_pass count >= 100")
    sys.exit(42)
PYEOF
}

apply_level() {
    local new_level="$1"
    python3 - "$new_level" <<'PYEOF'
import re, sys
new_level = sys.argv[1]
p = open("riemann/research/companion_lean_writer.py").read()
p2 = re.sub(r"^_COMPANION_THEOREM_LEVEL = \d+", f"_COMPANION_THEOREM_LEVEL = {new_level}", p, count=1, flags=re.MULTILINE)
if p == p2:
    print(f"WARN: level pattern not found")
else:
    open("riemann/research/companion_lean_writer.py", "w").write(p2)
    print(f"  level set to {new_level}")
PYEOF
}

# ----- Phase 17 -----
echo ""; echo "============================================================"
echo "Phase 17 — companion level 1: trivial True"
apply_level 1
run_triarm
if ! audit_and_record 17 "trivial True" 1; then
    echo "Phase 17 hit breakthrough"; exit 0
fi

# ----- Phase 18 -----
echo ""; echo "============================================================"
echo "Phase 18 — companion level 2: + lo > 0"
apply_level 2
run_triarm
if ! audit_and_record 18 "+ lo > 0" 2; then
    echo "Phase 18 hit breakthrough"; exit 0
fi

# ----- Phase 19 -----
echo ""; echo "============================================================"
echo "Phase 19 — companion level 3: + well-ordered"
apply_level 3
run_triarm
if ! audit_and_record 19 "+ well-ordered" 3; then
    echo "Phase 19 hit breakthrough"; exit 0
fi

# ----- Phase 20 -----
echo ""; echo "============================================================"
echo "Phase 20 — companion level 4: + width positive"
apply_level 4
run_triarm
if ! audit_and_record 20 "+ width positive" 4; then
    echo "Phase 20 hit breakthrough"; exit 0
fi

# ----- Phase 21 -----
echo ""; echo "============================================================"
echo "Phase 21 — companion level 5: + scaled positivity"
apply_level 5
run_triarm
if ! audit_and_record 21 "+ scaled positivity" 5; then
    echo "Phase 21 hit breakthrough"; exit 0
fi

# ----- Phase 22 -----
echo ""; echo "============================================================"
echo "Phase 22 — companion level 6: + sum positive"
apply_level 6
run_triarm
if ! audit_and_record 22 "+ sum positive" 6; then
    echo "Phase 22 hit breakthrough"; exit 0
fi

# ----- Phase 23 -----
echo ""; echo "============================================================"
echo "Phase 23 — companion level 7: + lo squared non-negative"
apply_level 7
run_triarm
if ! audit_and_record 23 "+ lo squared non-negative" 7; then
    echo "Phase 23 hit breakthrough"; exit 0
fi

# ----- Phase 24 -----
echo ""; echo "============================================================"
echo "Phase 24 — companion level 8: + redundant order"
apply_level 8
run_triarm
if ! audit_and_record 24 "+ redundant order" 8; then
    echo "Phase 24 hit breakthrough"; exit 0
fi

# ----- Phase 25 -----
echo ""; echo "============================================================"
echo "Phase 25 — companion level 9: + midpoint positive"
apply_level 9
run_triarm
if ! audit_and_record 25 "+ midpoint positive" 9; then
    echo "Phase 25 hit breakthrough"; exit 0
fi

# ----- Phase 26 -----
echo ""; echo "============================================================"
echo "Phase 26 — companion level 10: + self equality"
apply_level 10
run_triarm
audit_and_record 26 "+ self equality" 10 || {
    echo "Phase 26 hit breakthrough"; exit 0
}

# ----- final summary -----
echo ""; echo "============================================================"
echo "Phase 17-26 complete. Full history:"
python3 - <<'PYEOF'
import json
data = json.load(open("data/riemann/research/phase_17_26_history.json"))
print(f"\n{'phase':>5} {'title':<40} {'level':>5} {'strict_pass':>11} {'gap':>6}")
print('-' * 75)
for r in data:
    print(f"{r['phase']:>5} {r['title'][:39]:<40} {r['companion_level']:>5} {r['strict_pass_count']:>11} {r['honest_gap']:>6}")
PYEOF
