from fastapi import FastAPI, Depends, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import RequestValidationError
from fastapi.exception_handlers import request_validation_exception_handler
from fastapi.responses import JSONResponse

from .routes import analysis, auth, media, uploads

from .config import settings
from .routes import privacy
from .privacy_logging import PRIVATE_PREFIXES, install_redaction
from .ownership import require_authority, AuthorityUnavailable
from .database import get_db

install_redaction()

def restoration_guard(request: Request, db=Depends(get_db)):
    if request.url.path.startswith(PRIVATE_PREFIXES):
        require_authority(db)


app = FastAPI(title="ScamShield API", version="2.0.0", dependencies=[Depends(restoration_guard)])


@app.exception_handler(RequestValidationError)
async def authentication_validation_error(request, error):
    if request.url.path.startswith("/v1/auth/"):
        # Never echo password/challenge inputs (including invalid UTF-8) in errors.
        return JSONResponse(status_code=422, content={"detail": "Invalid authentication input"})
    if request.url.path.startswith(PRIVATE_PREFIXES):
        return JSONResponse(status_code=422, content={"detail": "Invalid private input"})
    return await request_validation_exception_handler(request, error)


@app.middleware("http")
async def authentication_cache_control(request, call_next):
    try:
        response = await call_next(request)
    except AuthorityUnavailable:
        response = JSONResponse(status_code=503, content={"detail": "Restoration fencing unavailable"})
    except Exception:
        if not request.url.path.startswith(PRIVATE_PREFIXES):
            raise
        # SQL/transport exception representations can include private parameters.
        response = JSONResponse(status_code=503, content={"detail": "Private operation unavailable"})
    if request.url.path.startswith(PRIVATE_PREFIXES):
        response.headers["Cache-Control"] = "no-store"
        response.headers["Pragma"] = "no-cache"
    return response


app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(auth.router)
app.include_router(analysis.router)
app.include_router(uploads.router)
app.include_router(media.router)
app.include_router(privacy.router)


@app.get("/health")
def health():
    return {"status": "ok"}
