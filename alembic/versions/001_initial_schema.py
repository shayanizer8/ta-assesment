"""001_initial_schema

Revision ID: 001_initial_schema
Revises: 
Create Date: 2026-07-24 12:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = '001_initial_schema'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Enum types
    submission_status_enum = postgresql.ENUM('pending', 'submitted', 'in_review', 'scored', 'rejected', name='submission_status')
    submission_status_enum.create(op.get_bind(), checkfirst=True)

    review_decision_enum = postgresql.ENUM('pending', 'advance', 'reject', 'hold', name='review_decision')
    review_decision_enum.create(op.get_bind(), checkfirst=True)

    actor_type_enum = postgresql.ENUM('candidate', 'reviewer', 'system', name='actor_type')
    actor_type_enum.create(op.get_bind(), checkfirst=True)

    # 1. candidates
    op.create_table(
        'candidates',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('email', sa.Text(), nullable=False, unique=True),
        sa.Column('name', sa.Text(), nullable=False),
        sa.Column('city', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    )

    # 2. assessment_briefs
    op.create_table(
        'assessment_briefs',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('role', sa.Text(), nullable=False),
        sa.Column('title', sa.Text(), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    )
    op.create_index('ix_assessment_briefs_role', 'assessment_briefs', ['role'])

    # 3. reviewer_users
    op.create_table(
        'reviewer_users',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('email', sa.Text(), nullable=False, unique=True),
        sa.Column('name', sa.Text(), nullable=False),
        sa.Column('password_hash', sa.Text(), nullable=False),
        sa.Column('is_active', sa.Boolean(), server_default=sa.text('true'), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    )

    # 4. submissions
    op.create_table(
        'submissions',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('candidate_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('candidates.id', ondelete='CASCADE'), nullable=False),
        sa.Column('assessment_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('assessment_briefs.id', ondelete='CASCADE'), nullable=False),
        sa.Column('private_token', sa.Text(), nullable=False, unique=True),
        sa.Column('work_link', sa.Text(), nullable=True),
        sa.Column('file_reference', sa.Text(), nullable=True),
        sa.Column('time_taken_minutes', sa.Integer(), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('challenges', sa.Text(), nullable=True),
        sa.Column('status', postgresql.ENUM('pending', 'submitted', 'in_review', 'scored', 'rejected', name='submission_status', create_type=False), server_default='pending', nullable=False),


        sa.Column('submitted_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.UniqueConstraint('candidate_id', 'assessment_id', name='uq_candidate_assessment'),
        sa.CheckConstraint('time_taken_minutes >= 0', name='ck_submission_time_taken_positive'),
    )
    op.create_index('ix_submissions_private_token', 'submissions', ['private_token'])
    op.create_index('ix_submissions_status', 'submissions', ['status'])
    op.create_index('ix_submissions_submitted_at', 'submissions', ['submitted_at'])
    op.create_index('ix_submissions_status_submitted_at', 'submissions', ['status', 'submitted_at'])

    # 5. reviews
    op.create_table(
        'reviews',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('submission_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('submissions.id', ondelete='CASCADE'), nullable=False),
        sa.Column('reviewer_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('reviewer_users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('score', sa.Numeric(precision=5, scale=2), nullable=True),
        sa.Column('decision', postgresql.ENUM('pending', 'advance', 'reject', 'hold', name='review_decision', create_type=False), server_default='pending', nullable=False),


        sa.Column('private_note', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.UniqueConstraint('submission_id', 'reviewer_id', name='uq_submission_reviewer'),
        sa.CheckConstraint('score >= 0 AND score <= 100', name='ck_review_score_range'),
    )

    # 6. audit_logs
    op.create_table(
        'audit_logs',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('actor_type', postgresql.ENUM('candidate', 'reviewer', 'system', name='actor_type', create_type=False), nullable=False),


        sa.Column('actor_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('submission_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('submissions.id', ondelete='SET NULL'), nullable=True),
        sa.Column('action', sa.Text(), nullable=False),
        sa.Column('metadata', postgresql.JSONB(astext_type=sa.Text()), server_default='{}', nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    )
    op.create_index('ix_audit_logs_created_at', 'audit_logs', ['created_at'])


def downgrade() -> None:
    op.drop_index('ix_audit_logs_created_at', table_name='audit_logs')
    op.drop_table('audit_logs')

    op.drop_table('reviews')

    op.drop_index('ix_submissions_status_submitted_at', table_name='submissions')
    op.drop_index('ix_submissions_submitted_at', table_name='submissions')
    op.drop_index('ix_submissions_status', table_name='submissions')
    op.drop_index('ix_submissions_private_token', table_name='submissions')
    op.drop_table('submissions')

    op.drop_table('reviewer_users')

    op.drop_index('ix_assessment_briefs_role', table_name='assessment_briefs')
    op.drop_table('assessment_briefs')

    op.drop_table('candidates')

    op.execute('DROP TYPE IF EXISTS actor_type CASCADE;')
    op.execute('DROP TYPE IF EXISTS review_decision CASCADE;')
    op.execute('DROP TYPE IF EXISTS submission_status CASCADE;')
