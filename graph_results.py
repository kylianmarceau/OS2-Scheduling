#!/usr/bin/env python3
"""
Generate the required scheduling comparison graphs.

The assignment brief asks for graphs covering:
- response time
- waiting time per order
- total waiting time per patron
- turnaround time
- throughput
- predictability, fairness, and starvation risk

This script keeps those requirements compact by producing six report-ready PNGs.
"""

import argparse
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
from matplotlib.lines import Line2D
from matplotlib.ticker import FuncFormatter
import pandas as pd


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

NUMERIC_COLUMNS = [
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
]

SCHEDULERS = ["FCFS", "SJF", "PRIORITY", "MLFQ"]
COLORS = {
    "FCFS": "#2563eb",
    "SJF": "#059669",
    "PRIORITY": "#f97316",
    "MLFQ": "#7c3aed",
}
TEXT_COLOR = "#111827"
MUTED_TEXT = "#6b7280"
GRID_COLOR = "#e5e7eb"
FIGURE_BG = "#f8fafc"
AXIS_BG = "#ffffff"


def load_results(results_dir):
    csv_files = sorted(results_dir.glob("*.csv"))
    if not csv_files:
        raise FileNotFoundError(f"No CSV files found in {results_dir}")

    frames = []
    for csv_file in csv_files:
        frame = pd.read_csv(csv_file)
        if list(frame.columns) != EXPECTED_COLUMNS:
            raise ValueError(
                f"{csv_file} has unexpected columns.\n"
                f"Expected: {EXPECTED_COLUMNS}\n"
                f"Found:    {list(frame.columns)}"
            )
        frame["sourceFile"] = csv_file.name
        frames.append(frame)

    data = pd.concat(frames, ignore_index=True)
    for column in NUMERIC_COLUMNS:
        data[column] = pd.to_numeric(data[column], errors="raise")

    validate_results(data)
    return data


def validate_results(data):
    if data.empty:
        raise ValueError("The result CSV files are empty.")

    invalid_wait = data["waitingTime"] != data["serviceStartTime"] - data["arrivalTime"]
    invalid_response = data["responseTime"] != data["serviceStartTime"] - data["arrivalTime"]
    invalid_turnaround = data["turnaroundTime"] != data["completionTime"] - data["arrivalTime"]
    invalid_order = data["completionTime"] < data["serviceStartTime"]

    if invalid_wait.any():
        raise ValueError("At least one row has a waitingTime inconsistent with timestamps.")
    if invalid_response.any():
        raise ValueError("At least one row has a responseTime inconsistent with timestamps.")
    if invalid_turnaround.any():
        raise ValueError("At least one row has a turnaroundTime inconsistent with timestamps.")
    if invalid_order.any():
        raise ValueError("At least one row completes before service starts.")


def build_run_summary(data):
    run_rows = []
    patron_rows = []
    group_columns = ["runId", "scheduler", "noPatrons", "switchTime", "seed"]

    for run_key, run_data in data.groupby(group_columns, sort=False):
        run_id, scheduler, no_patrons, switch_time, seed = run_key
        run_time = run_data["completionTime"].max()
        orders_completed = len(run_data)

        patron_waits = (
            run_data.groupby("patronID")["waitingTime"]
            .sum()
            .reindex(range(int(no_patrons)), fill_value=0)
        )

        run_rows.append({
            "runId": run_id,
            "scheduler": scheduler,
            "noPatrons": no_patrons,
            "switchTime": switch_time,
            "seed": seed,
            "ordersCompleted": orders_completed,
            "throughput": orders_completed / run_time * 1000 if run_time else 0.0,
            "waitingMean": run_data["waitingTime"].mean(),
            "waitingMedian": run_data["waitingTime"].median(),
            "responseMean": run_data["responseTime"].mean(),
            "responseMedian": run_data["responseTime"].median(),
            "turnaroundMean": run_data["turnaroundTime"].mean(),
            "turnaroundMedian": run_data["turnaroundTime"].median(),
            "turnaroundStd": run_data["turnaroundTime"].std(ddof=0),
            "p95Waiting": run_data["waitingTime"].quantile(0.95),
            "maxWaiting": run_data["waitingTime"].max(),
            "patronWaitingMean": patron_waits.mean(),
            "patronWaitingMedian": patron_waits.median(),
            "patronWaitingStd": patron_waits.std(ddof=0),
            "maxPatronWaiting": patron_waits.max(),
        })

        for patron_id, total_waiting in patron_waits.items():
            patron_rows.append({
                "runId": run_id,
                "scheduler": scheduler,
                "noPatrons": no_patrons,
                "switchTime": switch_time,
                "seed": seed,
                "patronID": patron_id,
                "totalWaitingTime": total_waiting,
            })

    run_summary = pd.DataFrame(run_rows)
    patron_summary = pd.DataFrame(patron_rows)
    return run_summary, patron_summary


def build_load_summary(run_summary):
    value_columns = [
        "throughput",
        "waitingMean",
        "waitingMedian",
        "responseMean",
        "responseMedian",
        "turnaroundMean",
        "turnaroundMedian",
        "turnaroundStd",
        "p95Waiting",
        "maxWaiting",
        "patronWaitingMean",
        "patronWaitingMedian",
        "patronWaitingStd",
        "maxPatronWaiting",
    ]

    summary = (
        run_summary
        .groupby(["scheduler", "noPatrons"], as_index=False)[value_columns]
        .mean()
    )
    summary["scheduler"] = pd.Categorical(summary["scheduler"], SCHEDULERS, ordered=True)
    return summary.sort_values(["scheduler", "noPatrons"])


def set_style():
    plt.rcParams.update({
        "figure.facecolor": FIGURE_BG,
        "savefig.facecolor": FIGURE_BG,
        "axes.facecolor": AXIS_BG,
        "axes.grid": True,
        "grid.color": GRID_COLOR,
        "grid.linewidth": 0.8,
        "grid.alpha": 1.0,
        "axes.spines.top": False,
        "axes.spines.right": False,
        "axes.edgecolor": "#d1d5db",
        "axes.titleweight": "bold",
        "axes.titlecolor": TEXT_COLOR,
        "axes.labelcolor": MUTED_TEXT,
        "axes.labelsize": 10,
        "xtick.color": MUTED_TEXT,
        "ytick.color": MUTED_TEXT,
        "font.family": "DejaVu Sans",
        "font.size": 10,
        "legend.frameon": False,
    })


def metric_formatter(value, _):
    if abs(value) >= 1000:
        return f"{value:,.0f}"
    if abs(value) >= 100:
        return f"{value:.0f}"
    if abs(value) >= 10:
        return f"{value:.1f}"
    return f"{value:.2f}"


def polish_axes(ax):
    ax.set_axisbelow(True)
    ax.grid(True, axis="y")
    ax.grid(False, axis="x")
    ax.yaxis.set_major_formatter(FuncFormatter(metric_formatter))
    ax.spines["left"].set_color("#d1d5db")
    ax.spines["bottom"].set_color("#d1d5db")
    ax.tick_params(axis="both", which="major", labelsize=9, length=0, pad=6)
    ax.title.set_fontsize(11)
    ax.title.set_position((0, 1.02))
    ax.title.set_horizontalalignment("left")


def save_figure(fig, path):
    fig.savefig(path, dpi=200, bbox_inches="tight", pad_inches=0.25)
    plt.close(fig)


def save_table_figure(fig, path):
    fig.savefig(path, dpi=200, bbox_inches="tight", pad_inches=0.04, facecolor="#ffffff")
    plt.close(fig)


def scheduler_rows(frame, scheduler):
    return frame[frame["scheduler"] == scheduler].sort_values("noPatrons")


def add_scheduler_lines(ax, load_summary, column):
    for scheduler in SCHEDULERS:
        rows = scheduler_rows(load_summary, scheduler)
        ax.plot(
            rows["noPatrons"],
            rows[column],
            color=COLORS[scheduler],
            linewidth=2.0,
            marker="o",
            markersize=4.2,
            markeredgecolor=AXIS_BG,
            markeredgewidth=1.0,
            label=scheduler,
        )

    ax.set_xlabel("Number of patrons in run")
    ax.set_xticks(sorted(load_summary["noPatrons"].unique()))
    ax.margins(x=0.03, y=0.08)
    polish_axes(ax)


def add_scheduler_legend(fig, y=-0.01):
    scheduler_handles = [
        Line2D(
            [0],
            [0],
            color=COLORS[scheduler],
            linewidth=2.0,
            marker="o",
            markersize=4.2,
            markeredgecolor=AXIS_BG,
            markeredgewidth=1.0,
            label=scheduler,
        )
        for scheduler in SCHEDULERS
    ]
    legend = fig.legend(
        handles=scheduler_handles,
        loc="lower center",
        ncol=4,
        bbox_to_anchor=(0.5, y),
        columnspacing=1.8,
        handlelength=2.8,
    )
    for text in legend.get_texts():
        text.set_color(TEXT_COLOR)


def plot_core_metric_group(load_summary, output_dir, metric_type):
    if metric_type == "mean":
        metrics = [
            ("waitingMean", "Mean Per-Order Waiting Time", "Mean waiting time per order (ms)"),
            ("responseMean", "Mean Per-Order Response Time", "Mean response time per order (ms)"),
            ("turnaroundMean", "Mean Per-Order Turnaround Time", "Mean turnaround time per order (ms)"),
            ("patronWaitingMean", "Mean Total Waiting Time per Patron", "Mean total waiting time per patron (ms)"),
        ]
        title = "Mean Core Metrics by Load"
        filename = "01_core_metrics_mean.png"
    elif metric_type == "median":
        metrics = [
            ("waitingMedian", "Median Per-Order Waiting Time", "Median waiting time per order (ms)"),
            ("responseMedian", "Median Per-Order Response Time", "Median response time per order (ms)"),
            ("turnaroundMedian", "Median Per-Order Turnaround Time", "Median turnaround time per order (ms)"),
            ("patronWaitingMedian", "Median Total Waiting Time per Patron", "Median total waiting time per patron (ms)"),
        ]
        title = "Median Core Metrics by Load"
        filename = "02_core_metrics_median.png"
    else:
        raise ValueError(f"Unknown metric_type: {metric_type}")

    fig, axes = plt.subplots(2, 2, figsize=(12.2, 7.8), sharex=True)
    for ax, (column, subtitle, ylabel) in zip(axes.flat, metrics):
        add_scheduler_lines(ax, load_summary, column)
        ax.set_title(subtitle)
        ax.set_ylabel(ylabel)

    add_scheduler_legend(fig)
    fig.tight_layout(rect=(0, 0.06, 1, 1), h_pad=2.0, w_pad=2.0)
    save_figure(fig, output_dir / filename)


def color_boxplot(box):
    for patch, scheduler in zip(box["boxes"], SCHEDULERS):
        patch.set_facecolor(COLORS[scheduler])
        patch.set_alpha(0.82)
        patch.set_edgecolor("#1f2937")
        patch.set_linewidth(0.8)
    for key in ["whiskers", "caps"]:
        for item in box[key]:
            item.set_color("#374151")
            item.set_linewidth(1.1)
    for item in box["medians"]:
        item.set_color(TEXT_COLOR)
        item.set_linewidth(2.0)
    for item in box.get("means", []):
        item.set_marker("D")
        item.set_markerfacecolor(AXIS_BG)
        item.set_markeredgecolor(TEXT_COLOR)
        item.set_markersize(4.5)


def boxplot_by_scheduler(ax, values_by_scheduler, title, ylabel):
    values = [values_by_scheduler[scheduler].dropna() for scheduler in SCHEDULERS]
    box = ax.boxplot(
        values,
        tick_labels=SCHEDULERS,
        patch_artist=True,
        showfliers=False,
        showmeans=True,
        meanprops={
            "marker": "D",
            "markerfacecolor": AXIS_BG,
            "markeredgecolor": TEXT_COLOR,
            "markersize": 4.5,
        },
    )
    color_boxplot(box)
    ax.set_title(title)
    ax.set_ylabel(ylabel)
    ax.tick_params(axis="x", rotation=15)
    polish_axes(ax)


def plot_distributions(data, patron_summary, output_dir):
    fig, axes = plt.subplots(2, 2, figsize=(12.2, 7.8))

    boxplot_by_scheduler(
        axes[0, 0],
        {s: data.loc[data["scheduler"] == s, "waitingTime"] for s in SCHEDULERS},
        "Per-Order Waiting Time Distribution",
        "Waiting time per order (ms)",
    )
    boxplot_by_scheduler(
        axes[0, 1],
        {s: data.loc[data["scheduler"] == s, "responseTime"] for s in SCHEDULERS},
        "Per-Order Response Time Distribution",
        "Response time per order (ms)",
    )
    boxplot_by_scheduler(
        axes[1, 0],
        {s: data.loc[data["scheduler"] == s, "turnaroundTime"] for s in SCHEDULERS},
        "Per-Order Turnaround Time Distribution",
        "Turnaround time per order (ms)",
    )
    boxplot_by_scheduler(
        axes[1, 1],
        {s: patron_summary.loc[patron_summary["scheduler"] == s, "totalWaitingTime"] for s in SCHEDULERS},
        "Total Waiting Time per Patron Distribution",
        "Total waiting time per patron per run (ms)",
    )

    fig.tight_layout(rect=(0, 0, 1, 1), h_pad=2.0, w_pad=2.0)
    save_figure(fig, output_dir / "03_core_metric_distributions.png")


def plot_throughput(run_summary, load_summary, output_dir):
    fig, axes = plt.subplots(1, 2, figsize=(12.2, 5.0))

    add_scheduler_lines(axes[0], load_summary, "throughput")
    axes[0].set_title("Mean Throughput by Patron Count")
    axes[0].set_ylabel("Completed orders per 1000 ms")

    boxplot_by_scheduler(
        axes[1],
        {s: run_summary.loc[run_summary["scheduler"] == s, "throughput"] for s in SCHEDULERS},
        "Run Throughput Distribution",
        "Completed orders per 1000 ms",
    )

    scheduler_handles = [
        Line2D([0], [0], color=COLORS[scheduler], linewidth=2.0, marker="o", markersize=4.2, label=scheduler)
        for scheduler in SCHEDULERS
    ]
    fig.legend(handles=scheduler_handles, loc="lower center", ncol=4, bbox_to_anchor=(0.5, -0.02))
    fig.tight_layout(rect=(0, 0.08, 1, 1), w_pad=2.0)
    save_figure(fig, output_dir / "04_throughput.png")


def plot_quality_metrics(load_summary, output_dir):
    metrics = [
        ("turnaroundStd", "Predictability: Per-Order Turnaround Variation", "Std. dev. of per-order turnaround time (ms)"),
        ("patronWaitingStd", "Fairness: Variation in Total Waiting per Patron", "Std. dev. of total patron waiting time (ms)"),
        ("p95Waiting", "Starvation Risk: 95th Percentile Per-Order Wait", "95th percentile per-order waiting time (ms)"),
        ("maxWaiting", "Starvation Risk: Maximum Per-Order Wait", "Maximum per-order waiting time (ms)"),
    ]

    fig, axes = plt.subplots(2, 2, figsize=(12.2, 7.8), sharex=True)
    for ax, (column, title, ylabel) in zip(axes.flat, metrics):
        add_scheduler_lines(ax, load_summary, column)
        ax.set_title(title)
        ax.set_ylabel(ylabel)

    scheduler_handles = [
        Line2D([0], [0], color=COLORS[scheduler], linewidth=2.0, marker="o", markersize=4.2, label=scheduler)
        for scheduler in SCHEDULERS
    ]
    fig.legend(handles=scheduler_handles, loc="lower center", ncol=4, bbox_to_anchor=(0.5, -0.01))
    fig.tight_layout(rect=(0, 0.06, 1, 1), h_pad=2.0, w_pad=2.0)
    save_figure(fig, output_dir / "05_predictability_fairness_starvation.png")


def format_number(value):
    if pd.isna(value):
        return ""
    if abs(value) >= 1000:
        return f"{value:,.0f}"
    if abs(value) >= 100:
        return f"{value:.1f}"
    return f"{value:.3f}"


def plot_metric_summary_table(run_summary, output_dir):
    metrics = [
        ("Experiment coverage", "runs", "Runs", "sum"),
        ("Experiment coverage", "ordersCompleted", "Orders completed", "sum"),
        ("Efficiency", "throughput", "Mean throughput (orders / 1000 ms)", "mean"),
        ("Order-level timing", "waitingMean", "Mean waiting time (ms)", "mean"),
        ("Order-level timing", "waitingMedian", "Median waiting time (ms)", "mean"),
        ("Order-level timing", "responseMean", "Mean response time (ms)", "mean"),
        ("Order-level timing", "responseMedian", "Median response time (ms)", "mean"),
        ("Order-level timing", "turnaroundMean", "Mean turnaround time (ms)", "mean"),
        ("Order-level timing", "turnaroundMedian", "Median turnaround time (ms)", "mean"),
        ("Predictability", "turnaroundStd", "Turnaround std. dev. (ms)", "mean"),
        ("Patron-level fairness", "patronWaitingMean", "Mean total patron waiting (ms)", "mean"),
        ("Patron-level fairness", "patronWaitingMedian", "Median total patron waiting (ms)", "mean"),
        ("Patron-level fairness", "patronWaitingStd", "Patron waiting std. dev. (ms)", "mean"),
        ("Starvation indicators", "p95Waiting", "95th percentile order wait (ms)", "mean"),
        ("Starvation indicators", "maxWaiting", "Maximum order wait (ms)", "mean"),
        ("Starvation indicators", "maxPatronWaiting", "Worst patron total waiting (ms)", "mean"),
    ]

    summary_rows = []
    for scheduler in SCHEDULERS:
        scheduler_runs = run_summary[run_summary["scheduler"] == scheduler]
        row = {"scheduler": scheduler}
        row["runs"] = len(scheduler_runs)
        for _, column, _, reducer in metrics:
            if column == "runs":
                continue
            if reducer == "sum":
                row[column] = scheduler_runs[column].sum()
            else:
                row[column] = scheduler_runs[column].mean()
        summary_rows.append(row)

    summary = pd.DataFrame(summary_rows).set_index("scheduler")
    cell_text = []
    previous_group = None
    group_rows = []
    for group, column, label, _ in metrics:
        if group != previous_group:
            group_rows.append(len(cell_text) + 1)
            cell_text.append([group, "", "", "", ""])
            previous_group = group
        cell_text.append(["  " + label] + [format_number(summary.loc[scheduler, column]) for scheduler in SCHEDULERS])

    fig_height = 0.31 * (len(cell_text) + 1)
    fig, ax = plt.subplots(figsize=(12.0, fig_height))
    fig.patch.set_facecolor("#ffffff")
    ax.set_position([0, 0, 1, 1])
    ax.axis("off")

    table = ax.table(
        cellText=cell_text,
        colLabels=["Metric"] + SCHEDULERS,
        cellLoc="right",
        colLoc="center",
        bbox=[0, 0, 1, 1],
        colWidths=[0.46, 0.135, 0.135, 0.135, 0.135],
    )
    table.auto_set_font_size(False)
    table.set_fontsize(9.2)
    table.scale(1, 1.32)

    for (row, col), cell in table.get_celld().items():
        cell.set_edgecolor("#e5e7eb")
        cell.set_linewidth(0.45)
        if row == 0:
            cell.set_facecolor("#f8fafc")
            cell.get_text().set_color(TEXT_COLOR)
            cell.get_text().set_weight("bold")
            cell.PAD = 0.06
            if col == 0:
                cell.get_text().set_ha("left")
            else:
                cell.get_text().set_ha("center")
        elif row in group_rows:
            cell.set_facecolor("#eef2f7")
            cell.set_linewidth(0)
            cell.PAD = 0.055
            if col == 0:
                cell.get_text().set_color("#374151")
                cell.get_text().set_weight("bold")
                cell.get_text().set_ha("left")
            else:
                cell.get_text().set_text("")
        elif col == 0:
            cell.set_facecolor("#ffffff")
            cell.get_text().set_ha("left")
            cell.get_text().set_color("#374151")
            cell.PAD = 0.04
        elif row % 2 == 0:
            cell.set_facecolor("#ffffff")
            cell.get_text().set_color(TEXT_COLOR)
            cell.get_text().set_ha("right")
            cell.PAD = 0.04
        else:
            cell.set_facecolor("#fbfdff")
            cell.get_text().set_color(TEXT_COLOR)
            cell.get_text().set_ha("right")
            cell.PAD = 0.04

    save_table_figure(fig, output_dir / "06_metric_summary_table.png")


def print_required_summary(data, run_summary):
    print(f"Read {len(data)} completed drink orders.")
    print(f"Summarised {len(run_summary)} runs.")
    print("Required graph/table set:")
    print("  01_core_metrics_mean.png")
    print("  02_core_metrics_median.png")
    print("  03_core_metric_distributions.png")
    print("  04_throughput.png")
    print("  05_predictability_fairness_starvation.png")
    print("  06_metric_summary_table.png")


def parse_args():
    parser = argparse.ArgumentParser(description="Generate the required assignment graphs.")
    parser.add_argument(
        "--results-dir",
        type=Path,
        default=Path("results"),
        help="Directory containing scheduler CSV files. Default: results",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("graphs"),
        help="Directory where graph PNGs are written. Default: graphs",
    )
    return parser.parse_args()


def main():
    args = parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    set_style()

    data = load_results(args.results_dir)
    run_summary, patron_summary = build_run_summary(data)
    load_summary = build_load_summary(run_summary)

    plot_core_metric_group(load_summary, args.output_dir, "mean")
    plot_core_metric_group(load_summary, args.output_dir, "median")
    plot_distributions(data, patron_summary, args.output_dir)
    plot_throughput(run_summary, load_summary, args.output_dir)
    plot_quality_metrics(load_summary, args.output_dir)
    plot_metric_summary_table(run_summary, args.output_dir)

    print_required_summary(data, run_summary)
    print(f"Wrote graphs to {args.output_dir}")


if __name__ == "__main__":
    main()
