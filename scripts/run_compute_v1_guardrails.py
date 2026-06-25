from __future__ import annotations

import subprocess
import sys
from pathlib import Path

GUARDRAIL_TESTS = [
    "tests/test_compute_v1_benchmark.py",
    "tests/test_compute_v1_equivalence.py",
    "tests/test_compute_v1_runtime_estimator.py",
]


def main() -> int:
    repo_root = Path(__file__).resolve().parents[1]
    command = [sys.executable, "-m", "pytest", *GUARDRAIL_TESTS, "-q"]
    print("[compute_v1_guardrails] running:", " ".join(command))
    completed = subprocess.run(command, cwd=repo_root)
    return completed.returncode


if __name__ == "__main__":
    raise SystemExit(main())
