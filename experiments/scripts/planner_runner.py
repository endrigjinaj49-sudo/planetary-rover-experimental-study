#!/usr/bin/env python3
"""
Run ENHSP on one PDDL/PDDL+ problem and extract basic experiment metrics.

This script uses only the Python standard library.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import time
from pathlib import Path
from typing import Any


PLAN_LINE_PATTERN = re.compile(
    r"^\s*(?P<timestamp>\d+(?:\.\d+)?):\s*(?P<content>.+?)\s*$"
)

PLAN_LENGTH_PATTERN = re.compile(
    r"Plan-Length\s*:\s*(\d+)",
    re.IGNORECASE,
)

ELAPSED_TIME_PATTERN = re.compile(
    r"Elapsed\s+Time\s*:\s*(\d+(?:\.\d+)?)",
    re.IGNORECASE,
)

WAIT_DURATION_PATTERN = re.compile(
    r"\[(\d+(?:\.\d+)?)\]"
)


def parse_enhsp_output(output_text: str) -> dict[str, Any]:
    """Extract status, plan information, and action counts from ENHSP output."""

    lower_output = output_text.lower()

    if "problem solved" in lower_output:
        status = "solved"
    elif (
        "problem unsolvable" in lower_output
        or "problem is unsolvable" in lower_output
        or "goal is unreachable" in lower_output
        or "goal not reachable" in lower_output
    ):
        status = "unsolvable"
    else:
        status = "unknown"

    actions: list[dict[str, Any]] = []
    waiting_periods: list[dict[str, float]] = []

    for line in output_text.splitlines():
        match = PLAN_LINE_PATTERN.match(line)

        if not match:
            continue

        timestamp = float(match.group("timestamp"))
        content = match.group("content").strip()
        content_lower = content.lower()

        if "waiting" in content_lower:
            duration_match = WAIT_DURATION_PATTERN.search(content)

            duration = (
                float(duration_match.group(1))
                if duration_match
                else 0.0
            )

            waiting_periods.append(
                {
                    "start_time": timestamp,
                    "duration": duration,
                    "end_time": timestamp + duration,
                }
            )

        elif content.startswith("(") and content.endswith(")"):
            actions.append(
                {
                    "timestamp": timestamp,
                    "action": content,
                }
            )

    reported_plan_length_match = PLAN_LENGTH_PATTERN.search(output_text)
    reported_elapsed_time_match = ELAPSED_TIME_PATTERN.search(output_text)

    reported_plan_length = (
        int(reported_plan_length_match.group(1))
        if reported_plan_length_match
        else None
    )

    reported_elapsed_time = (
        float(reported_elapsed_time_match.group(1))
        if reported_elapsed_time_match
        else None
    )

    # Calculate the temporal makespan directly from the plan.
    temporal_end_points: list[float] = [
        action["timestamp"] for action in actions
    ]

    temporal_end_points.extend(
        waiting["end_time"] for waiting in waiting_periods
    )

    plan_makespan = (
        max(temporal_end_points)
        if temporal_end_points
        else None
    )

    action_names = [action["action"].lower() for action in actions]

    return {
        "status": status,
        "solved": status == "solved",
        "reported_plan_length": reported_plan_length,
        "reported_elapsed_time": reported_elapsed_time,
        "plan_makespan": plan_makespan,
        "action_count": len(actions),
        "move_actions": sum(
            action.startswith("(move ")
            for action in action_names
        ),
        "collect_actions": sum(
            action.startswith("(collect-data ")
            for action in action_names
        ),
        "offload_actions": sum(
            action.startswith("(offload-data ")
            for action in action_names
        ),
        "waiting_periods": len(waiting_periods),
        "total_waiting_time": sum(
            waiting["duration"] for waiting in waiting_periods
        ),
        "actions": actions,
        "waits": waiting_periods,
    }


def run_enhsp(
    domain_path: Path,
    problem_path: Path,
    enhsp_jar: Path,
    output_path: Path,
    timeout_seconds: float,
    planner: str | None,
) -> dict[str, Any]:
    """Run ENHSP and return parsed metrics."""

    for path, description in (
        (domain_path, "Domain file"),
        (problem_path, "Problem file"),
        (enhsp_jar, "ENHSP JAR"),
    ):
        if not path.is_file():
            raise FileNotFoundError(
                f"{description} not found: {path}"
            )

    output_path.parent.mkdir(parents=True, exist_ok=True)

    command = [
        "java",
        "-jar",
        str(enhsp_jar),
        "-o",
        str(domain_path),
        "-f",
        str(problem_path),
    ]

    if planner:
        command.extend(["-planner", planner])

    start_time = time.perf_counter()

    try:
        process = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            check=False,
        )

        wall_runtime_seconds = time.perf_counter() - start_time

        combined_output = process.stdout

        if process.stderr:
            combined_output += "\n\n--- STDERR ---\n"
            combined_output += process.stderr

        output_path.write_text(
            combined_output,
            encoding="utf-8",
        )

        metrics = parse_enhsp_output(combined_output)

        metrics.update(
            {
                "domain": str(domain_path),
                "problem": str(problem_path),
                "output_file": str(output_path),
                "planner": planner or "ENHSP default",
                "timeout_seconds": timeout_seconds,
                "wall_runtime_seconds": round(
                    wall_runtime_seconds,
                    6,
                ),
                "return_code": process.returncode,
                "command": command,
            }
        )

        if metrics["status"] == "unknown" and process.returncode != 0:
            metrics["status"] = "error"
            metrics["solved"] = False

        return metrics

    except subprocess.TimeoutExpired as error:
        wall_runtime_seconds = time.perf_counter() - start_time

        partial_stdout = error.stdout or ""
        partial_stderr = error.stderr or ""

        if isinstance(partial_stdout, bytes):
            partial_stdout = partial_stdout.decode(
                errors="replace"
            )

        if isinstance(partial_stderr, bytes):
            partial_stderr = partial_stderr.decode(
                errors="replace"
            )

        timeout_output = (
            partial_stdout
            + "\n\n--- TIMEOUT STDERR ---\n"
            + partial_stderr
        )

        output_path.write_text(
            timeout_output,
            encoding="utf-8",
        )

        return {
            "status": "timeout",
            "solved": False,
            "domain": str(domain_path),
            "problem": str(problem_path),
            "output_file": str(output_path),
            "planner": planner or "ENHSP default",
            "timeout_seconds": timeout_seconds,
            "wall_runtime_seconds": round(
                wall_runtime_seconds,
                6,
            ),
            "return_code": 124,
            "reported_plan_length": None,
            "reported_elapsed_time": None,
            "plan_makespan": None,
            "action_count": 0,
            "move_actions": 0,
            "collect_actions": 0,
            "offload_actions": 0,
            "waiting_periods": 0,
            "total_waiting_time": 0.0,
            "actions": [],
            "waits": [],
            "command": command,
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
        description="Run ENHSP and parse its output."
    )

    parser.add_argument(
        "--domain",
        type=Path,
        required=True,
        help="Path to the PDDL domain file.",
    )

    parser.add_argument(
        "--problem",
        type=Path,
        required=True,
        help="Path to the PDDL problem file.",
    )

    parser.add_argument(
        "--output",
        type=Path,
        required=True,
        help="Path where the raw ENHSP output will be saved.",
    )

    parser.add_argument(
        "--enhsp-jar",
        type=Path,
        default=default_jar,
        help=f"Path to enhsp.jar. Default: {default_jar}",
    )

    parser.add_argument(
        "--planner",
        type=str,
        default=None,
        help="Optional ENHSP planner configuration, such as opt-hrmax.",
    )

    parser.add_argument(
        "--timeout",
        type=float,
        default=120.0,
        help="Maximum runtime in seconds. Default: 120.",
    )

    return parser.parse_args()


def main() -> int:
    """Program entry point."""

    arguments = parse_arguments()

    try:
        result = run_enhsp(
            domain_path=arguments.domain.expanduser().resolve(),
            problem_path=arguments.problem.expanduser().resolve(),
            enhsp_jar=arguments.enhsp_jar.expanduser().resolve(),
            output_path=arguments.output.expanduser().resolve(),
            timeout_seconds=arguments.timeout,
            planner=arguments.planner,
        )

    except (FileNotFoundError, OSError) as error:
        print(
            json.dumps(
                {
                    "status": "configuration_error",
                    "solved": False,
                    "error": str(error),
                },
                indent=2,
            )
        )
        return 1

    print(json.dumps(result, indent=2))

    # Unsolvable is a valid experimental result, not a program error.
    if result["status"] in {"solved", "unsolvable"}:
        return 0

    return 1


if __name__ == "__main__":
    sys.exit(main())
