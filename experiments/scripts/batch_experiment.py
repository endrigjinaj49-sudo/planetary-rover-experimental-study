#!/usr/bin/env python3
"""
Run a batch of reproducible planetary-rover PDDL+ experiments.

For every experimental condition, this script:

1. Generates a PDDL+ problem.
2. Saves its metadata.
3. Runs ENHSP.
4. Extracts planner and plan metrics.
5. Appends one row to a CSV results file.
"""

from __future__ import annotations

import argparse
import csv
import json
import statistics
import sys
import time
from itertools import product
from pathlib import Path
from typing import Any

from planner_runner import run_enhsp
from problem_generator import generate_problem, load_config


RESULT_FIELDS = [
    "instance_id",
    "seed",
    "dataset_count",
    "memory_level",
    "memory_ratio",
    "memory_capacity",
    "total_dataset_size",
    "memory_utilization_ratio",
    "corruption_level",
    "safe_dataset_count",
    "unsafe_dataset_count",
    "all_datasets_theoretically_safe",
    "dataset_sizes",
    "encoding_times",
    "corruption_margins",
    "loss_times",
    "status",
    "solved",
    "planner",
    "timeout_seconds",
    "wall_runtime_seconds",
    "return_code",
    "reported_plan_length",
    "reported_elapsed_time",
    "plan_makespan",
    "action_count",
    "move_actions",
    "collect_actions",
    "offload_actions",
    "waiting_periods",
    "total_waiting_time",
    "problem_file",
    "metadata_file",
    "raw_output_file",
    "error_message",
]


def mean_or_none(values: list[float]) -> float | None:
    """Return the mean of a non-empty list."""

    if not values:
        return None

    return statistics.mean(values)


def create_result_row(
    metadata: dict[str, Any],
    planner_result: dict[str, Any],
    problem_path: Path,
    metadata_path: Path,
) -> dict[str, Any]:
    """Combine problem metadata and planner metrics into one CSV row."""

    datasets = metadata["datasets"]

    dataset_sizes = [
        dataset["size"]
        for dataset in datasets
    ]

    encoding_times = [
        dataset["encoding_time"]
        for dataset in datasets
    ]

    corruption_margins = [
        dataset["corruption_margin"]
        for dataset in datasets
    ]

    loss_times = [
        dataset["loss_time"]
        for dataset in datasets
    ]

    memory_capacity = metadata["memory_capacity"]
    total_dataset_size = metadata["total_dataset_size"]

    memory_utilization_ratio = (
        total_dataset_size / memory_capacity
        if memory_capacity > 0
        else None
    )

    return {
        "instance_id": metadata["instance_id"],
        "seed": metadata["seed"],
        "dataset_count": metadata["dataset_count"],
        "memory_level": metadata["memory_level"],
        "memory_ratio": metadata["memory_ratio"],
        "memory_capacity": memory_capacity,
        "total_dataset_size": total_dataset_size,
        "memory_utilization_ratio": (
            round(memory_utilization_ratio, 6)
            if memory_utilization_ratio is not None
            else None
        ),
        "corruption_level": metadata["corruption_level"],
        "safe_dataset_count": metadata["safe_dataset_count"],
        "unsafe_dataset_count": metadata["unsafe_dataset_count"],
        "all_datasets_theoretically_safe": (
            metadata["unsafe_dataset_count"] == 0
        ),
        "dataset_sizes": json.dumps(dataset_sizes),
        "encoding_times": json.dumps(encoding_times),
        "corruption_margins": json.dumps(corruption_margins),
        "loss_times": json.dumps(loss_times),
        "status": planner_result.get("status", "error"),
        "solved": planner_result.get("solved", False),
        "planner": planner_result.get("planner", ""),
        "timeout_seconds": planner_result.get(
            "timeout_seconds"
        ),
        "wall_runtime_seconds": planner_result.get(
            "wall_runtime_seconds"
        ),
        "return_code": planner_result.get("return_code"),
        "reported_plan_length": planner_result.get(
            "reported_plan_length"
        ),
        "reported_elapsed_time": planner_result.get(
            "reported_elapsed_time"
        ),
        "plan_makespan": planner_result.get(
            "plan_makespan"
        ),
        "action_count": planner_result.get(
            "action_count",
            0,
        ),
        "move_actions": planner_result.get(
            "move_actions",
            0,
        ),
        "collect_actions": planner_result.get(
            "collect_actions",
            0,
        ),
        "offload_actions": planner_result.get(
            "offload_actions",
            0,
        ),
        "waiting_periods": planner_result.get(
            "waiting_periods",
            0,
        ),
        "total_waiting_time": planner_result.get(
            "total_waiting_time",
            0.0,
        ),
        "problem_file": str(problem_path),
        "metadata_file": str(metadata_path),
        "raw_output_file": planner_result.get(
            "output_file",
            "",
        ),
        "error_message": planner_result.get(
            "error",
            "",
        ),
    }


def load_existing_instance_ids(
    results_path: Path,
) -> set[str]:
    """Read completed instance IDs for resume mode."""

    if not results_path.is_file():
        return set()

    with results_path.open(
        "r",
        encoding="utf-8",
        newline="",
    ) as csv_file:
        reader = csv.DictReader(csv_file)

        return {
            row["instance_id"]
            for row in reader
            if row.get("instance_id")
        }


def parse_arguments() -> argparse.Namespace:
    """Read command-line arguments."""

    default_jar = (
        Path.home()
        / "enhsp"
        / "ENHSP-Public"
        / "enhsp-dist"
        / "enhsp.jar"
    )

    parser = argparse.ArgumentParser(
        description=(
            "Generate and run a batch of rover "
            "PDDL+ experiments."
        )
    )

    parser.add_argument(
        "--config",
        type=Path,
        default=Path(
            "experiments/config/experiment_config.json"
        ),
        help="Experiment configuration JSON file.",
    )

    parser.add_argument(
        "--domain",
        type=Path,
        default=Path(
            "planning_models/pddl_plus/"
            "domain-memory-rover-plus.pddl"
        ),
        help="PDDL+ domain file.",
    )

    parser.add_argument(
        "--enhsp-jar",
        type=Path,
        default=default_jar,
        help="Path to enhsp.jar.",
    )

    parser.add_argument(
        "--generated-dir",
        type=Path,
        default=Path(
            "experiments/generated_problems"
        ),
        help="Directory for generated problems.",
    )

    parser.add_argument(
        "--raw-output-dir",
        type=Path,
        default=Path(
            "experiments/raw_outputs"
        ),
        help="Directory for raw ENHSP output.",
    )

    parser.add_argument(
        "--results",
        type=Path,
        default=Path(
            "experiments/results/pilot_results.csv"
        ),
        help="CSV results file.",
    )

    parser.add_argument(
        "--runs-per-condition",
        type=int,
        default=1,
        help=(
            "Number of different seeded missions "
            "for each condition. Default: 1."
        ),
    )

    parser.add_argument(
        "--seed-start",
        type=int,
        default=0,
        help="First random seed. Default: 0.",
    )

    parser.add_argument(
        "--timeout",
        type=float,
        default=120.0,
        help=(
            "Maximum ENHSP runtime per instance "
            "in seconds. Default: 120."
        ),
    )

    parser.add_argument(
        "--planner",
        type=str,
        default=None,
        help=(
            "Optional ENHSP planner configuration, "
            "for example opt-hrmax."
        ),
    )

    parser.add_argument(
        "--resume",
        action="store_true",
        help=(
            "Append to an existing CSV and skip "
            "already completed instance IDs."
        ),
    )

    parser.add_argument(
        "--max-instances",
        type=int,
        default=None,
        help=(
            "Optional maximum number of instances. "
            "Useful for smoke testing."
        ),
    )

    return parser.parse_args()


def main() -> int:
    """Generate, run, and save the experiment batch."""

    arguments = parse_arguments()

    if arguments.runs_per_condition < 1:
        print(
            "Error: --runs-per-condition must be at least 1.",
            file=sys.stderr,
        )
        return 1

    try:
        config = load_config(arguments.config.resolve())
    except (
        FileNotFoundError,
        json.JSONDecodeError,
    ) as error:
        print(
            json.dumps(
                {
                    "status": "configuration_error",
                    "error": str(error),
                },
                indent=2,
            )
        )
        return 1

    domain_path = arguments.domain.resolve()
    enhsp_jar = arguments.enhsp_jar.expanduser().resolve()

    if not domain_path.is_file():
        print(
            f"Domain file not found: {domain_path}",
            file=sys.stderr,
        )
        return 1

    if not enhsp_jar.is_file():
        print(
            f"ENHSP JAR not found: {enhsp_jar}",
            file=sys.stderr,
        )
        return 1

    generated_dir = arguments.generated_dir.resolve()
    raw_output_dir = arguments.raw_output_dir.resolve()
    results_path = arguments.results.resolve()

    generated_dir.mkdir(parents=True, exist_ok=True)
    raw_output_dir.mkdir(parents=True, exist_ok=True)
    results_path.parent.mkdir(parents=True, exist_ok=True)

    dataset_counts = list(config["dataset_counts"])
    memory_levels = list(config["memory_ratios"].keys())
    corruption_levels = list(
        config["corruption_margin_choices"].keys()
    )

    seeds = list(
        range(
            arguments.seed_start,
            arguments.seed_start
            + arguments.runs_per_condition,
        )
    )

    conditions = list(
        product(
            dataset_counts,
            memory_levels,
            corruption_levels,
            seeds,
        )
    )

    if arguments.max_instances is not None:
        conditions = conditions[: arguments.max_instances]

    existing_ids = (
        load_existing_instance_ids(results_path)
        if arguments.resume
        else set()
    )

    file_mode = (
        "a"
        if arguments.resume and results_path.is_file()
        else "w"
    )

    write_header = (
        file_mode == "w"
        or results_path.stat().st_size == 0
        if results_path.exists()
        else True
    )

    counters = {
        "solved": 0,
        "unsolvable": 0,
        "timeout": 0,
        "error": 0,
        "unknown": 0,
        "skipped": 0,
    }

    planner_runtimes: list[float] = []
    batch_start = time.perf_counter()

    with results_path.open(
        file_mode,
        encoding="utf-8",
        newline="",
    ) as csv_file:
        writer = csv.DictWriter(
            csv_file,
            fieldnames=RESULT_FIELDS,
        )

        if write_header:
            writer.writeheader()

        total_conditions = len(conditions)

        for index, (
            dataset_count,
            memory_level,
            corruption_level,
            seed,
        ) in enumerate(conditions, start=1):

            try:
                problem_text, metadata = generate_problem(
                    config=config,
                    dataset_count=dataset_count,
                    memory_level=memory_level,
                    corruption_level=corruption_level,
                    seed=seed,
                )

                instance_id = metadata["instance_id"]

                if instance_id in existing_ids:
                    counters["skipped"] += 1
                    print(
                        f"[{index}/{total_conditions}] "
                        f"{instance_id}: skipped"
                    )
                    continue

                problem_path = (
                    generated_dir
                    / f"{instance_id}.pddl"
                )

                metadata_path = (
                    generated_dir
                    / f"{instance_id}.json"
                )

                raw_output_path = (
                    raw_output_dir
                    / f"{instance_id}.txt"
                )

                problem_path.write_text(
                    problem_text,
                    encoding="utf-8",
                )

                metadata_path.write_text(
                    json.dumps(metadata, indent=2),
                    encoding="utf-8",
                )

                planner_result = run_enhsp(
                    domain_path=domain_path,
                    problem_path=problem_path,
                    enhsp_jar=enhsp_jar,
                    output_path=raw_output_path,
                    timeout_seconds=arguments.timeout,
                    planner=arguments.planner,
                )

            except Exception as error:
                # Continue the batch even if one instance fails.
                instance_id = (
                    f"rover-n{dataset_count}"
                    f"-mem-{memory_level}"
                    f"-corr-{corruption_level}"
                    f"-seed-{seed}"
                )

                metadata = {
                    "instance_id": instance_id,
                    "seed": seed,
                    "dataset_count": dataset_count,
                    "memory_level": memory_level,
                    "memory_ratio": config[
                        "memory_ratios"
                    ][memory_level],
                    "memory_capacity": 0,
                    "total_dataset_size": 0,
                    "corruption_level": corruption_level,
                    "safe_dataset_count": 0,
                    "unsafe_dataset_count": 0,
                    "datasets": [],
                }

                problem_path = (
                    generated_dir
                    / f"{instance_id}.pddl"
                )

                metadata_path = (
                    generated_dir
                    / f"{instance_id}.json"
                )

                planner_result = {
                    "status": "error",
                    "solved": False,
                    "planner": (
                        arguments.planner
                        or "ENHSP default"
                    ),
                    "timeout_seconds": arguments.timeout,
                    "wall_runtime_seconds": None,
                    "return_code": None,
                    "output_file": "",
                    "error": (
                        f"{type(error).__name__}: {error}"
                    ),
                }

            row = create_result_row(
                metadata=metadata,
                planner_result=planner_result,
                problem_path=problem_path,
                metadata_path=metadata_path,
            )

            writer.writerow(row)
            csv_file.flush()

            status = str(row["status"])

            if status not in counters:
                counters["unknown"] += 1
            else:
                counters[status] += 1

            runtime = row["wall_runtime_seconds"]

            if runtime is not None:
                planner_runtimes.append(float(runtime))

            print(
                f"[{index}/{total_conditions}] "
                f"{row['instance_id']}: "
                f"{status}, "
                f"runtime={runtime}"
            )

    batch_runtime = time.perf_counter() - batch_start

    summary = {
        "status": "batch_complete",
        "results_file": str(results_path),
        "requested_instances": len(conditions),
        "completed_instances": (
            len(conditions) - counters["skipped"]
        ),
        **counters,
        "mean_wall_runtime_seconds": (
            round(
                mean_or_none(planner_runtimes),
                6,
            )
            if planner_runtimes
            else None
        ),
        "total_batch_runtime_seconds": round(
            batch_runtime,
            6,
        ),
        "runs_per_condition": (
            arguments.runs_per_condition
        ),
        "seed_start": arguments.seed_start,
        "planner": (
            arguments.planner
            or "ENHSP default"
        ),
        "timeout_seconds": arguments.timeout,
    }

    summary_path = results_path.with_suffix(
        ".summary.json"
    )

    summary_path.write_text(
        json.dumps(summary, indent=2),
        encoding="utf-8",
    )

    print()
    print(json.dumps(summary, indent=2))

    return 0


if __name__ == "__main__":
    sys.exit(main())
