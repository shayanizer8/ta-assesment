import asyncio
import uuid
from datetime import datetime, timedelta, timezone
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy import select, delete

from app.config import settings
from app.models import (
    Base, Candidate, AssessmentBrief, ReviewerUser, Submission, Review, AuditLog,
    SubmissionStatus, ReviewDecision, ActorType
)
from app.auth import get_password_hash


async def seed():
    engine = create_async_engine(settings.DATABASE_URL, echo=False)
    async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as db:
        print("Cleaning up existing data...")
        await db.execute(delete(AuditLog))
        await db.execute(delete(Review))
        await db.execute(delete(Submission))
        await db.execute(delete(ReviewerUser))
        await db.execute(delete(AssessmentBrief))
        await db.execute(delete(Candidate))
        await db.commit()

        print("Seeding candidates...")
        c1 = Candidate(id=uuid.uuid4(), email="alice@example.com", name="Alice Johnson", city="San Francisco")
        c2 = Candidate(id=uuid.uuid4(), email="bob@example.com", name="Bob Smith", city="London")
        c3 = Candidate(id=uuid.uuid4(), email="charlie@example.com", name="Charlie Brown", city="San Francisco")
        c4 = Candidate(id=uuid.uuid4(), email="diana@example.com", name="Diana Prince", city="Berlin")
        db.add_all([c1, c2, c3, c4])

        print("Seeding assessment briefs...")
        b1 = AssessmentBrief(
            id=uuid.uuid4(),
            role="Backend Engineer",
            title="Python Async API Challenge",
            content="# Backend Challenge\n\nBuild a FastAPI REST backend with PostgreSQL."
        )
        b2 = AssessmentBrief(
            id=uuid.uuid4(),
            role="Frontend Engineer",
            title="React Dashboard Challenge",
            content="# Frontend Challenge\n\nBuild a React dashboard with TailwindCSS."
        )
        db.add_all([b1, b2])

        print("Seeding reviewer users...")
        r1 = ReviewerUser(
            id=uuid.uuid4(),
            email="reviewer1@techabout.com",
            name="Sarah Reviewer",
            password_hash=get_password_hash("reviewer123"),
            is_active=True
        )
        r2 = ReviewerUser(
            id=uuid.uuid4(),
            email="reviewer2@techabout.com",
            name="Mike TechLead",
            password_hash=get_password_hash("reviewer123"),
            is_active=True
        )
        db.add_all([r1, r2])
        await db.commit()

        print("Seeding submissions...")
        now = datetime.now(timezone.utc)

        s1 = Submission(
            id=uuid.uuid4(),
            candidate_id=c1.id,
            assessment_id=b1.id,
            private_token="tok_alice_backend_abc123",
            work_link="https://github.com/alice/backend-repo",
            file_reference="s3://techabout-uploads/alice-solution.zip",
            time_taken_minutes=120,
            notes="Implemented cleanly with async SQLAlchemy.",
            challenges="Handling rate limits and DB constraints.",
            status=SubmissionStatus.SCORED,
            submitted_at=now - timedelta(days=2)
        )

        s2 = Submission(
            id=uuid.uuid4(),
            candidate_id=c2.id,
            assessment_id=b1.id,
            private_token="tok_bob_backend_xyz789",
            work_link="https://github.com/bob/backend-submission",
            file_reference="s3://techabout-uploads/bob-solution.zip",
            time_taken_minutes=90,
            notes="Basic implementation.",
            challenges="None",
            status=SubmissionStatus.REJECTED,
            submitted_at=now - timedelta(days=1)
        )

        s3 = Submission(
            id=uuid.uuid4(),
            candidate_id=c3.id,
            assessment_id=b2.id,
            private_token="tok_charlie_frontend_456def",
            work_link="https://github.com/charlie/react-app",
            file_reference=None,
            time_taken_minutes=150,
            notes="Used TailwindCSS and Next.js.",
            challenges="Responsive grid design.",
            status=SubmissionStatus.SUBMITTED,
            submitted_at=now - timedelta(hours=5)
        )

        s4 = Submission(
            id=uuid.uuid4(),
            candidate_id=c4.id,
            assessment_id=b2.id,
            private_token="tok_diana_pending_789ghi",
            work_link=None,
            file_reference=None,
            time_taken_minutes=None,
            notes=None,
            challenges=None,
            status=SubmissionStatus.PENDING,
            submitted_at=None
        )
        db.add_all([s1, s2, s3, s4])
        await db.commit()

        print("Seeding reviews...")
        rev1 = Review(
            id=uuid.uuid4(),
            submission_id=s1.id,
            reviewer_id=r1.id,
            score=92.50,
            decision=ReviewDecision.ADVANCE,
            private_note="Excellent code architecture and unit tests."
        )

        rev2 = Review(
            id=uuid.uuid4(),
            submission_id=s2.id,
            reviewer_id=r2.id,
            score=45.00,
            decision=ReviewDecision.REJECT,
            private_note="Missing DB constraint error handling and tests."
        )
        db.add_all([rev1, rev2])

        print("Seeding audit logs...")
        al1 = AuditLog(
            actor_type=ActorType.CANDIDATE,
            actor_id=c1.id,
            submission_id=s1.id,
            action="submission.created",
            metadata_json={"work_link": s1.work_link}
        )
        al2 = AuditLog(
            actor_type=ActorType.REVIEWER,
            actor_id=r1.id,
            submission_id=s1.id,
            action="review.created",
            metadata_json={"score": 92.50, "decision": "advance"}
        )
        db.add_all([al1, al2])

        await db.commit()
        print("\nSeed data successfully inserted into PostgreSQL!")
        print("\nSample Tokens & Credentials:")
        print(f"Reviewer Email: {r1.email} | Password: reviewer123")
        print(f"Candidate Token 1 (Scored): {s1.private_token}")
        print(f"Candidate Token 2 (Submitted): {s3.private_token}")
        print(f"Candidate Token 3 (Pending): {s4.private_token}")

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(seed())
