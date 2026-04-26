#!/usr/bin/env bash
# Phase 4 background learning loop.
#
# Runs the tri-arm hyperloop benchmark on rh-classical + rh-spectral seeds
# with the falsification ledger active. Each iteration:
#   1. Wipes prior g7_* campaign dirs and lean residue dirs
#   2. Runs baseline, klein, hyperloop campaigns sequentially (10 rounds each)
#   3. Extracts the per-round Odlyzko + contradiction stats
#   4. Appends a row to the verdict timeline
#
# The script terminates when EITHER:
#   (a) hyperloop's late-rounds (r6-r10) contradiction count drops to 0
#       in two consecutive iterations (the campaign learned), OR
#   (b) MAX_ITERATIONS reached (default 5)
#
# Usage:
#   nohup bash scripts/run_phase4_learning_loop.sh > /tmp/phase4_loop.log 2>&1 &
#   tail -f /tmp/phase4_loop.log

set -e

cd "$(dirname "$0")/.."

MAX_ITERATIONS="${MAX_ITERATIONS:-5}"
SEEDS=(--seed-pack rh-classical --seed-pack rh-spectral)
ROUNDS=10
HYPS=8
WORKERS=8
PATIENCE=12

VERDICT_PATH="data/riemann/research/phase4_learning_loop_verdict.json"
mkdir -p "$(dirname "$VERDICT_PATH")"
echo "[]" > "$VERDICT_PATH"

iteration=0
consecutive_zero_late=0
while [ "$iteration" -lt "$MAX_ITERATIONS" ]; do
    iteration=$((iteration + 1))
    echo ""
    echo "============================================================"
    echo "Iteration $iteration / $MAX_ITERATIONS  ($(date '+%Y-%m-%d %H:%M:%S'))"
    echo "============================================================"

    # Wipe prior state — this is what makes the falsification ledger truly fresh
    # per iteration. Inside one iteration the ledger accumulates within a campaign.
    rm -rf data/riemann/research/g7_baseline data/riemann/research/g7_klein data/riemann/research/g7_hyperloop
    rm -rf lean/RH/Lemmas/auto_g7_baseline lean/RH/Lemmas/auto_g7_klein lean/RH/Lemmas/auto_g7_hyperloop

    for mode in baseline klein hyperloop; do
        echo ""
        echo "---- arm: $mode ----"
        python3 -m riemann.research.cli \
            --campaign-id "g7_${mode}" \
            "${SEEDS[@]}" \
            --topology "$mode" \
            --max-rounds "$ROUNDS" \
            --max-hypotheses-per-round "$HYPS" \
            --max-worker-runs-per-round "$WORKERS" \
            --patience "$PATIENCE" 2>&1 | tail -3
    done

    # Record this iteration's verdict
    python3 scripts/extract_phase4_iteration_verdict.py \
        --iteration "$iteration" \
        --verdict-path "$VERDICT_PATH"

    # Check stop condition: hyperloop late-rounds contradictions = 0 twice in a row
    late_zero=$(python3 -c "
import json
data = json.load(open('$VERDICT_PATH'))
last = data[-1] if data else None
print(1 if last and last['hyperloop']['late_contradictions'] == 0 else 0)
")
    if [ "$late_zero" = "1" ]; then
        consecutive_zero_late=$((consecutive_zero_late + 1))
        if [ "$consecutive_zero_late" -ge 2 ]; then
            echo ""
            echo "TERMINATION: hyperloop late-rounds contradictions = 0 in 2 consecutive iterations"
            echo "Campaign has learned. Loop complete."
            break
        fi
    else
        consecutive_zero_late=0
    fi
done

echo ""
echo "============================================================"
echo "Loop complete after $iteration iteration(s)."
echo "Verdict: $VERDICT_PATH"
echo "============================================================"
python3 -c "
import json
data = json.load(open('$VERDICT_PATH'))
print(f'{\"iter\":>4} {\"baseline_odl\":>12} {\"klein_odl\":>10} {\"hyper_odl\":>10} {\"hyper_wrong\":>11} {\"hyper_late\":>10}')
for row in data:
    print(f'{row[\"iteration\"]:>4} {row[\"baseline\"][\"odlyzko_mean\"]:>12.4f} {row[\"klein\"][\"odlyzko_mean\"]:>10.4f} {row[\"hyperloop\"][\"odlyzko_mean\"]:>10.4f} {row[\"hyperloop\"][\"wrongness_pct\"]:>10.2f}% {row[\"hyperloop\"][\"late_contradictions\"]:>10}')
"
