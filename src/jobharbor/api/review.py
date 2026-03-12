from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlmodel import Session

from jobharbor.db import get_session
from jobharbor.models import ApplicationStatus
from jobharbor.repositories.application_repo import ApplicationRepository

router = APIRouter(prefix="/review", tags=["review"])


class ReviewApplicationResponse(BaseModel):
    id: int
    job_id: int
    status: ApplicationStatus


@router.get("/queue", response_model=list[ReviewApplicationResponse])
def get_review_queue(
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    session: Session = Depends(get_session),
) -> list[ReviewApplicationResponse]:
    repository = ApplicationRepository(session)
    applications = repository.list_ready_for_review(limit=limit, offset=offset)
    return [
        ReviewApplicationResponse(
            id=application.id,
            job_id=application.job_id,
            status=application.status,
        )
        for application in applications
    ]


@router.post("/{application_id}/submitted", response_model=ReviewApplicationResponse)
def mark_submitted(
    application_id: int,
    session: Session = Depends(get_session),
) -> ReviewApplicationResponse:
    repository = ApplicationRepository(session)
    try:
        application = repository.transition_status(application_id, ApplicationStatus.submitted)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    return ReviewApplicationResponse(
        id=application.id,
        job_id=application.job_id,
        status=application.status,
    )
