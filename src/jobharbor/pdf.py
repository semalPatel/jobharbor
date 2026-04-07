from __future__ import annotations

import re
from pathlib import Path

from sqlmodel import Session

from jobharbor.models import Application, Artifact, Evaluation, Job
from jobharbor.reports import evaluation_result_from_model


class PdfRenderer:
    def render(
        self,
        *,
        application: Application,
        evaluation: Evaluation,
        job: Job,
        cv_text: str,
        output_dir: Path,
    ) -> Path:
        output_dir.mkdir(parents=True, exist_ok=True)
        filename = f"cv-{application.id:03d}-{_slug(job.company or job.source)}.pdf"
        path = output_dir / filename
        result = evaluation_result_from_model(evaluation)
        text = "\n".join(
            [
                f"Candidate CV for {result.company} - {result.role}",
                "",
                f"Score: {result.score}/5",
                f"Recommendation: {result.recommendation}",
                "",
                "Profile CV",
                cv_text.strip(),
            ]
        )
        path.write_bytes(_minimal_pdf(text))
        return path


class PdfArtifactService:
    def __init__(self, *, session: Session, output_dir: Path, renderer: PdfRenderer | None = None) -> None:
        self._session = session
        self._output_dir = output_dir
        self._renderer = renderer or PdfRenderer()

    def render_for_application(self, *, application_id: int, cv_text: str = "") -> Artifact | None:
        application = self._session.get(Application, application_id)
        if application is None:
            raise LookupError(f"application not found: id={application_id}")
        evaluation = self._latest_evaluation(application_id)
        if evaluation is None:
            raise LookupError(f"evaluation not found for application_id={application_id}")
        job = self._session.get(Job, application.job_id)
        if job is None:
            raise LookupError(f"job not found: id={application.job_id}")
        try:
            path = self._renderer.render(
                application=application,
                evaluation=evaluation,
                job=job,
                cv_text=cv_text,
                output_dir=self._output_dir,
            )
        except Exception:
            self._session.rollback()
            return None
        artifact = Artifact(application_id=application.id, kind="pdf", path=str(path))
        self._session.add(artifact)
        self._session.commit()
        self._session.refresh(artifact)
        return artifact

    def _latest_evaluation(self, application_id: int) -> Evaluation | None:
        from sqlmodel import select

        stmt = (
            select(Evaluation)
            .where(Evaluation.application_id == application_id)
            .order_by(Evaluation.id.desc())
            .limit(1)
        )
        return self._session.exec(stmt).first()


def _minimal_pdf(text: str) -> bytes:
    escaped = _pdf_escape(_ascii(text))
    stream = f"BT /F1 12 Tf 72 720 Td ({escaped}) Tj ET"
    objects = [
        "1 0 obj << /Type /Catalog /Pages 2 0 R >> endobj",
        "2 0 obj << /Type /Pages /Kids [3 0 R] /Count 1 >> endobj",
        "3 0 obj << /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >> endobj",
        "4 0 obj << /Type /Font /Subtype /Type1 /BaseFont /Helvetica >> endobj",
        f"5 0 obj << /Length {len(stream)} >> stream\n{stream}\nendstream endobj",
    ]
    body = "%PDF-1.4\n" + "\n".join(objects) + "\ntrailer << /Root 1 0 R >>\n%%EOF\n"
    return body.encode("ascii", errors="ignore")


def _ascii(value: str) -> str:
    return value.encode("ascii", errors="ignore").decode("ascii")


def _pdf_escape(value: str) -> str:
    return value.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)").replace("\n", " ")[:1500]


def _slug(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug or "unknown"
