from __future__ import annotations

import argparse
from pathlib import Path
from typing import Sequence

from jobharbor.config import Settings
from jobharbor.db import get_engine, init_db
from jobharbor.pipeline_inbox import PipelineInboxService
from jobharbor.tracker import TrackerExportService, set_tracker_note, set_tracker_status
from jobharbor.workspace import WorkspacePaths, bootstrap_workspace
from sqlmodel import Session


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

    tracker = subcommands.add_parser("tracker", help="export or update the application tracker")
    tracker.add_argument("--status", default=None, help="filter exported rows by tracker status")
    tracker.add_argument("--company", default=None, help="filter exported rows by company")
    tracker.add_argument("--min-score", type=float, default=None, help="reserved for evaluation scores")
    tracker_subcommands = tracker.add_subparsers(dest="tracker_command")
    tracker_subcommands.add_parser("export", help="export data/applications.md")
    show = tracker_subcommands.add_parser("show", help="show one tracker row")
    show.add_argument("application_id", type=int)
    set_status = tracker_subcommands.add_parser("set-status", help="set lifecycle tracker status")
    set_status.add_argument("application_id", type=int)
    set_status.add_argument("status")
    note = tracker_subcommands.add_parser("note", help="replace tracker notes")
    note.add_argument("application_id", type=int)
    note.add_argument("note")

    pipeline = subcommands.add_parser("pipeline", help="import and process data/pipeline.md")
    pipeline.add_argument("--limit", type=int, default=None, help="maximum pending items to process")
    pipeline.add_argument("--sync-only", action="store_true", help="only import/export pipeline.md")

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
    if args.command == "tracker":
        settings = Settings()
        paths = WorkspacePaths.from_settings(settings)
        engine = get_engine(settings.database_url)
        init_db(engine=engine)
        with Session(engine) as session:
            service = TrackerExportService(session)
            tracker_command = args.tracker_command or "export"
            if tracker_command == "export":
                rows = service.export_applications(
                    paths.applications_md,
                    status=args.status,
                    company=args.company,
                    min_score=args.min_score,
                )
                print(f"Exported {len(rows)} tracker row(s) to {paths.applications_md}")
                return 0
            if tracker_command == "show":
                rows = [row for row in service.rows() if row.application_id == args.application_id]
                print(service.render(rows), end="")
                return 0
            if tracker_command == "set-status":
                set_tracker_status(session, args.application_id, args.status)
                service.export_applications(paths.applications_md)
                print(f"Updated tracker status for application {args.application_id}")
                return 0
            if tracker_command == "note":
                set_tracker_note(session, args.application_id, args.note)
                service.export_applications(paths.applications_md)
                print(f"Updated tracker note for application {args.application_id}")
                return 0
    if args.command == "pipeline":
        settings = Settings()
        paths = WorkspacePaths.from_settings(settings)
        engine = get_engine(settings.database_url)
        init_db(engine=engine)
        with Session(engine) as session:
            service = PipelineInboxService(session=session, path=paths.pipeline_md)
            if args.sync_only:
                imported = service.import_markdown()
                service.export_markdown()
                print(f"Synced {len(imported)} pipeline item(s)")
                return 0
            processed = service.process_pending(reports_dir=paths.reports_dir, limit=args.limit)
            TrackerExportService(session).export_applications(paths.applications_md)
            print(f"Processed {len(processed)} pipeline item(s)")
            return 0
    raise SystemExit(f"unsupported command: {args.command}")


if __name__ == "__main__":
    raise SystemExit(main())
