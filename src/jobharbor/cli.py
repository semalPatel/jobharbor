from __future__ import annotations

import argparse
from pathlib import Path
from typing import Sequence

from jobharbor.config import Settings
from jobharbor.workspace import WorkspacePaths, bootstrap_workspace


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="jobharbor")
    subcommands = parser.add_subparsers(dest="command", required=True)

    bootstrap = subcommands.add_parser("bootstrap", help="create workspace files")
    bootstrap.add_argument(
        "--home",
        type=Path,
        default=None,
        help="workspace root; defaults to JOBHARBOR_HOME or ./workspace",
    )

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "bootstrap":
        settings = Settings(jobharbor_home=args.home) if args.home else Settings()
        result = bootstrap_workspace(settings)
        paths = WorkspacePaths.from_settings(settings)
        print(f"Bootstrapped workspace at {paths.root}")
        print(f"Created {len(result.created)} path(s); preserved {len(result.preserved)}.")
        return 0
    raise SystemExit(f"unsupported command: {args.command}")


if __name__ == "__main__":
    raise SystemExit(main())
