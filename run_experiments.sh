#!/bin/bash
set -euo pipefail

patron_counts=(10 20 30 40 50 60 70 80 90 100)
schedulers=(0 1 2 3)
seeds=(42 123 456 789 1337 2000)
switch_time=5

make compile
rm -rf results
mkdir -p results

total_runs=$((${#patron_counts[@]} * ${#schedulers[@]} * ${#seeds[@]}))
run_number=0

for patron_count in "${patron_counts[@]}"; do
    for seed in "${seeds[@]}"; do
        for scheduler in "${schedulers[@]}"; do
            run_number=$((run_number + 1))
            echo "[$run_number/$total_runs] patrons=$patron_count scheduler=$scheduler switch_time=$switch_time seed=$seed"
            java -cp bin barScheduling.SchedulingSimulation "$patron_count" "$scheduler" "$switch_time" "$seed"
        done
    done
done

echo "Experiment runs complete. CSV files are in results/."
