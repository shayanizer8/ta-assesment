from uuid import UUID
from datetime import datetime
from typing import Optional, List, Any
from urllib.parse import urlparse
from pydantic import BaseModel, ConfigDict, Field, field_validator
from app.models import SubmissionStatus, ReviewDecision, ActorType


class LoginRequest(BaseModel):
    email: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class CandidateResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    email: str
    city: Optional[str] = None


class BriefResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    role: str
    title: str
    content: str
    created_at: datetime


class SubmissionSubmitRequest(BaseModel):
    work_link: Optional[str] = None
    file_reference: Optional[str] = None
    time_taken_minutes: Optional[int] = Field(default=None, ge=0)
    notes: Optional[str] = None
    challenges: Optional[str] = None

    @field_validator("work_link")
    @classmethod
    def validate_work_link(cls, v: Optional[str]) -> Optional[str]:
        if v is None or v.strip() == "":
            return None
        parsed = urlparse(v)
        if parsed.scheme.lower() not in ("http", "https"):
            raise ValueError("work_link must use http or https protocol (javascript: and data: URLs are strictly prohibited)")
        if not parsed.netloc:
            raise ValueError("work_link must be a valid URL with domain/host")
        return v


class ReviewCreateRequest(BaseModel):
    score: Optional[float] = Field(default=None, ge=0.0, le=100.0)
    decision: ReviewDecision
    private_note: Optional[str] = None


class ReviewResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    submission_id: UUID
    reviewer_id: UUID
    score: Optional[float] = None
    decision: ReviewDecision
    private_note: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class AuditLogResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    actor_type: ActorType
    actor_id: Optional[UUID] = None
    submission_id: Optional[UUID] = None
    action: str
    metadata_json: dict[str, Any] = Field(alias="metadata_json")
    created_at: datetime


class CandidateSubmissionView(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    status: SubmissionStatus
    submitted_at: Optional[datetime] = None
    work_link: Optional[str] = None
    file_reference: Optional[str] = None
    time_taken_minutes: Optional[int] = None
    notes: Optional[str] = None
    challenges: Optional[str] = None
    assessment: BriefResponse


class SubmissionDetailResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    candidate_id: UUID
    assessment_id: UUID
    candidate: CandidateResponse
    assessment: BriefResponse
    private_token: str
    work_link: Optional[str] = None
    file_reference: Optional[str] = None
    time_taken_minutes: Optional[int] = None
    notes: Optional[str] = None
    challenges: Optional[str] = None
    status: SubmissionStatus
    submitted_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime
    reviews: List[ReviewResponse] = []
    audit_logs: List[AuditLogResponse] = []


class SubmissionListResponse(BaseModel):
    items: List[SubmissionDetailResponse]
    total: int
    page: int
    page_size: int
