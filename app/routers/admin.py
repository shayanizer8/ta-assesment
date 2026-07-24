from typing import Optional
from datetime import datetime
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Request, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_
from sqlalchemy.orm import joinedload, selectinload

from app.database import get_db
from app.models import (
    Submission, Candidate, AssessmentBrief, Review, ReviewerUser, AuditLog,
    SubmissionStatus, ReviewDecision, ActorType
)
from app.schemas import (
    LoginRequest, TokenResponse, SubmissionDetailResponse, SubmissionListResponse,
    ReviewCreateRequest, ReviewResponse
)
from app.auth import verify_password, create_access_token, get_current_reviewer
from app.rate_limiter import limiter
from app.config import settings

auth_router = APIRouter(prefix="/auth", tags=["Authentication"])
admin_router = APIRouter(prefix="/admin", tags=["Admin Submissions"])


from fastapi.security import OAuth2PasswordRequestForm

@auth_router.post("/login", response_model=TokenResponse)
@limiter.limit(settings.RATE_LIMIT_AUTH)
async def login(
    request: Request,
    body: Optional[LoginRequest] = None,
    db: AsyncSession = Depends(get_db)
):
    email = None
    password = None

    content_type = request.headers.get("content-type", "")
    if "x-www-form-urlencoded" in content_type or "form-data" in content_type:
        form = await request.form()
        email = form.get("username") or form.get("email")
        password = form.get("password")
    elif body:
        email = body.email
        password = body.password

    if not email or not password:
        try:
            json_body = await request.json()
            email = json_body.get("email") or json_body.get("username")
            password = json_body.get("password")
        except Exception:
            pass

    if not email or not password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email and password are required."
        )

    stmt = select(ReviewerUser).where(ReviewerUser.email == email, ReviewerUser.is_active.is_(True))
    result = await db.execute(stmt)
    reviewer = result.scalar_one_or_none()

    if not reviewer or not verify_password(password, reviewer.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    access_token = create_access_token(data={"sub": str(reviewer.id), "email": reviewer.email})
    return TokenResponse(access_token=access_token)




@admin_router.get("/submissions", response_model=SubmissionListResponse)
async def list_submissions(
    role: Optional[str] = Query(None, description="Filter by brief role"),
    status_filter: Optional[SubmissionStatus] = Query(None, alias="status", description="Filter by status"),
    score_min: Optional[float] = Query(None, ge=0, le=100, description="Filter by minimum review score"),
    score_max: Optional[float] = Query(None, ge=0, le=100, description="Filter by maximum review score"),
    city: Optional[str] = Query(None, description="Filter candidate city"),
    submitted_after: Optional[datetime] = Query(None, description="Filter submitted after timestamp"),
    submitted_before: Optional[datetime] = Query(None, description="Filter submitted before timestamp"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_reviewer: ReviewerUser = Depends(get_current_reviewer),
    db: AsyncSession = Depends(get_db)
):
    # Base query joining candidates, briefs, and eager-loading reviews & audit logs to avoid N+1 queries
    query = (
        select(Submission)
        .join(Submission.candidate)
        .join(Submission.assessment)
        .options(
            joinedload(Submission.candidate),
            joinedload(Submission.assessment),
            selectinload(Submission.reviews),
            selectinload(Submission.audit_logs)
        )
    )

    conditions = []
    if role:
        conditions.append(AssessmentBrief.role.ilike(f"%{role}%"))
    if status_filter:
        conditions.append(Submission.status == status_filter)
    if city:
        conditions.append(Candidate.city.ilike(f"%{city}%"))
    if submitted_after:
        conditions.append(Submission.submitted_at >= submitted_after)
    if submitted_before:
        conditions.append(Submission.submitted_at <= submitted_before)

    if score_min is not None or score_max is not None:
        query = query.outerjoin(Submission.reviews)
        if score_min is not None:
            conditions.append(Review.score >= score_min)
        if score_max is not None:
            conditions.append(Review.score <= score_max)

    if conditions:
        query = query.where(and_(*conditions))

    # Count total distinct submission records matching filter
    count_stmt = select(func.count(func.distinct(Submission.id))).join(Submission.candidate).join(Submission.assessment)
    if score_min is not None or score_max is not None:
        count_stmt = count_stmt.outerjoin(Submission.reviews)
    if conditions:
        count_stmt = count_stmt.where(and_(*conditions))
    total_result = await db.execute(count_stmt)
    total = total_result.scalar_one() or 0


    # Order and paginate
    query = query.order_by(Submission.submitted_at.desc().nullslast(), Submission.created_at.desc())
    offset = (page - 1) * page_size
    query = query.offset(offset).limit(page_size)

    result = await db.execute(query)
    submissions = result.scalars().unique().all()

    return SubmissionListResponse(
        items=submissions,
        total=total,
        page=page,
        page_size=page_size
    )


@admin_router.get("/submissions/{submission_id}", response_model=SubmissionDetailResponse)
async def get_submission_detail(
    submission_id: UUID,
    current_reviewer: ReviewerUser = Depends(get_current_reviewer),
    db: AsyncSession = Depends(get_db)
):
    stmt = (
        select(Submission)
        .options(
            joinedload(Submission.candidate),
            joinedload(Submission.assessment),
            selectinload(Submission.reviews),
            selectinload(Submission.audit_logs)
        )
        .where(Submission.id == submission_id)
    )
    result = await db.execute(stmt)
    submission = result.scalar_one_or_none()

    if not submission:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Submission not found"
        )

    return submission


@admin_router.post("/submissions/{submission_id}/review", response_model=ReviewResponse)
async def review_submission(
    submission_id: UUID,
    body: ReviewCreateRequest,
    current_reviewer: ReviewerUser = Depends(get_current_reviewer),
    db: AsyncSession = Depends(get_db)
):
    # Fetch submission
    stmt = select(Submission).where(Submission.id == submission_id)
    result = await db.execute(stmt)
    submission = result.scalar_one_or_none()

    if not submission:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Submission not found"
        )

    # State Machine Validation: Reviewer cannot review a pending (unsubmitted) submission
    if submission.status == SubmissionStatus.PENDING:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot review a submission that is still in 'pending' status (candidate has not submitted work yet)."
        )

    # Check if this reviewer already reviewed this submission (1 review per submission per reviewer model)
    review_stmt = select(Review).where(
        Review.submission_id == submission_id,
        Review.reviewer_id == current_reviewer.id
    )
    review_result = await db.execute(review_stmt)
    review = review_result.scalar_one_or_none()

    is_new = review is None
    if is_new:
        review = Review(
            submission_id=submission_id,
            reviewer_id=current_reviewer.id,
            score=body.score,
            decision=body.decision,
            private_note=body.private_note
        )
        db.add(review)
        action_name = "review.created"
    else:
        review.score = body.score
        review.decision = body.decision
        review.private_note = body.private_note
        action_name = "review.updated"

    # Status State Machine transition triggered by reviewer action
    if body.decision == ReviewDecision.REJECT:
        submission.status = SubmissionStatus.REJECTED
    elif body.decision == ReviewDecision.ADVANCE:
        if body.score is not None:
            submission.status = SubmissionStatus.SCORED
        else:
            submission.status = SubmissionStatus.IN_REVIEW
    elif body.decision in (ReviewDecision.HOLD, ReviewDecision.PENDING):
        if body.score is not None:
            submission.status = SubmissionStatus.SCORED
        else:
            submission.status = SubmissionStatus.IN_REVIEW

    # Audit logging
    audit_entry = AuditLog(
        actor_type=ActorType.REVIEWER,
        actor_id=current_reviewer.id,
        submission_id=submission_id,
        action=action_name,
        metadata_json={
            "score": body.score,
            "decision": body.decision.value,
            "new_submission_status": submission.status.value,
            "reviewer_email": current_reviewer.email
        }
    )
    db.add(audit_entry)

    await db.commit()
    await db.refresh(review)

    return review
