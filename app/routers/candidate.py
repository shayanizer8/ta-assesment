from typing import Any
from fastapi import APIRouter, Depends, HTTPException, Request, status, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import joinedload
from sqlalchemy.sql import func

from app.database import get_db
from app.models import Submission, SubmissionStatus, AuditLog, ActorType
from app.schemas import SubmissionSubmitRequest, CandidateSubmissionView, BriefResponse
from app.rate_limiter import limiter
from app.config import settings
from app.tasks import send_submission_confirmation_email, queue_file_antivirus_scan

router = APIRouter(prefix="/submissions", tags=["Candidate Submissions"])


@router.get("/{token}", response_model=CandidateSubmissionView)
@limiter.limit(settings.RATE_LIMIT_CANDIDATE)
async def get_candidate_submission(
    request: Request,
    token: str,
    db: AsyncSession = Depends(get_db)
):
    stmt = (
        select(Submission)
        .options(joinedload(Submission.assessment), joinedload(Submission.candidate))
        .where(Submission.private_token == token)
    )
    result = await db.execute(stmt)
    submission = result.scalar_one_or_none()

    if not submission:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Submission token not found or invalid"
        )

    return submission


@router.post("/{token}", response_model=CandidateSubmissionView)
@limiter.limit(settings.RATE_LIMIT_CANDIDATE)
async def submit_candidate_work(
    request: Request,
    token: str,
    body: SubmissionSubmitRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db)
):
    stmt = (
        select(Submission)
        .options(joinedload(Submission.assessment), joinedload(Submission.candidate))
        .where(Submission.private_token == token)
    )
    result = await db.execute(stmt)
    submission = result.scalar_one_or_none()

    if not submission:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Submission token not found or invalid"
        )

    # State Machine Guard: If submission has progressed past 'submitted', candidate cannot edit
    if submission.status in (SubmissionStatus.IN_REVIEW, SubmissionStatus.SCORED, SubmissionStatus.REJECTED):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Submission is currently in '{submission.status.value}' state and cannot be modified."
        )

    is_first_submission = (submission.status == SubmissionStatus.PENDING)
    action_type = "submission.created" if is_first_submission else "submission.updated"

    # Update submission fields
    submission.work_link = body.work_link
    submission.file_reference = body.file_reference
    submission.time_taken_minutes = body.time_taken_minutes
    submission.notes = body.notes
    submission.challenges = body.challenges
    submission.status = SubmissionStatus.SUBMITTED
    submission.submitted_at = func.now()

    # Create Audit Log
    audit_entry = AuditLog(
        actor_type=ActorType.CANDIDATE,
        actor_id=submission.candidate_id,
        submission_id=submission.id,
        action=action_type,
        metadata_json={
            "work_link": body.work_link,
            "file_reference": body.file_reference,
            "time_taken_minutes": body.time_taken_minutes,
            "is_first_submission": is_first_submission
        }
    )
    db.add(audit_entry)

    await db.commit()
    await db.refresh(submission)

    # Schedule background tasks
    if submission.candidate and submission.candidate.email:
        background_tasks.add_task(send_submission_confirmation_email, submission.candidate.email, str(submission.id))
    if body.file_reference:
        background_tasks.add_task(queue_file_antivirus_scan, str(submission.id), body.file_reference)

    return submission
