"""Run pytest under Coverage.py using ``pyproject.toml`` (no ``pytest-cov`` plugin).

``pytest`` alone stays free of ``--cov`` flags so any environment with pytest works.
This module is invoked via the ``texas-holdem-gym-test`` console script and CI.
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path


def _find_repo_root() -> Path:
    """Directory that contains ``pyproject.toml`` and ``src/texasholdemgym`` (editable layout)."""
    for start in (Path.cwd(), Path(__file__).resolve().parent):
        for p in [start, *start.parents]:
            if (p / "pyproject.toml").is_file() and (p / "src" / "texasholdemgym").is_dir():
                return p
    return Path.cwd()


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    parser = argparse.ArgumentParser(
        prog="texas-holdem-gym-test",
        description="Run pytest with coverage + terminal report (pyproject.toml [tool.coverage]).",
    )
    parser.add_argument("--html", action="store_true", help="After the report, write htmlcov/ for browsing.")
    ns, pytest_args = parser.parse_known_args(argv)

    root = _find_repo_root()
    os.chdir(root)

    exe = sys.executable
    run = subprocess.run([exe, "-m", "coverage", "run", "-m", "pytest", "-q", *pytest_args])
    if run.returncode != 0:
        return int(run.returncode)

    rep = subprocess.run([exe, "-m", "coverage", "report", "-m", "--skip-covered"])
    if rep.returncode != 0:
        return int(rep.returncode)

    if ns.html:
        html = subprocess.run([exe, "-m", "coverage", "html"])
        return int(html.returncode)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
