from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from sqlalchemy.exc import IntegrityError

from app.rate_limiter import limiter
from app.routers.candidate import router as candidate_router
from app.routers.admin import auth_router, admin_router

app = FastAPI(
    title="TechAbout Assessment API",
    description="Backend service for TechAbout recruitment assessment workflow, candidate submissions, reviewer scoring, and audit logging.",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json"
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)


@app.exception_handler(IntegrityError)
async def integrity_error_handler(request: Request, exc: IntegrityError):
    err_msg = str(exc.orig) if exc.orig else str(exc)
    if "uq_candidate_assessment" in err_msg or "unique constraint" in err_msg.lower():
        return JSONResponse(
            status_code=status.HTTP_409_CONFLICT,
            content={
                "detail": "Duplicate submission error: Candidate has already been assigned or submitted for this assessment."
            }
        )
    return JSONResponse(
        status_code=status.HTTP_409_CONFLICT,
        content={"detail": f"Database integrity constraint violation: {err_msg}"}
    )


app.include_router(candidate_router)
app.include_router(auth_router)
app.include_router(admin_router)


@app.get("/health", tags=["Health Check"])
async def health_check():
    return {"status": "ok", "service": "ta-assessment-api"}
