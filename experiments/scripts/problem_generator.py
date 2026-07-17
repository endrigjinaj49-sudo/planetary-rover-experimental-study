#!/usr/bin/env python3
"""
Generate reproducible PDDL+ planetary-rover problem instances.

The generated missions vary:

- number of datasets;
- rover memory pressure;
- corruption severity;
- random seed.

Only the problem files change. The original PDDL+ domain remains unchanged.
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
    """Load and validate the JSON experiment configuration."""

    if not config_path.is_file():
        raise FileNotFoundError(
            f"Configuration file not found: {config_path}"
        )

    with config_path.open("r", encoding="utf-8") as config_file:
        return json.load(config_file)


def format_number(value: float | int) -> str:
    """Format numbers cleanly for PDDL."""

    numeric_value = float(value)

    if numeric_value.is_integer():
        return str(int(numeric_value))

    return f"{numeric_value:.3f}".rstrip("0").rstrip(".")


def calculate_memory_capacity(
    dataset_sizes: list[int],
    memory_ratio: float,
) -> int:
    """
    Calculate memory capacity relative to the total data volume.

    Capacity is always at least as large as the largest individual
    dataset. Therefore, every dataset can fit individually.
    """

    total_size = sum(dataset_sizes)
    largest_dataset = max(dataset_sizes)

    proportional_capacity = math.ceil(total_size * memory_ratio)

    return max(largest_dataset, proportional_capacity)


def create_connections(site_names: list[str]) -> list[str]:
    """Create a bidirectional linear map: base <-> site1 <-> site2..."""

    locations = ["base", *site_names]
    connections: list[str] = []

    for index in range(len(locations) - 1):
        first = locations[index]
        second = locations[index + 1]

        connections.append(f"    (connected {first} {second})")
        connections.append(f"    (connected {second} {first})")

    return connections


def generate_problem(
    config: dict[str, Any],
    dataset_count: int,
    memory_level: str,
    corruption_level: str,
    seed: int,
) -> tuple[str, dict[str, Any]]:
    """Generate the PDDL+ problem and its experimental metadata."""

    dataset_counts = config["dataset_counts"]

    if dataset_count not in dataset_counts:
        raise ValueError(
            f"Dataset count must be one of {dataset_counts}; "
            f"received {dataset_count}."
        )

    memory_ratios = config["memory_ratios"]

    if memory_level not in memory_ratios:
        raise ValueError(
            f"Unknown memory level: {memory_level}"
        )

    margin_options = config["corruption_margin_choices"]

    if corruption_level not in margin_options:
        raise ValueError(
            f"Unknown corruption level: {corruption_level}"
        )

    size_min = int(config["dataset_size"]["min"])
    size_max = int(config["dataset_size"]["max"])

    encoding_min = int(config["encoding_time"]["min"])
    encoding_max = int(config["encoding_time"]["max"])

    encoding_rate = float(config["encoding_rate"])
    corruption_rate = float(config["corruption_rate"])

    # Separate random streams keep the basic mission identical across
    # memory and corruption conditions when the same seed is used.
    mission_rng = random.Random(seed)
    corruption_rng = random.Random(seed + 1_000_003)

    dataset_sizes = [
        mission_rng.randint(size_min, size_max)
        for _ in range(dataset_count)
    ]

    encoding_times = [
        mission_rng.randint(encoding_min, encoding_max)
        for _ in range(dataset_count)
    ]

    selected_margins: list[int] = []

    corruption_choices = margin_options[corruption_level]

    for _ in range(dataset_count):
        choice_index = corruption_rng.randrange(
            len(corruption_choices)
        )
        selected_margins.append(
            int(corruption_choices[choice_index])
        )

    loss_times = [
        max(1, encoding_time + margin)
        for encoding_time, margin in zip(
            encoding_times,
            selected_margins,
        )
    ]

    memory_ratio = float(memory_ratios[memory_level])

    memory_capacity = calculate_memory_capacity(
        dataset_sizes,
        memory_ratio,
    )

    site_names = [
        f"site{index}"
        for index in range(1, dataset_count + 1)
    ]

    data_names = [
        f"data{index}"
        for index in range(1, dataset_count + 1)
    ]

    problem_name = (
        f"rover-n{dataset_count}"
        f"-mem-{memory_level}"
        f"-corr-{corruption_level}"
        f"-seed-{seed}"
    )

    connection_lines = create_connections(site_names)

    data_location_lines = [
        f"    (data-at {data_name} {site_name})"
        for data_name, site_name in zip(
            data_names,
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

    dataset_metadata: list[dict[str, Any]] = []

    for index, data_name in enumerate(data_names):
        dataset_size = dataset_sizes[index]
        encoding_time = encoding_times[index]
        corruption_margin = selected_margins[index]
        loss_time = loss_times[index]

        encoding_required = encoding_time * encoding_rate
        corruption_limit = loss_time * corruption_rate

        numeric_lines.extend(
            [
                (
                    f"    (= (data-size {data_name}) "
                    f"{format_number(dataset_size)})"
                ),
                (
                    f"    (= (corruption {data_name}) 0)"
                ),
                (
                    f"    (= (corruption-limit {data_name}) "
                    f"{format_number(corruption_limit)})"
                ),
                (
                    f"    (= (corruption-rate {data_name}) "
                    f"{format_number(corruption_rate)})"
                ),
                (
                    f"    (= (encoding-progress {data_name}) 0)"
                ),
                (
                    f"    (= (encoding-required {data_name}) "
                    f"{format_number(encoding_required)})"
                ),
                (
                    f"    (= (encoding-rate {data_name}) "
                    f"{format_number(encoding_rate)})"
                ),
            ]
        )

        dataset_metadata.append(
            {
                "dataset": data_name,
                "site": site_names[index],
                "size": dataset_size,
                "encoding_time": encoding_time,
                "corruption_margin": corruption_margin,
                "loss_time": loss_time,
                "theoretically_safe": loss_time > encoding_time,
            }
        )

    goal_lines: list[str] = []

    for data_name in data_names:
        goal_lines.append(f"      (offloaded {data_name})")
        goal_lines.append(f"      (not (lost {data_name}))")

    problem_text = "\n".join(
        [
            f"(define (problem {problem_name})",
            "  (:domain memory-rover-plus)",
            "",
            "  (:objects",
            "    rover1 - rover",
            f"    base {' '.join(site_names)} - location",
            f"    {' '.join(data_names)} - data",
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

    metadata = {
        "instance_id": problem_name,
        "seed": seed,
        "dataset_count": dataset_count,
        "memory_level": memory_level,
        "memory_ratio": memory_ratio,
        "memory_capacity": memory_capacity,
        "total_dataset_size": sum(dataset_sizes),
        "corruption_level": corruption_level,
        "safe_dataset_count": sum(
            dataset["theoretically_safe"]
            for dataset in dataset_metadata
        ),
        "unsafe_dataset_count": sum(
            not dataset["theoretically_safe"]
            for dataset in dataset_metadata
        ),
        "datasets": dataset_metadata,
    }

    return problem_text, metadata


def parse_arguments() -> argparse.Namespace:
    """Read command-line arguments."""

    parser = argparse.ArgumentParser(
        description="Generate one rover PDDL+ problem instance."
    )

    parser.add_argument(
        "--datasets",
        type=int,
        required=True,
        help="Number of scientific datasets.",
    )

    parser.add_argument(
        "--memory",
        choices=["low", "medium", "high"],
        required=True,
        help="Memory-pressure level.",
    )

    parser.add_argument(
        "--corruption",
        choices=["low", "medium", "high"],
        required=True,
        help="Corruption-severity level.",
    )

    parser.add_argument(
        "--seed",
        type=int,
        required=True,
        help="Random mission seed.",
    )

    parser.add_argument(
        "--config",
        type=Path,
        default=Path(
            "experiments/config/experiment_config.json"
        ),
        help="Path to the experiment configuration.",
    )

    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path(
            "experiments/generated_problems"
        ),
        help="Directory for generated PDDL and metadata files.",
    )

    return parser.parse_args()


def main() -> int:
    """Generate and save one reproducible problem instance."""

    arguments = parse_arguments()

    try:
        config = load_config(arguments.config)

        problem_text, metadata = generate_problem(
            config=config,
            dataset_count=arguments.datasets,
            memory_level=arguments.memory,
            corruption_level=arguments.corruption,
            seed=arguments.seed,
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

    except (
        FileNotFoundError,
        ValueError,
        KeyError,
        json.JSONDecodeError,
    ) as error:
        print(
            json.dumps(
                {
                    "status": "generation_error",
                    "error": str(error),
                },
                indent=2,
            )
        )
        return 1


if __name__ == "__main__":
    sys.exit(main())
