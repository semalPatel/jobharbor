from pathlib import Path

from jobharbor.config import Settings
from jobharbor.workspace import WorkspaceBootstrapper, WorkspacePaths


def test_workspace_paths_resolve_under_explicit_home(tmp_path: Path) -> None:
    paths = WorkspacePaths.from_settings(Settings(jobharbor_home=tmp_path))

    assert paths.cv_md == tmp_path / "cv.md"
    assert paths.profile_yml == tmp_path / "config" / "profile.yml"
    assert paths.portals_yml == tmp_path / "portals.yml"
    assert paths.applications_md == tmp_path / "data" / "applications.md"
    assert paths.pipeline_md == tmp_path / "data" / "pipeline.md"
    assert paths.scan_history_tsv == tmp_path / "data" / "scan-history.tsv"
    assert paths.reports_dir == tmp_path / "reports"
    assert paths.output_dir == tmp_path / "output"
    assert paths.jds_dir == tmp_path / "jds"


def test_bootstrap_creates_expected_workspace_paths(tmp_path: Path) -> None:
    paths = WorkspacePaths(tmp_path)
    result = WorkspaceBootstrapper(paths).bootstrap()

    assert paths.cv_md.exists()
    assert paths.profile_yml.exists()
    assert paths.portals_yml.exists()
    assert paths.applications_md.exists()
    assert paths.pipeline_md.exists()
    assert paths.scan_history_tsv.exists()
    assert paths.reports_dir.is_dir()
    assert paths.output_dir.is_dir()
    assert paths.jds_dir.is_dir()
    assert paths.prompts_dir.is_dir()
    assert paths.templates_dir.is_dir()
    assert paths.states_yml.exists()
    assert paths.cv_md in result.created


def test_bootstrap_does_not_overwrite_existing_files(tmp_path: Path) -> None:
    paths = WorkspacePaths(tmp_path)
    paths.config_dir.mkdir(parents=True)
    paths.profile_yml.write_text("name: Existing User\n", encoding="utf-8")

    result = WorkspaceBootstrapper(paths).bootstrap()

    assert paths.profile_yml.read_text(encoding="utf-8") == "name: Existing User\n"
    assert paths.profile_yml in result.preserved
