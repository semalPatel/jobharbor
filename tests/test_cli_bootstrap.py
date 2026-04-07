from pathlib import Path

from jobharbor.cli import main


def test_jobharbor_bootstrap_creates_workspace_files(tmp_path: Path) -> None:
    exit_code = main(["bootstrap", "--home", str(tmp_path)])

    assert exit_code == 0
    assert (tmp_path / "cv.md").exists()
    assert (tmp_path / "config" / "profile.yml").exists()
    assert (tmp_path / "portals.yml").exists()
    assert (tmp_path / "data" / "applications.md").exists()
    assert (tmp_path / "data" / "pipeline.md").exists()
