from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from shutil import copyfile

from jobharbor.config import Settings


@dataclass(frozen=True)
class WorkspacePaths:
    root: Path

    @classmethod
    def from_settings(cls, settings: Settings | None = None) -> "WorkspacePaths":
        return cls((settings or Settings()).jobharbor_home)

    @property
    def cv_md(self) -> Path:
        return self.root / "cv.md"

    @property
    def config_dir(self) -> Path:
        return self.root / "config"

    @property
    def profile_yml(self) -> Path:
        return self.config_dir / "profile.yml"

    @property
    def portals_yml(self) -> Path:
        return self.root / "portals.yml"

    @property
    def data_dir(self) -> Path:
        return self.root / "data"

    @property
    def applications_md(self) -> Path:
        return self.data_dir / "applications.md"

    @property
    def pipeline_md(self) -> Path:
        return self.data_dir / "pipeline.md"

    @property
    def scan_history_tsv(self) -> Path:
        return self.data_dir / "scan-history.tsv"

    @property
    def reports_dir(self) -> Path:
        return self.root / "reports"

    @property
    def output_dir(self) -> Path:
        return self.root / "output"

    @property
    def jds_dir(self) -> Path:
        return self.root / "jds"

    @property
    def prompts_dir(self) -> Path:
        return self.root / "prompts"

    @property
    def templates_dir(self) -> Path:
        return self.root / "templates"

    @property
    def states_yml(self) -> Path:
        return self.config_dir / "states.yml"


@dataclass(frozen=True)
class BootstrapResult:
    created: tuple[Path, ...]
    preserved: tuple[Path, ...]


class WorkspaceBootstrapper:
    def __init__(
        self,
        paths: WorkspacePaths,
        template_dir: Path | None = None,
    ) -> None:
        self.paths = paths
        self.template_dir = template_dir or default_template_dir()

    def bootstrap(self) -> BootstrapResult:
        created: list[Path] = []
        preserved: list[Path] = []

        for directory in self._directories():
            if directory.exists():
                preserved.append(directory)
            else:
                directory.mkdir(parents=True, exist_ok=True)
                created.append(directory)

        for source_name, target in self._template_targets().items():
            source = self.template_dir / source_name
            if target.exists():
                preserved.append(target)
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            copyfile(source, target)
            created.append(target)

        for target, contents in self._generated_targets().items():
            if target.exists():
                preserved.append(target)
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(contents, encoding="utf-8")
            created.append(target)

        return BootstrapResult(tuple(created), tuple(preserved))

    def _directories(self) -> tuple[Path, ...]:
        return (
            self.paths.root,
            self.paths.config_dir,
            self.paths.data_dir,
            self.paths.reports_dir,
            self.paths.output_dir,
            self.paths.jds_dir,
            self.paths.prompts_dir,
            self.paths.templates_dir,
        )

    def _template_targets(self) -> dict[str, Path]:
        return {
            "portals.example.yml": self.paths.portals_yml,
            "profile.example.yml": self.paths.profile_yml,
            "applications.md": self.paths.applications_md,
            "pipeline.md": self.paths.pipeline_md,
            "states.yml": self.paths.states_yml,
        }

    def _generated_targets(self) -> dict[Path, str]:
        return {
            self.paths.cv_md: "# CV\n\nAdd your master CV here.\n",
            self.paths.scan_history_tsv: (
                "url\tfirst_seen\tsource\ttitle\tcompany\tstatus\treason\n"
            ),
            self.paths.prompts_dir / "evaluation.md": (
                "Evaluate the job against the candidate profile and return only JSON matching\n"
                "Jobharbor's EvaluationResult schema. Do not submit or apply to the job.\n"
            ),
        }


def default_template_dir() -> Path:
    return Path(__file__).resolve().parents[2] / "templates"


def bootstrap_workspace(settings: Settings | None = None) -> BootstrapResult:
    paths = WorkspacePaths.from_settings(settings)
    return WorkspaceBootstrapper(paths).bootstrap()


__all__ = [
    "BootstrapResult",
    "WorkspaceBootstrapper",
    "WorkspacePaths",
    "bootstrap_workspace",
    "default_template_dir",
]
