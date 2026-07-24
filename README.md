# `ta-assessment-api` — Technical Assessment Service

`ta-assessment-api` is a robust, production-grade backend service built with **Python 3.13**, **FastAPI**, **SQLAlchemy 2.x**, **Alembic**, and **PostgreSQL** for TechAbout's recruitment assessment workflow.

---

## 1. Quick Start & Setup

### 1.1 Prerequisites
- Python 3.13+ installed.
- PostgreSQL database running (or use the local virtual environment).

### 1.2 Virtual Environment Activation & Installation
Dependencies are pre-installed in the root `venv`:
```powershell
# Windows PowerShell
.\venv\Scripts\Activate.ps1
```
Or install dependencies directly:
```bash
pip install fastapi "uvicorn[standard]" "sqlalchemy>=2.0" alembic asyncpg psycopg2-binary "pydantic>=2.0" pydantic-settings pyjwt "pwdlib[bcrypt]" slowapi httpx pytest pytest-asyncio
```

### 1.3 Environment Variables
Set environment variables or create a `.env` file in the project root:
```env
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5433/ta_assessment
TEST_DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5433/ta_assessment_test
SYNC_DATABASE_URL=postgresql+psycopg2://postgres:postgres@localhost:5433/ta_assessment
JWT_SECRET=ta_assessment_super_secret_jwt_key_2026_change_in_prod
ACCESS_TOKEN_EXPIRE_MINUTES=60
```

---

## 2. Database Setup & Migrations

### 2.1 Running Migrations
Apply the initial schema to PostgreSQL:
```powershell
.\venv\Scripts\alembic.exe upgrade head
```

### 2.2 Migration Rollback Demonstration
Verify Alembic migration rollback (`downgrade`):
```powershell
# Rollback the last migration
.\venv\Scripts\alembic.exe downgrade -1

# Re-apply migrations
.\venv\Scripts\alembic.exe upgrade head
```

### 2.3 Seeding Initial Sample Data
Populate the database with test candidates, assessment briefs, reviewer users, submissions, reviews, and audit logs:
```powershell
.\venv\Scripts\python.exe seed.py
```

---

## 3. Running the Server & OpenAPI Documentation

### 3.1 Start Development Server
```powershell
.\venv\Scripts\uvicorn.exe app.main:app --reload --port 8000
```

### 3.2 Interactive API Docs & OpenAPI Specification
- **Interactive Swagger UI:** [http://localhost:8000/docs](http://localhost:8000/docs)
- **ReDoc Documentation:** [http://localhost:8000/redoc](http://localhost:8000/redoc)
- **OpenAPI JSON Spec:** [http://localhost:8000/openapi.json](http://localhost:8000/openapi.json) (or exported [`openapi.json`](file:///c:/Users/Shayan/Downloads/TechAbout/ta-assesment/openapi.json))
- **cURL Command Examples:** See [`curl_examples.md`](file:///c:/Users/Shayan/Downloads/TechAbout/ta-assesment/curl_examples.md)

---

## 4. Automated Testing

Run the full pytest suite against the PostgreSQL test database:
```powershell
.\venv\Scripts\pytest.exe -v
```

### Test Coverage (6 Mandatory Verification Areas):
1. **Candidate Token Auth (`GET /submissions/{token}`):** Valid token returns assessment brief & submission status; invalid token returns HTTP 404.
2. **Reviewer Auth (`/admin/*`):** Missing/invalid JWT token returns HTTP 401 Unauthorized; valid JWT allows access.
3. **Input Validation:** Submitting malformed `work_link` (`javascript:` or `data:`) or negative `time_taken_minutes` returns HTTP 422 and prevents DB modification.
4. **Duplicate Submission Guard:** Submitting two submissions for the same `(candidate_id, assessment_id)` triggers PostgreSQL `UNIQUE` constraint and surfaces a clean HTTP 409 Conflict.
5. **Reviewer Permission / State Machine:** Reviewers can score a `submitted` submission, but attempting to score a `pending` (unsubmitted) submission returns HTTP 400 Bad Request.
6. **Audit Logging:** Every candidate submission and reviewer score creates an immutable `audit_logs` record with action names (`submission.created`, `review.created`) and correct `actor_type`.

---

## 5. Architectural Design & Tradeoffs

### 5.1 Auth Model Tradeoffs
- **Candidate Auth:** Candidates receive an unguessable 32-byte opaque URL-safe bearer token (`secrets.token_urlsafe(32)`, offering 256 bits of entropy).
  - *Why acceptable here:* Single-resource scope (candidate accessing their own take-home test), low PII risk, eliminates user account creation friction.
  - *When insufficient:* High-stakes systems requiring PII confidentiality, multi-session management, or role delegation where identity revocation is required.
- **Reviewer Auth:** Reviewer users authenticate via `/auth/login` using bcrypt-hashed passwords to receive short-lived JWT access tokens.

### 5.2 N+1 Optimization Analysis
To avoid N+1 query overhead on the `/admin/submissions` list and detail routes:
- We use SQLAlchemy 2.0 `joinedload(Submission.candidate)` and `joinedload(Submission.assessment)` for 1:1 candidate and brief data.
- We use `selectinload(Submission.reviews)` and `selectinload(Submission.audit_logs)` to load 1:N relations efficiently in a second batched query.
- Result: 1 single SQL query with JOINs loads candidates, briefs, reviews, and logs regardless of result set size.

### 5.3 Review Model Choice
- We implemented a `UNIQUE (submission_id, reviewer_id)` constraint on the `reviews` table.
- *Justification:* Allows multiple reviewers to evaluate a single candidate submission (one review row per reviewer) without ambiguity or overwriting colleague reviews.

---

## 6. Status State Machine

The submission status moves strictly through the following state machine:

```
[ pending ]  ---> Candidate POST /submissions/{token} --->  [ submitted ]
                                                                |
                                        Reviewer Decision       v
                                  +-----------------------------+-----------------------------+
                                  |                             |                             |
                                  v                             v                             v
                             [ in_review ]                 [ scored ]                    [ rejected ]
```

### State Machine Rules:
1. **Pending -> Submitted:** Triggered by candidate submitting work (`POST /submissions/{token}`). Sets `submitted_at = NOW()`.
2. **Editing Restriction (409 Conflict):** Once a submission transitions to `in_review`, `scored`, or `rejected`, candidate edits are blocked and return HTTP 409 Conflict.
3. **Review Restriction (400 Bad Request):** Reviewers cannot review or score a submission still in `pending` status (candidate hasn't submitted work yet).

---

## 7. Scaling to 50,000 Applicants (Design Discussion)

1. **Keyset / Cursor Pagination vs. Offset Pagination:**
   - Offset pagination (`OFFSET 40000 LIMIT 20`) forces PostgreSQL to scan 40,000 index tuples before returning 20 rows, leading to high I/O and query latency.
   - For scale, we recommend **keyset pagination** on `(submitted_at, id)`: `WHERE (submitted_at, id) < ($last_submitted_at, $last_id) ORDER BY submitted_at DESC, id DESC LIMIT 20`, utilizing the index directly.
2. **Database Indexing Strategy:**
   - Composite index `ix_submissions_status_submitted_at (status, submitted_at)` allows instant index scans for reviewer dashboard filtering.
   - Unique index `uq_candidate_assessment (candidate_id, assessment_id)` prevents duplicate records at the storage engine level.
3. **Audit Log Table Growth & Partitioning:**
   - As `audit_logs` is append-only, partitioning by month (`RANGE (created_at)`) allows easy archival of historical logs without locking active tables.
4. **What NOT to Build Prematurely:**
   - Do not introduce Redis cache clusters, read-replica routers, or microservices until metrics show database connection limits or CPU bottlenecks under real production load.

---

## 8. Async & Background Worker Architecture

- **Take-Home Implementation:** Uses FastAPI `BackgroundTasks` to execute non-blocking stub tasks after candidate submission (`send_submission_confirmation_email` and `queue_file_antivirus_scan`).
- **Production Evolution (Durable Workers):**
  - Replace `BackgroundTasks` with a dedicated worker queue (e.g. Celery / SQS / Redis Streams).
  - Use the **Transactional Outbox Pattern**: Write job intent into an `outbox` table inside the same DB transaction as the submission edit. A background worker process polls the outbox table, processes the job, and updates completion state. If a worker crashes, no notifications are lost.
  - **Idempotency:** Workers deduplicate retries using job IDs or submission audit log IDs to ensure candidates never receive duplicate confirmation emails.

---

## 9. Deployment & Production Operations

- **Required Environment Variables:** `DATABASE_URL`, `JWT_SECRET` (from Secrets Manager), `ACCESS_TOKEN_EXPIRE_MINUTES`.
- **Structured Logging:** Use standard JSON log format with a correlation ID (`x-request-id`) injected into context for distributed tracing.
- **Backup & Recovery Strategy:** Daily `pg_dump` snapshots stored in cloud object storage + Write-Ahead Logging (WAL) archiving for Point-In-Time Recovery (PITR).

---

## 10. Explicit Non-Goals

1. **No Direct File Upload Storage:** `file_reference` is stored as an opaque string (e.g. S3 key). Direct binary file upload to the API is explicitly avoided.
2. **No Password Reset / Refresh Token Flow:** Out of scope for reviewer login; simple access tokens are issued.
3. **No Tiered Reviewer Roles:** All reviewers currently have equal permissions.
4. **No Real Email Delivery Infrastructure:** Stubbed via async tasks.
5. **No Queue Infrastructure:** FastAPI `BackgroundTasks` is used instead of Celery/Redis.
