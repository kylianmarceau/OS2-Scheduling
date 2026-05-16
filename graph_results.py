#!/usr/bin/env python3
"""
Generate graphs for the Allegra the Barman scheduling experiment.

Inputs:
    analysis_results/scheduler_summary.csv
    analysis_results/run_summary.csv
    analysis_results/patron_summary.csv
    results/*.csv

Outputs:
    graphs/*.png
"""

import argparse
import glob
import os
import tempfile
from pathlib import Path

os.environ.setdefault(
    "MPLCONFIGDIR",
    str(Path(tempfile.gettempdir()) / "os2-scheduling-matplotlib"),
)
Path(os.environ["MPLCONFIGDIR"]).mkdir(parents=True, exist_ok=True)

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import pandas as pd


SCHEDULER_ORDER = ["FCFS", "SJF", "PRIORITY", "MLFQ"]
SCHEDULER_COLORS = {
    "FCFS": "#1f77b4",
    "SJF": "#2ca02c",
    "PRIORITY": "#d62728",
    "MLFQ": "#9467bd",
}


LINE_GRAPHS = [
    {
        "filename": "01_average_waiting_time.png",
        "column": "avgWaitingTimeMean",
        "title": "Average Waiting Time by Scheduler",
        "ylabel": "Average waiting time (ms)",
    },
    {
        "filename": "02_median_waiting_time.png",
        "column": "medianWaitingTimeMean",
        "title": "Median Waiting Time by Scheduler",
        "ylabel": "Median waiting time (ms)",
    },
    {
        "filename": "03_average_response_time.png",
        "column": "avgResponseTimeMean",
        "title": "Average Response Time by Scheduler",
        "ylabel": "Average response time (ms)",
    },
    {
        "filename": "04_average_turnaround_time.png",
        "column": "avgTurnaroundTimeMean",
        "title": "Average Turnaround Time by Scheduler",
        "ylabel": "Average turnaround time (ms)",
    },
    {
        "filename": "05_throughput.png",
        "column": "throughputOrdersPer1000MsMean",
        "title": "Throughput by Scheduler",
        "ylabel": "Completed orders per 1000 ms",
    },
    {
        "filename": "06_fairness_stddev.png",
        "column": "fairnessStdDevMean",
        "title": "Fairness: Spread of Total Patron Waiting Times",
        "ylabel": "Std. dev. of patron total waiting time (ms)",
    },
    {
        "filename": "07_p95_waiting_starvation.png",
        "column": "p95WaitingTimeMean",
        "title": "Starvation Indicator: 95th Percentile Waiting Time",
        "ylabel": "95th percentile waiting time (ms)",
    },
    {
        "filename": "08_max_waiting_starvation.png",
        "column": "maxWaitingTimeMean",
        "title": "Starvation Indicator: Maximum Waiting Time",
        "ylabel": "Maximum waiting time (ms)",
    },
    {
        "filename": "09_max_patron_total_waiting.png",
        "column": "maxPatronTotalWaitingTimeMean",
        "title": "Worst Patron Total Waiting Time",
        "ylabel": "Maximum patron total waiting time (ms)",
    },
]


def require_file(path):
    if not path.exists():
        raise FileNotFoundError(
            f"Missing {path}. Run python3 analysis.py before graph_results.py."
        )


def make_output_dir(path):
    path.mkdir(parents=True, exist_ok=True)


def set_common_style():
    plt.rcParams.update({
        "figure.figsize": (9.5, 5.8),
        "axes.grid": True,
        "grid.alpha": 0.28,
        "axes.spines.top": False,
        "axes.spines.right": False,
        "axes.titleweight": "bold",
        "axes.labelsize": 10,
        "legend.frameon": False,
        "font.size": 10,
    })


def plot_metric_lines(summary, output_dir):
    for graph in LINE_GRAPHS:
        fig, ax = plt.subplots()

        for scheduler in SCHEDULER_ORDER:
            scheduler_rows = summary[summary["scheduler"] == scheduler].sort_values("noPatrons")
            if scheduler_rows.empty:
                continue

            ax.plot(
                scheduler_rows["noPatrons"],
                scheduler_rows[graph["column"]],
                marker="o",
                linewidth=2,
                markersize=4,
                label=scheduler,
                color=SCHEDULER_COLORS[scheduler],
            )

        ax.set_title(graph["title"])
        ax.set_xlabel("Number of patrons")
        ax.set_ylabel(graph["ylabel"])
        ax.legend(title="Scheduler")
        ax.set_xticks(sorted(summary["noPatrons"].unique()))
        fig.tight_layout()
        fig.savefig(output_dir / graph["filename"], dpi=180)
        plt.close(fig)


def plot_run_boxplot(run_summary, output_dir):
    metrics = [
        ("avgWaitingTime", "10_run_average_waiting_boxplot.png", "Run Average Waiting Time Distribution"),
        ("avgTurnaroundTime", "11_run_average_turnaround_boxplot.png", "Run Average Turnaround Time Distribution"),
        ("throughputOrdersPer1000Ms", "12_run_throughput_boxplot.png", "Run Throughput Distribution"),
    ]

    for column, filename, title in metrics:
        grouped = [
            run_summary[run_summary["scheduler"] == scheduler][column].dropna()
            for scheduler in SCHEDULER_ORDER
        ]

        fig, ax = plt.subplots(figsize=(8.2, 5.5))
        box = ax.boxplot(
            grouped,
            tick_labels=SCHEDULER_ORDER,
            patch_artist=True,
            showfliers=True,
        )
        color_boxplot(box)
        ax.set_title(title)
        ax.set_xlabel("Scheduler")
        ax.set_ylabel(column_to_label(column))
        fig.tight_layout()
        fig.savefig(output_dir / filename, dpi=180)
        plt.close(fig)


def plot_raw_waiting_boxplot(results_dir, output_dir):
    rows = []
    for filename in sorted(glob.glob(str(results_dir / "*.csv"))):
        frame = pd.read_csv(filename, usecols=["scheduler", "waitingTime", "turnaroundTime"])
        rows.append(frame)

    if not rows:
        return

    raw = pd.concat(rows, ignore_index=True)

    for column, filename, title, ylabel in [
        (
            "waitingTime",
            "13_raw_waiting_time_boxplot.png",
            "Per-Order Waiting Time Distribution",
            "Waiting time (ms)",
        ),
        (
            "turnaroundTime",
            "14_raw_turnaround_time_boxplot.png",
            "Per-Order Turnaround Time Distribution",
            "Turnaround time (ms)",
        ),
    ]:
        grouped = [
            raw[raw["scheduler"] == scheduler][column].dropna()
            for scheduler in SCHEDULER_ORDER
        ]

        fig, ax = plt.subplots(figsize=(8.2, 5.5))
        box = ax.boxplot(
            grouped,
            tick_labels=SCHEDULER_ORDER,
            patch_artist=True,
            showfliers=False,
        )
        color_boxplot(box)
        ax.set_title(title)
        ax.set_xlabel("Scheduler")
        ax.set_ylabel(ylabel)
        ax.text(
            0.01,
            0.02,
            "Outliers hidden to keep the distributions readable.",
            transform=ax.transAxes,
            fontsize=8,
            alpha=0.75,
        )
        fig.tight_layout()
        fig.savefig(output_dir / filename, dpi=180)
        plt.close(fig)


def plot_patron_total_wait_boxplot(patron_summary, output_dir):
    grouped = [
        patron_summary[patron_summary["scheduler"] == scheduler]["totalWaitingTime"].dropna()
        for scheduler in SCHEDULER_ORDER
    ]

    fig, ax = plt.subplots(figsize=(8.2, 5.5))
    box = ax.boxplot(
        grouped,
        tick_labels=SCHEDULER_ORDER,
        patch_artist=True,
        showfliers=False,
    )
    color_boxplot(box)
    ax.set_title("Per-Patron Total Waiting Time Distribution")
    ax.set_xlabel("Scheduler")
    ax.set_ylabel("Total waiting time per patron (ms)")
    ax.text(
        0.01,
        0.02,
        "Outliers hidden to keep the distributions readable.",
        transform=ax.transAxes,
        fontsize=8,
        alpha=0.75,
    )
    fig.tight_layout()
    fig.savefig(output_dir / "15_patron_total_waiting_boxplot.png", dpi=180)
    plt.close(fig)


def color_boxplot(box):
    for patch, scheduler in zip(box["boxes"], SCHEDULER_ORDER):
        patch.set_facecolor(SCHEDULER_COLORS[scheduler])
        patch.set_alpha(0.7)
    for element in ["whiskers", "caps", "medians"]:
        for item in box[element]:
            item.set_color("#333333")
            item.set_linewidth(1.2)


def column_to_label(column):
    labels = {
        "avgWaitingTime": "Average waiting time (ms)",
        "avgTurnaroundTime": "Average turnaround time (ms)",
        "throughputOrdersPer1000Ms": "Completed orders per 1000 ms",
    }
    return labels.get(column, column)


def parse_args():
    parser = argparse.ArgumentParser(
        description="Generate scheduling experiment graphs from analysis CSV files."
    )
    parser.add_argument(
        "--analysis-dir",
        default="analysis_results",
        type=Path,
        help="Directory containing analysis summary CSV files. Default: analysis_results",
    )
    parser.add_argument(
        "--results-dir",
        default="results",
        type=Path,
        help="Directory containing raw scheduler CSV files. Default: results",
    )
    parser.add_argument(
        "--output-dir",
        default="graphs",
        type=Path,
        help="Directory where PNG graphs should be written. Default: graphs",
    )
    return parser.parse_args()


def main():
    args = parse_args()
    scheduler_summary_path = args.analysis_dir / "scheduler_summary.csv"
    run_summary_path = args.analysis_dir / "run_summary.csv"
    patron_summary_path = args.analysis_dir / "patron_summary.csv"

    require_file(scheduler_summary_path)
    require_file(run_summary_path)
    require_file(patron_summary_path)
    make_output_dir(args.output_dir)
    set_common_style()

    scheduler_summary = pd.read_csv(scheduler_summary_path)
    run_summary = pd.read_csv(run_summary_path)
    patron_summary = pd.read_csv(patron_summary_path)

    plot_metric_lines(scheduler_summary, args.output_dir)
    plot_run_boxplot(run_summary, args.output_dir)
    plot_raw_waiting_boxplot(args.results_dir, args.output_dir)
    plot_patron_total_wait_boxplot(patron_summary, args.output_dir)

    graph_count = len(list(args.output_dir.glob("*.png")))
    print(f"Wrote {graph_count} graph PNG files to {args.output_dir}")


if __name__ == "__main__":
    main()
