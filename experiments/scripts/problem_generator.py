#!/usr/bin/env python3
"""
Generate reproducible planetary-rover PDDL+ problems.

Two models are supported:

- original: instantaneous movement
- timed: movement represented by an action, process, and arrival event
"""

from __future__ import annotations

import argparse
import json
import math
import random
import sys
from pathlib import Path
from typing import Any


def load_config(config_path: Path) -> dict[str, Any]:
    """Load the experiment configuration."""

    if not config_path.is_file():
        raise FileNotFoundError(
            f"Configuration file not found: {config_path}"
        )

    with config_path.open("r", encoding="utf-8") as config_file:
        return json.load(config_file)


def format_number(value: float | int) -> str:
    """Format a number for use in PDDL."""

    numeric_value = float(value)

    if numeric_value.is_integer():
        return str(int(numeric_value))

    return f"{numeric_value:.3f}".rstrip("0").rstrip(".")


def calculate_memory_capacity(
    dataset_sizes: list[int],
    memory_ratio: float,
) -> int:
    """
    Calculate memory capacity relative to total data volume.

    Every dataset is guaranteed to fit individually.
    """

    total_size = sum(dataset_sizes)
    largest_dataset = max(dataset_sizes)

    return max(
        largest_dataset,
        math.ceil(total_size * memory_ratio),
    )


def create_map(
    site_names: list[str],
    travel_time_per_edge: float,
    timed_movement: bool,
) -> tuple[list[str], list[str]]:
    """Create a bidirectional linear map and travel-time values."""

    locations = ["base", *site_names]
    connection_lines: list[str] = []
    travel_time_lines: list[str] = []

    for index in range(len(locations) - 1):
        first = locations[index]
        second = locations[index + 1]

        connection_lines.extend(
            [
                f"    (connected {first} {second})",
                f"    (connected {second} {first})",
            ]
        )

        if timed_movement:
            formatted_time = format_number(
                travel_time_per_edge
            )

            travel_time_lines.extend(
                [
                    (
                        f"    (= (travel-time {first} {second}) "
                        f"{formatted_time})"
                    ),
                    (
                        f"    (= (travel-time {second} {first}) "
                        f"{formatted_time})"
                    ),
                ]
            )

    return connection_lines, travel_time_lines


def choose_safe_indices(
    dataset_count: int,
    safe_fraction: float,
    rng: random.Random,
) -> set[int]:
    """Choose a controlled number of theoretically safe datasets."""

    target_safe_count = int(
        dataset_count * safe_fraction + 0.5
    )

    target_safe_count = max(
        0,
        min(dataset_count, target_safe_count),
    )

    indices = list(range(dataset_count))
    rng.shuffle(indices)

    return set(indices[:target_safe_count])


def generate_problem(
    config: dict[str, Any],
    dataset_count: int,
    memory_level: str,
    corruption_level: str,
    seed: int,
    model: str = "original",
) -> tuple[str, dict[str, Any]]:
    """Generate one PDDL+ problem and its metadata."""

    if dataset_count not in config["dataset_counts"]:
        raise ValueError(
            f"Unsupported dataset count: {dataset_count}"
        )

    if memory_level not in config["memory_ratios"]:
        raise ValueError(
            f"Unsupported memory level: {memory_level}"
        )

    margin_options = config["corruption_margin_choices"]

    if corruption_level not in margin_options:
        raise ValueError(
            f"Unsupported corruption level: {corruption_level}"
        )

    if model not in {"original", "timed"}:
        raise ValueError(
            "Model must be either 'original' or 'timed'."
        )

    timed_movement = model == "timed"

    size_min = int(config["dataset_size"]["min"])
    size_max = int(config["dataset_size"]["max"])

    encoding_min = int(config["encoding_time"]["min"])
    encoding_max = int(config["encoding_time"]["max"])

    encoding_rate = float(config["encoding_rate"])
    corruption_rate = float(config["corruption_rate"])

    travel_time_per_edge = float(
        config["travel_time_per_edge"]
    )

    mission_rng = random.Random(seed)
    condition_rng = random.Random(seed + 1_000_003)

    dataset_sizes = [
        mission_rng.randint(size_min, size_max)
        for _ in range(dataset_count)
    ]

    encoding_times = [
        mission_rng.randint(encoding_min, encoding_max)
        for _ in range(dataset_count)
    ]

    corruption_margin_choices = [
        float(value)
        for value in margin_options[corruption_level]
    ]

    dataset_names = [
        f"data{index}"
        for index in range(1, dataset_count + 1)
    ]

    site_names = [
        f"site{index}"
        for index in range(1, dataset_count + 1)
    ]

    memory_ratio = float(
        config["memory_ratios"][memory_level]
    )

    memory_capacity = calculate_memory_capacity(
        dataset_sizes,
        memory_ratio,
    )

    model_label = "timed" if timed_movement else "original"

    problem_name = (
        f"rover-{model_label}"
        f"-n{dataset_count}"
        f"-mem-{memory_level}"
        f"-corr-{corruption_level}"
        f"-seed-{seed}"
    )

    domain_name = (
        "memory-rover-experimental"
        if timed_movement
        else "memory-rover-plus"
    )

    connection_lines, travel_time_lines = create_map(
        site_names=site_names,
        travel_time_per_edge=travel_time_per_edge,
        timed_movement=timed_movement,
    )

    data_location_lines = [
        f"    (data-at {dataset} {site})"
        for dataset, site in zip(
            dataset_names,
            site_names,
        )
    ]

    numeric_lines: list[str] = [
        "    (= (used-memory rover1) 0)",
        (
            "    (= (memory-capacity rover1) "
            f"{memory_capacity})"
        ),
    ]

    if timed_movement:
        numeric_lines.append(
            "    (= (travel-progress rover1) 0)"
        )
        numeric_lines.extend(travel_time_lines)

    dataset_metadata: list[dict[str, Any]] = []

    for index, dataset_name in enumerate(dataset_names):
        dataset_size = dataset_sizes[index]
        encoding_time = encoding_times[index]

        if timed_movement:
            minimum_return_time = (
                (index + 1) * travel_time_per_edge
            )
        else:
            minimum_return_time = 0.0

        earliest_direct_offload_time = max(
            float(encoding_time),
            minimum_return_time,
        )

        margin = condition_rng.choice(
            corruption_margin_choices
        )

        theoretically_safe = margin > 0

        loss_time = max(
            0.5,
            earliest_direct_offload_time + margin,
        )

        encoding_required = (
            encoding_time * encoding_rate
        )

        corruption_limit = (
            loss_time * corruption_rate
        )

        numeric_lines.extend(
            [
                (
                    f"    (= (data-size {dataset_name}) "
                    f"{format_number(dataset_size)})"
                ),
                f"    (= (corruption {dataset_name}) 0)",
                (
                    f"    (= (corruption-limit {dataset_name}) "
                    f"{format_number(corruption_limit)})"
                ),
                (
                    f"    (= (corruption-rate {dataset_name}) "
                    f"{format_number(corruption_rate)})"
                ),
                (
                    f"    (= (encoding-progress "
                    f"{dataset_name}) 0)"
                ),
                (
                    f"    (= (encoding-required "
                    f"{dataset_name}) "
                    f"{format_number(encoding_required)})"
                ),
                (
                    f"    (= (encoding-rate {dataset_name}) "
                    f"{format_number(encoding_rate)})"
                ),
            ]
        )

        dataset_metadata.append(
            {
                "dataset": dataset_name,
                "site": site_names[index],
                "size": dataset_size,
                "encoding_time": encoding_time,
                "minimum_return_time": minimum_return_time,
                "earliest_direct_offload_time": (
                    earliest_direct_offload_time
                ),
                "corruption_margin": margin,
                "loss_time": loss_time,
                "theoretically_safe": theoretically_safe,
            }
        )

    goal_lines: list[str] = []

    for dataset_name in dataset_names:
        goal_lines.extend(
            [
                f"      (offloaded {dataset_name})",
                f"      (not (lost {dataset_name}))",
            ]
        )

    problem_text = "\n".join(
        [
            f"(define (problem {problem_name})",
            f"  (:domain {domain_name})",
            "",
            "  (:objects",
            "    rover1 - rover",
            f"    base {' '.join(site_names)} - location",
            f"    {' '.join(dataset_names)} - data",
            "  )",
            "",
            "  (:init",
            "    (at rover1 base)",
            "    (base base)",
            *connection_lines,
            *data_location_lines,
            *numeric_lines,
            "  )",
            "",
            "  (:goal",
            "    (and",
            *goal_lines,
            "    )",
            "  )",
            "",
            "  (:metric minimize (total-time))",
            ")",
            "",
        ]
    )

    safe_dataset_count = sum(
        dataset["theoretically_safe"]
        for dataset in dataset_metadata
    )

    metadata = {
        "instance_id": problem_name,
        "model": model_label,
        "seed": seed,
        "dataset_count": dataset_count,
        "memory_level": memory_level,
        "memory_ratio": memory_ratio,
        "memory_capacity": memory_capacity,
        "total_dataset_size": sum(dataset_sizes),
        "corruption_level": corruption_level,
        "travel_time_per_edge": (
            travel_time_per_edge
            if timed_movement
            else 0.0
        ),
        "safe_dataset_count": safe_dataset_count,
        "unsafe_dataset_count": (
            dataset_count - safe_dataset_count
        ),
        "datasets": dataset_metadata,
    }

    return problem_text, metadata


def parse_arguments() -> argparse.Namespace:
    """Read command-line arguments."""

    parser = argparse.ArgumentParser(
        description="Generate one rover PDDL+ problem."
    )

    parser.add_argument(
        "--datasets",
        type=int,
        required=True,
    )

    parser.add_argument(
        "--memory",
        choices=["low", "medium", "high"],
        required=True,
    )

    parser.add_argument(
        "--corruption",
        choices=["low", "medium", "high"],
        required=True,
    )

    parser.add_argument(
        "--seed",
        type=int,
        required=True,
    )

    parser.add_argument(
        "--model",
        choices=["original", "timed"],
        default="original",
    )

    parser.add_argument(
        "--config",
        type=Path,
        default=Path(
            "experiments/config/experiment_config.json"
        ),
    )

    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path(
            "experiments/generated_problems"
        ),
    )

    return parser.parse_args()


def main() -> int:
    """Generate and save one problem."""

    arguments = parse_arguments()

    try:
        config = load_config(arguments.config)

        problem_text, metadata = generate_problem(
            config=config,
            dataset_count=arguments.datasets,
            memory_level=arguments.memory,
            corruption_level=arguments.corruption,
            seed=arguments.seed,
            model=arguments.model,
        )

        arguments.output_dir.mkdir(
            parents=True,
            exist_ok=True,
        )

        instance_id = metadata["instance_id"]

        problem_path = (
            arguments.output_dir
            / f"{instance_id}.pddl"
        )

        metadata_path = (
            arguments.output_dir
            / f"{instance_id}.json"
        )

        problem_path.write_text(
            problem_text,
            encoding="utf-8",
        )

        metadata_path.write_text(
            json.dumps(metadata, indent=2),
            encoding="utf-8",
        )

        print(
            json.dumps(
                {
                    "status": "generated",
                    "problem_file": str(problem_path),
                    "metadata_file": str(metadata_path),
                    **metadata,
                },
                indent=2,
            )
        )

        return 0

    except Exception as error:
        print(
            json.dumps(
                {
                    "status": "generation_error",
                    "error": (
                        f"{type(error).__name__}: {error}"
                    ),
                },
                indent=2,
            )
        )
        return 1


if __name__ == "__main__":
    sys.exit(main())
