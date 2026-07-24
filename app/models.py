import enum
import uuid
from datetime import datetime, timezone
from typing import Optional, List, Any

from sqlalchemy import (
    Column,
    String,
    Text,
    Integer,
    Boolean,
    Numeric,
    DateTime,
    ForeignKey,
    UniqueConstraint,
    CheckConstraint,
    Index,
    Enum as SQLEnum,
    func
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class SubmissionStatus(str, enum.Enum):
    PENDING = "pending"
    SUBMITTED = "submitted"
    IN_REVIEW = "in_review"
    SCORED = "scored"
    REJECTED = "rejected"


class ReviewDecision(str, enum.Enum):
    PENDING = "pending"
    ADVANCE = "advance"
    REJECT = "reject"
    HOLD = "hold"


class ActorType(str, enum.Enum):
    CANDIDATE = "candidate"
    REVIEWER = "reviewer"
    SYSTEM = "system"


def utc_now():
    return datetime.now(timezone.utc)


class Candidate(Base):
    __tablename__ = "candidates"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    city: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    submissions: Mapped[List["Submission"]] = relationship("Submission", back_populates="candidate")


class AssessmentBrief(Base):
    __tablename__ = "assessment_briefs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    role: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    submissions: Mapped[List["Submission"]] = relationship("Submission", back_populates="assessment")


class ReviewerUser(Base):
    __tablename__ = "reviewer_users"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    password_hash: Mapped[str] = mapped_column(Text, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    reviews: Mapped[List["Review"]] = relationship("Review", back_populates="reviewer")


class Submission(Base):
    __tablename__ = "submissions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    candidate_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("candidates.id"), nullable=False)
    assessment_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("assessment_briefs.id"), nullable=False)
    private_token: Mapped[str] = mapped_column(Text, unique=True, nullable=False, index=True)
    work_link: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    file_reference: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    time_taken_minutes: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    challenges: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[SubmissionStatus] = mapped_column(
        SQLEnum(SubmissionStatus, name="submission_status", values_callable=lambda x: [e.value for e in x]),
        nullable=False,
        default=SubmissionStatus.PENDING,
        index=True
    )

    submitted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False
    )

    candidate: Mapped["Candidate"] = relationship("Candidate", back_populates="submissions")
    assessment: Mapped["AssessmentBrief"] = relationship("AssessmentBrief", back_populates="submissions")
    reviews: Mapped[List["Review"]] = relationship("Review", back_populates="submission", cascade="all, delete-orphan")
    audit_logs: Mapped[List["AuditLog"]] = relationship("AuditLog", back_populates="submission", cascade="all, delete-orphan")

    __table_args__ = (
        UniqueConstraint("candidate_id", "assessment_id", name="uq_candidate_assessment"),
        CheckConstraint("time_taken_minutes >= 0", name="ck_submission_time_taken_positive"),
        Index("ix_submissions_status_submitted_at", "status", "submitted_at"),
    )


class Review(Base):
    __tablename__ = "reviews"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    submission_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("submissions.id"), nullable=False)
    reviewer_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("reviewer_users.id"), nullable=False)
    score: Mapped[Optional[float]] = mapped_column(Numeric(5, 2), nullable=True)
    decision: Mapped[ReviewDecision] = mapped_column(
        SQLEnum(ReviewDecision, name="review_decision", values_callable=lambda x: [e.value for e in x]),
        nullable=False,
        default=ReviewDecision.PENDING
    )

    private_note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False
    )

    submission: Mapped["Submission"] = relationship("Submission", back_populates="reviews")
    reviewer: Mapped["ReviewerUser"] = relationship("ReviewerUser", back_populates="reviews")

    __table_args__ = (
        UniqueConstraint("submission_id", "reviewer_id", name="uq_submission_reviewer"),
        CheckConstraint("score >= 0 AND score <= 100", name="ck_review_score_range"),
    )


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    actor_type: Mapped[ActorType] = mapped_column(
        SQLEnum(ActorType, name="actor_type", values_callable=lambda x: [e.value for e in x]),
        nullable=False
    )

    actor_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), nullable=True)
    submission_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("submissions.id"), nullable=True)
    action: Mapped[str] = mapped_column(Text, nullable=False)
    metadata_json: Mapped[dict[str, Any]] = mapped_column("metadata", JSONB, nullable=False, server_default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True)

    submission: Mapped[Optional["Submission"]] = relationship("Submission", back_populates="audit_logs")
