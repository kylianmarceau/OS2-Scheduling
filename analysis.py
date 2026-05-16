#!/usr/bin/env python3
"""
Analyse Allegra the Barman scheduling experiment CSV files.

Input:
    results/*.csv

Outputs:
    analysis_results/run_summary.csv
    analysis_results/patron_summary.csv
    analysis_results/scheduler_summary.csv
"""

import argparse
import csv
import glob
import statistics
from collections import defaultdict
from pathlib import Path


EXPECTED_COLUMNS = [
    "runId",
    "scheduler",
    "noPatrons",
    "switchTime",
    "seed",
    "patronID",
    "drinkName",
    "executionTime",
    "arrivalTime",
    "serviceStartTime",
    "completionTime",
    "waitingTime",
    "responseTime",
    "turnaroundTime",
    "queueLevel",
]

INTEGER_COLUMNS = {
    "noPatrons",
    "switchTime",
    "seed",
    "patronID",
    "executionTime",
    "arrivalTime",
    "serviceStartTime",
    "completionTime",
    "waitingTime",
    "responseTime",
    "turnaroundTime",
    "queueLevel",
}

SCHEDULER_ORDER = {
    "FCFS": 0,
    "SJF": 1,
    "PRIORITY": 2,
    "MLFQ": 3,
}


def mean(values):
    return statistics.mean(values) if values else 0.0


def median(values):
    return statistics.median(values) if values else 0.0


def stdev(values):
    return statistics.stdev(values) if len(values) > 1 else 0.0


def percentile(values, percent):
    """Return a linearly interpolated percentile for a non-empty list."""
    if not values:
        return 0.0

    sorted_values = sorted(values)
    if len(sorted_values) == 1:
        return float(sorted_values[0])

    index = (len(sorted_values) - 1) * (percent / 100.0)
    lower = int(index)
    upper = min(lower + 1, len(sorted_values) - 1)
    weight = index - lower
    return sorted_values[lower] * (1.0 - weight) + sorted_values[upper] * weight


def format_value(value):
    if isinstance(value, float):
        return f"{value:.6f}"
    return value


def write_csv(path, fieldnames, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as output_file:
        writer = csv.DictWriter(output_file, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: format_value(row.get(field, "")) for field in fieldnames})


def validate_row(filename, line_number, row):
    if row["serviceStartTime"] < row["arrivalTime"]:
        raise ValueError(f"{filename}:{line_number} service starts before arrival")

    if row["completionTime"] < row["serviceStartTime"]:
        raise ValueError(f"{filename}:{line_number} completion is before service start")

    if row["waitingTime"] != row["serviceStartTime"] - row["arrivalTime"]:
        raise ValueError(f"{filename}:{line_number} waitingTime does not match timestamps")

    if row["responseTime"] != row["serviceStartTime"] - row["arrivalTime"]:
        raise ValueError(f"{filename}:{line_number} responseTime does not match timestamps")

    if row["turnaroundTime"] != row["completionTime"] - row["arrivalTime"]:
        raise ValueError(f"{filename}:{line_number} turnaroundTime does not match timestamps")

    if not 0 <= row["patronID"] < row["noPatrons"]:
        raise ValueError(f"{filename}:{line_number} patronID is outside noPatrons range")


def read_result_rows(input_dir):
    csv_files = sorted(glob.glob(str(input_dir / "*.csv")))
    if not csv_files:
        raise FileNotFoundError(f"No CSV files found in {input_dir}")

    rows = []
    for filename in csv_files:
        with open(filename, newline="") as input_file:
            reader = csv.DictReader(input_file)
            if reader.fieldnames != EXPECTED_COLUMNS:
                raise ValueError(
                    f"{filename} has unexpected columns.\n"
                    f"Expected: {EXPECTED_COLUMNS}\n"
                    f"Found:    {reader.fieldnames}"
                )

            for line_number, row in enumerate(reader, start=2):
                row["sourceFile"] = Path(filename).name
                for column in INTEGER_COLUMNS:
                    try:
                        row[column] = int(row[column])
                    except ValueError as exc:
                        raise ValueError(
                            f"{filename}:{line_number} has non-integer {column}={row[column]!r}"
                        ) from exc

                validate_row(filename, line_number, row)
                rows.append(row)

    return rows


def group_runs(rows):
    runs = defaultdict(list)
    for row in rows:
        key = (
            row["scheduler"],
            row["noPatrons"],
            row["switchTime"],
            row["seed"],
            row["runId"],
        )
        runs[key].append(row)
    return runs


def build_run_summary(runs):
    summaries = []

    for key, run_rows in runs.items():
        scheduler, no_patrons, switch_time, seed, run_id = key

        waiting_times = [row["waitingTime"] for row in run_rows]
        response_times = [row["responseTime"] for row in run_rows]
        turnaround_times = [row["turnaroundTime"] for row in run_rows]
        execution_times = [row["executionTime"] for row in run_rows]

        patron_waits = defaultdict(int)
        for row in run_rows:
            patron_waits[row["patronID"]] += row["waitingTime"]

        total_waits_per_patron = [
            patron_waits.get(patron_id, 0)
            for patron_id in range(no_patrons)
        ]

        total_run_time = max(row["completionTime"] for row in run_rows)
        orders_completed = len(run_rows)
        throughput_per_ms = orders_completed / total_run_time if total_run_time > 0 else 0.0

        summaries.append({
            "runId": run_id,
            "scheduler": scheduler,
            "noPatrons": no_patrons,
            "switchTime": switch_time,
            "seed": seed,
            "ordersCompleted": orders_completed,
            "totalRunTime": total_run_time,
            "throughputOrdersPerMs": throughput_per_ms,
            "throughputOrdersPer1000Ms": throughput_per_ms * 1000.0,
            "avgWaitingTime": mean(waiting_times),
            "medianWaitingTime": median(waiting_times),
            "avgResponseTime": mean(response_times),
            "medianResponseTime": median(response_times),
            "avgTurnaroundTime": mean(turnaround_times),
            "medianTurnaroundTime": median(turnaround_times),
            "avgExecutionTime": mean(execution_times),
            "medianExecutionTime": median(execution_times),
            "minWaitingTime": min(waiting_times),
            "maxWaitingTime": max(waiting_times),
            "p95WaitingTime": percentile(waiting_times, 95),
            "avgPatronTotalWaitingTime": mean(total_waits_per_patron),
            "medianPatronTotalWaitingTime": median(total_waits_per_patron),
            "maxPatronTotalWaitingTime": max(total_waits_per_patron),
            "fairnessStdDevPatronTotalWaitingTime": stdev(total_waits_per_patron),
        })

    return sorted(summaries, key=run_sort_key)


def build_patron_summary(runs):
    patron_summaries = []

    for key, run_rows in runs.items():
        scheduler, no_patrons, switch_time, seed, run_id = key
        rows_by_patron = defaultdict(list)
        for row in run_rows:
            rows_by_patron[row["patronID"]].append(row)

        for patron_id in range(no_patrons):
            patron_rows = rows_by_patron.get(patron_id, [])
            waiting_times = [row["waitingTime"] for row in patron_rows]
            turnaround_times = [row["turnaroundTime"] for row in patron_rows]
            completion_times = [row["completionTime"] for row in patron_rows]

            patron_summaries.append({
                "runId": run_id,
                "scheduler": scheduler,
                "noPatrons": no_patrons,
                "switchTime": switch_time,
                "seed": seed,
                "patronID": patron_id,
                "ordersCompleted": len(patron_rows),
                "totalWaitingTime": sum(waiting_times),
                "avgWaitingTime": mean(waiting_times),
                "medianWaitingTime": median(waiting_times),
                "maxWaitingTime": max(waiting_times) if waiting_times else 0,
                "totalTurnaroundTime": sum(turnaround_times),
                "finalCompletionTime": max(completion_times) if completion_times else 0,
            })

    return sorted(patron_summaries, key=patron_sort_key)


def build_scheduler_summary(run_summaries):
    groups = defaultdict(list)
    for row in run_summaries:
        key = (row["scheduler"], row["noPatrons"], row["switchTime"])
        groups[key].append(row)

    summaries = []
    for key, rows in groups.items():
        scheduler, no_patrons, switch_time = key
        summaries.append({
            "scheduler": scheduler,
            "noPatrons": no_patrons,
            "switchTime": switch_time,
            "runs": len(rows),
            "totalOrdersCompleted": sum(row["ordersCompleted"] for row in rows),
            "avgWaitingTimeMean": mean([row["avgWaitingTime"] for row in rows]),
            "medianWaitingTimeMean": mean([row["medianWaitingTime"] for row in rows]),
            "avgResponseTimeMean": mean([row["avgResponseTime"] for row in rows]),
            "medianResponseTimeMean": mean([row["medianResponseTime"] for row in rows]),
            "avgTurnaroundTimeMean": mean([row["avgTurnaroundTime"] for row in rows]),
            "medianTurnaroundTimeMean": mean([row["medianTurnaroundTime"] for row in rows]),
            "throughputOrdersPer1000MsMean": mean([
                row["throughputOrdersPer1000Ms"] for row in rows
            ]),
            "fairnessStdDevMean": mean([
                row["fairnessStdDevPatronTotalWaitingTime"] for row in rows
            ]),
            "maxWaitingTimeMean": mean([row["maxWaitingTime"] for row in rows]),
            "p95WaitingTimeMean": mean([row["p95WaitingTime"] for row in rows]),
            "maxPatronTotalWaitingTimeMean": mean([
                row["maxPatronTotalWaitingTime"] for row in rows
            ]),
        })

    return sorted(summaries, key=scheduler_sort_key)


def run_sort_key(row):
    return (
        row["noPatrons"],
        row["seed"],
        SCHEDULER_ORDER.get(row["scheduler"], 99),
        row["switchTime"],
    )


def patron_sort_key(row):
    return (
        row["noPatrons"],
        row["seed"],
        SCHEDULER_ORDER.get(row["scheduler"], 99),
        row["switchTime"],
        row["patronID"],
    )


def scheduler_sort_key(row):
    return (
        row["noPatrons"],
        SCHEDULER_ORDER.get(row["scheduler"], 99),
        row["switchTime"],
    )


RUN_SUMMARY_COLUMNS = [
    "runId",
    "scheduler",
    "noPatrons",
    "switchTime",
    "seed",
    "ordersCompleted",
    "totalRunTime",
    "throughputOrdersPerMs",
    "throughputOrdersPer1000Ms",
    "avgWaitingTime",
    "medianWaitingTime",
    "avgResponseTime",
    "medianResponseTime",
    "avgTurnaroundTime",
    "medianTurnaroundTime",
    "avgExecutionTime",
    "medianExecutionTime",
    "minWaitingTime",
    "maxWaitingTime",
    "p95WaitingTime",
    "avgPatronTotalWaitingTime",
    "medianPatronTotalWaitingTime",
    "maxPatronTotalWaitingTime",
    "fairnessStdDevPatronTotalWaitingTime",
]

PATRON_SUMMARY_COLUMNS = [
    "runId",
    "scheduler",
    "noPatrons",
    "switchTime",
    "seed",
    "patronID",
    "ordersCompleted",
    "totalWaitingTime",
    "avgWaitingTime",
    "medianWaitingTime",
    "maxWaitingTime",
    "totalTurnaroundTime",
    "finalCompletionTime",
]

SCHEDULER_SUMMARY_COLUMNS = [
    "scheduler",
    "noPatrons",
    "switchTime",
    "runs",
    "totalOrdersCompleted",
    "avgWaitingTimeMean",
    "medianWaitingTimeMean",
    "avgResponseTimeMean",
    "medianResponseTimeMean",
    "avgTurnaroundTimeMean",
    "medianTurnaroundTimeMean",
    "throughputOrdersPer1000MsMean",
    "fairnessStdDevMean",
    "maxWaitingTimeMean",
    "p95WaitingTimeMean",
    "maxPatronTotalWaitingTimeMean",
]


def parse_args():
    parser = argparse.ArgumentParser(
        description="Generate analysis summaries from scheduling experiment CSV files."
    )
    parser.add_argument(
        "--input-dir",
        default="results",
        type=Path,
        help="Directory containing scheduler CSV files. Default: results",
    )
    parser.add_argument(
        "--output-dir",
        default="analysis_results",
        type=Path,
        help="Directory where summary CSV files should be written. Default: analysis_results",
    )
    return parser.parse_args()


def main():
    args = parse_args()
    rows = read_result_rows(args.input_dir)
    runs = group_runs(rows)

    run_summaries = build_run_summary(runs)
    patron_summaries = build_patron_summary(runs)
    scheduler_summaries = build_scheduler_summary(run_summaries)

    write_csv(args.output_dir / "run_summary.csv", RUN_SUMMARY_COLUMNS, run_summaries)
    write_csv(args.output_dir / "patron_summary.csv", PATRON_SUMMARY_COLUMNS, patron_summaries)
    write_csv(
        args.output_dir / "scheduler_summary.csv",
        SCHEDULER_SUMMARY_COLUMNS,
        scheduler_summaries,
    )

    print(f"Read {len(rows)} completed drink orders from {args.input_dir}")
    print(f"Summarised {len(run_summaries)} runs")
    print(f"Wrote {args.output_dir / 'run_summary.csv'}")
    print(f"Wrote {args.output_dir / 'patron_summary.csv'}")
    print(f"Wrote {args.output_dir / 'scheduler_summary.csv'}")


if __name__ == "__main__":
    main()
