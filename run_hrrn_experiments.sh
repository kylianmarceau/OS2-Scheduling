#!/bin/bash
set -euo pipefail

patron_counts=(10 20 30 40 50 60 70 80 90 100)
seeds=(42 123 456 789 1337 2000)
switch_time=5
scheduler=4
output_dir="hrrn_results"

make compile
rm -rf "$output_dir"
mkdir -p "$output_dir"

total_runs=$((${#patron_counts[@]} * ${#seeds[@]}))
run_number=0

for patron_count in "${patron_counts[@]}"; do
    for seed in "${seeds[@]}"; do
        run_number=$((run_number + 1))
        echo "[$run_number/$total_runs] patrons=$patron_count scheduler=HRRN switch_time=$switch_time seed=$seed"
        java -Dresults.dir="$output_dir" -cp bin barScheduling.SchedulingSimulation "$patron_count" "$scheduler" "$switch_time" "$seed"
    done
done

echo "HRRN experiment runs complete. CSV file is in $output_dir/."
