import pytest

from jobharbor.models import Application, ApplicationStatus
from jobharbor.tracker import set_tracker_status, tracker_status_for, validate_tracker_status
from sqlmodel import Session, SQLModel, create_engine


def test_maps_current_application_statuses_to_tracker_labels() -> None:
    assert tracker_status_for(Application(job_id=1, status=ApplicationStatus.drafting)) == "Drafting"
    assert tracker_status_for(Application(job_id=1, status=ApplicationStatus.ready_for_review)) == "Evaluated"
    assert tracker_status_for(Application(job_id=1, status=ApplicationStatus.submitted)) == "Applied"
    assert tracker_status_for(Application(job_id=1, status=ApplicationStatus.failed)) == "Failed"
    assert tracker_status_for(Application(job_id=1, status=ApplicationStatus.abandoned)) == "Discarded"


def test_validate_tracker_status_rejects_unknown_label() -> None:
    with pytest.raises(ValueError, match="unsupported tracker status"):
        validate_tracker_status("Submitted")


def test_setting_tracker_status_does_not_change_application_status() -> None:
    engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(engine)

    with Session(engine) as session:
        application = Application(job_id=1, status=ApplicationStatus.ready_for_review)
        session.add(application)
        session.commit()
        session.refresh(application)

        updated = set_tracker_status(session, application.id, "Interview")

    assert updated.status is ApplicationStatus.ready_for_review
    assert updated.tracker_status == "Interview"
