# `ta-assessment-api` — Curl Examples & API Documentation

Comprehensive list of `curl` commands demonstrating every candidate and reviewer API endpoint, including success and error scenarios.

Base URL: `http://localhost:8000`

---

## 1. Authentication (`POST /auth/login`)

### 1.1 Successful Reviewer Login
```bash
curl -X POST "http://localhost:8000/auth/login" \
  -H "Content-Type: application/json" \
  -d '{
    "email": "reviewer1@techabout.com",
    "password": "reviewer123"
  }'
```
**Response (200 OK):**
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer"
}
```

### 1.2 Failed Login (Invalid Credentials)
```bash
curl -X POST "http://localhost:8000/auth/login" \
  -H "Content-Type: application/json" \
  -d '{
    "email": "reviewer1@techabout.com",
    "password": "wrongpassword"
  }'
```
**Response (401 Unauthorized):**
```json
{
  "detail": "Incorrect email or password"
}
```

---

## 2. Candidate Endpoints

### 2.1 Fetch Brief & Submission View (`GET /submissions/{token}`)
```bash
curl -X GET "http://localhost:8000/submissions/tok_charlie_frontend_456def"
```
**Response (200 OK):**
```json
{
  "id": "e2ea2068-b564-473b-b67d-babd95da6e55",
  "status": "submitted",
  "submitted_at": "2026-07-24T06:33:05Z",
  "work_link": "https://github.com/charlie/react-app",
  "file_reference": null,
  "time_taken_minutes": 150,
  "notes": "Used TailwindCSS and Next.js.",
  "challenges": "Responsive grid design.",
  "assessment": {
    "id": "238d0ee3-f7f7-407e-af40-9024a23def19",
    "role": "Frontend Engineer",
    "title": "React Dashboard Challenge",
    "content": "# Frontend Challenge\n\nBuild a React dashboard with TailwindCSS.",
    "created_at": "2026-07-24T06:33:05Z"
  }
}
```

### 2.2 Invalid Token (`GET /submissions/{token}`)
```bash
curl -X GET "http://localhost:8000/submissions/invalid_token_999"
```
**Response (404 Not Found):**
```json
{
  "detail": "Submission token not found or invalid"
}
```

### 2.3 Submit Candidate Work (`POST /submissions/{token}`)
```bash
curl -X POST "http://localhost:8000/submissions/tok_diana_pending_789ghi" \
  -H "Content-Type: application/json" \
  -d '{
    "work_link": "https://github.com/diana/techabout-backend",
    "file_reference": "s3://techabout-uploads/diana-code.zip",
    "time_taken_minutes": 110,
    "notes": "Finished with full async test coverage.",
    "challenges": "PostgreSQL composite indexing."
  }'
```
**Response (200 OK):**
```json
{
  "id": "c2c25502-c509-4a6f-8da9-28499ab5b07f",
  "status": "submitted",
  "submitted_at": "2026-07-24T06:34:00Z",
  "work_link": "https://github.com/diana/techabout-backend",
  "file_reference": "s3://techabout-uploads/diana-code.zip",
  "time_taken_minutes": 110,
  "notes": "Finished with full async test coverage.",
  "challenges": "PostgreSQL composite indexing.",
  "assessment": {
    "id": "238d0ee3-f7f7-407e-af40-9024a23def19",
    "role": "Frontend Engineer",
    "title": "React Dashboard Challenge",
    "content": "# Frontend Challenge...",
    "created_at": "2026-07-24T06:33:05Z"
  }
}
```

### 2.4 Validation Failure (`javascript:` URL XSS prevention)
```bash
curl -X POST "http://localhost:8000/submissions/tok_diana_pending_789ghi" \
  -H "Content-Type: application/json" \
  -d '{
    "work_link": "javascript:alert(1)",
    "time_taken_minutes": -30
  }'
```
**Response (422 Unprocessable Entity):**
```json
{
  "detail": [
    {
      "type": "value_error",
      "loc": ["body", "work_link"],
      "msg": "Value error, work_link must use http or https protocol (javascript: and data: URLs are strictly prohibited)"
    }
  ]
}
```

### 2.5 Conflict Error (Modifying after review)
```bash
curl -X POST "http://localhost:8000/submissions/tok_alice_backend_abc123" \
  -H "Content-Type: application/json" \
  -d '{
    "work_link": "https://github.com/alice/attempt-edit",
    "time_taken_minutes": 100
  }'
```
**Response (409 Conflict):**
```json
{
  "detail": "Submission is currently in 'scored' state and cannot be modified."
}
```

---

## 3. Reviewer Admin Endpoints (JWT Required)

Set JWT Token variable:
```bash
TOKEN="<YOUR_JWT_ACCESS_TOKEN>"
```

### 3.1 List & Filter Submissions (`GET /admin/submissions`)
```bash
curl -X GET "http://localhost:8000/admin/submissions?role=Backend&city=San%20Francisco&page=1&page_size=10" \
  -H "Authorization: Bearer $TOKEN"
```
**Response (200 OK):**
```json
{
  "items": [
    {
      "id": "4dda2903-884a-47e5-aaa9-844bd1f54b44",
      "candidate_id": "1419b8f1-df65-49ad-902c-3ac263d4892b",
      "assessment_id": "8cb730b4-ae55-42a2-8575-b7a1db625181",
      "candidate": {
        "id": "1419b8f1-df65-49ad-902c-3ac263d4892b",
        "name": "Alice Johnson",
        "email": "alice@example.com",
        "city": "San Francisco"
      },
      "assessment": {
        "id": "8cb730b4-ae55-42a2-8575-b7a1db625181",
        "role": "Backend Engineer",
        "title": "Python Async API Challenge",
        "content": "# Backend Challenge...",
        "created_at": "2026-07-24T06:33:05Z"
      },
      "private_token": "tok_alice_backend_abc123",
      "work_link": "https://github.com/alice/backend-repo",
      "file_reference": "s3://techabout-uploads/alice-solution.zip",
      "time_taken_minutes": 120,
      "status": "scored",
      "submitted_at": "2026-07-22T06:33:05Z",
      "reviews": [
        {
          "id": "...",
          "score": 92.5,
          "decision": "advance",
          "private_note": "Excellent code architecture and unit tests."
        }
      ],
      "audit_logs": [...]
    }
  ],
  "total": 1,
  "page": 1,
  "page_size": 10
}
```

### 3.2 Fetch Submission Detail (`GET /admin/submissions/{id}`)
```bash
curl -X GET "http://localhost:8000/admin/submissions/4dda2903-884a-47e5-aaa9-844bd1f54b44" \
  -H "Authorization: Bearer $TOKEN"
```

### 3.3 Score & Review Submission (`POST /admin/submissions/{id}/review`)
```bash
curl -X POST "http://localhost:8000/admin/submissions/e2ea2068-b564-473b-b67d-babd95da6e55/review" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "score": 88.00,
    "decision": "advance",
    "private_note": "Strong candidate, clean code architecture."
  }'
```
**Response (200 OK):**
```json
{
  "id": "7f8a9b6c-1122-3344-5566-778899aabbcc",
  "submission_id": "e2ea2068-b564-473b-b67d-babd95da6e55",
  "reviewer_id": "...",
  "score": 88.0,
  "decision": "advance",
  "private_note": "Strong candidate, clean code architecture.",
  "created_at": "2026-07-24T06:34:00Z",
  "updated_at": "2026-07-24T06:34:00Z"
}
```

### 3.4 Invalid State Transition Error (Reviewing `pending` submission)
```bash
curl -X POST "http://localhost:8000/admin/submissions/c2c25502-c509-4a6f-8da9-28499ab5b07f/review" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "score": 80.0,
    "decision": "advance",
    "private_note": "Trying to review before candidate submitted work"
  }'
```
**Response (400 Bad Request):**
```json
{
  "detail": "Cannot review a submission that is still in 'pending' status (candidate has not submitted work yet)."
}
```

---

## 4. Rate Limiting (`429 Too Many Requests`)

If a candidate route exceeds 20 requests/min or auth route exceeds 5 requests/min:
```json
{
  "error": "Rate limit exceeded: 20 per 1 minute"
}
```
Headers returned include: `Retry-After: 60`.
