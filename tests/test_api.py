import uuid
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.models import (
    Candidate, AssessmentBrief, ReviewerUser, Submission, Review, AuditLog,
    SubmissionStatus, ReviewDecision, ActorType
)
from app.auth import get_password_hash, create_access_token


async def setup_base_data(db_session: AsyncSession):
    c1 = Candidate(id=uuid.uuid4(), email="test_cand@example.com", name="Test Candidate", city="Lahore")
    b1 = AssessmentBrief(
        id=uuid.uuid4(),
        role="Backend Engineer",
        title="Python Test Brief",
        content="Write code."
    )
    r1 = ReviewerUser(
        id=uuid.uuid4(),
        email="rev_test@techabout.com",
        name="Test Reviewer",
        password_hash=get_password_hash("pass123"),
        is_active=True
    )
    db_session.add_all([c1, b1, r1])
    await db_session.flush()
    return c1, b1, r1


@pytest.mark.asyncio
async def test_candidate_token_auth(client: AsyncClient, db_session: AsyncSession):
    c1, b1, r1 = await setup_base_data(db_session)
    token = "valid_candidate_token_123"
    s1 = Submission(
        id=uuid.uuid4(),
        candidate_id=c1.id,
        assessment_id=b1.id,
        private_token=token,
        status=SubmissionStatus.PENDING
    )
    db_session.add(s1)
    await db_session.commit()

    # 1. Valid token returns 200 & brief content
    res_valid = await client.get(f"/submissions/{token}")
    assert res_valid.status_code == 200
    data = res_valid.json()
    assert data["assessment"]["title"] == "Python Test Brief"
    assert data["status"] == "pending"

    # 2. Invalid token returns 404
    res_invalid = await client.get("/submissions/non_existent_token_xyz")
    assert res_invalid.status_code == 404
    assert "not found" in res_invalid.json()["detail"].lower()


@pytest.mark.asyncio
async def test_reviewer_jwt_auth(client: AsyncClient, db_session: AsyncSession):
    c1, b1, r1 = await setup_base_data(db_session)
    await db_session.commit()

    # 1. Protected route rejects missing JWT
    res_no_auth = await client.get("/admin/submissions")
    assert res_no_auth.status_code == 401

    # 2. Protected route rejects invalid JWT
    res_bad_auth = await client.get(
        "/admin/submissions",
        headers={"Authorization": "Bearer invalid_jwt_token_payload"}
    )
    assert res_bad_auth.status_code == 401

    # 3. Valid JWT returns 200
    access_token = create_access_token({"sub": str(r1.id), "email": r1.email})
    res_valid = await client.get(
        "/admin/submissions",
        headers={"Authorization": f"Bearer {access_token}"}
    )
    assert res_valid.status_code == 200
    assert "items" in res_valid.json()


@pytest.mark.asyncio
async def test_submission_validation_failure(client: AsyncClient, db_session: AsyncSession):
    c1, b1, r1 = await setup_base_data(db_session)
    token = "val_fail_token_999"
    s1 = Submission(
        id=uuid.uuid4(),
        candidate_id=c1.id,
        assessment_id=b1.id,
        private_token=token,
        status=SubmissionStatus.PENDING
    )
    db_session.add(s1)
    await db_session.commit()

    # 1. Malformed work_link with javascript: protocol
    res_bad_link = await client.post(
        f"/submissions/{token}",
        json={"work_link": "javascript:alert('xss')", "time_taken_minutes": 60}
    )
    assert res_bad_link.status_code == 422

    # 2. Negative time_taken_minutes
    res_neg_time = await client.post(
        f"/submissions/{token}",
        json={"work_link": "https://github.com/test/repo", "time_taken_minutes": -45}
    )
    assert res_neg_time.status_code == 422

    # Verify submission remains untouched in PENDING status
    stmt = select(Submission).where(Submission.id == s1.id)
    res_sub = await db_session.execute(stmt)
    sub = res_sub.scalar_one()
    assert sub.status == SubmissionStatus.PENDING
    assert sub.work_link is None


@pytest.mark.asyncio
async def test_duplicate_submission_constraint(client: AsyncClient, db_session: AsyncSession):
    c1, b1, r1 = await setup_base_data(db_session)
    cand_id = c1.id
    brief_id = b1.id

    s1 = Submission(
        id=uuid.uuid4(),
        candidate_id=cand_id,
        assessment_id=brief_id,
        private_token="token_first_sub",
        status=SubmissionStatus.PENDING
    )
    db_session.add(s1)
    await db_session.commit()

    # Attempt to insert a second submission for the exact same (candidate_id, assessment_id)
    s2 = Submission(
        id=uuid.uuid4(),
        candidate_id=cand_id,
        assessment_id=brief_id,
        private_token="token_second_sub",
        status=SubmissionStatus.PENDING
    )
    db_session.add(s2)

    with pytest.raises(Exception) as exc_info:
        await db_session.flush()

    assert "uq_candidate_assessment" in str(exc_info.value) or "unique" in str(exc_info.value).lower()
    await db_session.rollback()

    # Verify only 1 row exists in DB
    count_stmt = select(func.count(Submission.id)).where(
        Submission.candidate_id == cand_id,
        Submission.assessment_id == brief_id
    )
    res_count = await db_session.execute(count_stmt)
    assert res_count.scalar_one() == 1



@pytest.mark.asyncio
async def test_reviewer_status_transition_rules(client: AsyncClient, db_session: AsyncSession):
    c1, b1, r1 = await setup_base_data(db_session)
    access_token = create_access_token({"sub": str(r1.id), "email": r1.email})
    headers = {"Authorization": f"Bearer {access_token}"}

    # Submission 1 in PENDING state
    s_pending = Submission(
        id=uuid.uuid4(),
        candidate_id=c1.id,
        assessment_id=b1.id,
        private_token="tok_pending_state",
        status=SubmissionStatus.PENDING
    )
    db_session.add(s_pending)
    await db_session.commit()

    # Attempting to review a PENDING submission returns 400 Bad Request
    res_pending_review = await client.post(
        f"/admin/submissions/{s_pending.id}/review",
        headers=headers,
        json={"score": 85.0, "decision": "advance", "private_note": "Great job"}
    )
    assert res_pending_review.status_code == 400
    assert "pending" in res_pending_review.json()["detail"].lower()

    # Move submission to SUBMITTED state
    s_pending.status = SubmissionStatus.SUBMITTED
    await db_session.commit()

    # Reviewing a SUBMITTED submission succeeds (200)
    res_valid_review = await client.post(
        f"/admin/submissions/{s_pending.id}/review",
        headers=headers,
        json={"score": 90.0, "decision": "advance", "private_note": "Approved"}
    )
    assert res_valid_review.status_code == 200
    assert res_valid_review.json()["score"] == 90.0
    assert res_valid_review.json()["decision"] == "advance"


@pytest.mark.asyncio
async def test_audit_logging(client: AsyncClient, db_session: AsyncSession):
    c1, b1, r1 = await setup_base_data(db_session)
    token = "audit_log_token_123"
    s1 = Submission(
        id=uuid.uuid4(),
        candidate_id=c1.id,
        assessment_id=b1.id,
        private_token=token,
        status=SubmissionStatus.PENDING
    )
    db_session.add(s1)
    await db_session.commit()

    # 1. Candidate submits work
    submit_res = await client.post(
        f"/submissions/{token}",
        json={
            "work_link": "https://github.com/audit/repo",
            "time_taken_minutes": 100,
            "notes": "Testing audit log creation"
        }
    )
    assert submit_res.status_code == 200

    # Verify candidate submission audit log entry
    stmt_audits = select(AuditLog).where(AuditLog.submission_id == s1.id)
    audits_res = await db_session.execute(stmt_audits)
    audits = audits_res.scalars().all()

    cand_audits = [a for a in audits if a.actor_type == ActorType.CANDIDATE]
    assert len(cand_audits) == 1
    assert cand_audits[0].action == "submission.created"
    assert cand_audits[0].actor_id == c1.id

    # 2. Reviewer reviews submission
    access_token = create_access_token({"sub": str(r1.id), "email": r1.email})
    headers = {"Authorization": f"Bearer {access_token}"}
    review_res = await client.post(
        f"/admin/submissions/{s1.id}/review",
        headers=headers,
        json={"score": 95.0, "decision": "advance", "private_note": "Solid work"}
    )
    assert review_res.status_code == 200

    # Verify reviewer review audit log entry
    audits_res2 = await db_session.execute(stmt_audits)
    audits2 = audits_res2.scalars().all()

    rev_audits = [a for a in audits2 if a.actor_type == ActorType.REVIEWER]
    assert len(rev_audits) == 1
    assert rev_audits[0].action == "review.created"
    assert rev_audits[0].actor_id == r1.id
