from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import RequestValidationError
from fastapi.exception_handlers import request_validation_exception_handler
from fastapi.responses import JSONResponse

from .routes import analysis, auth, media, uploads

from .config import settings

app = FastAPI(title="ScamShield API", version="2.0.0")


@app.exception_handler(RequestValidationError)
async def authentication_validation_error(request, error):
    if request.url.path.startswith("/v1/auth/"):
        # Never echo password/challenge inputs (including invalid UTF-8) in errors.
        return JSONResponse(status_code=422, content={"detail": "Invalid authentication input"})
    return await request_validation_exception_handler(request, error)


@app.middleware("http")
async def authentication_cache_control(request, call_next):
    response = await call_next(request)
    if request.url.path.startswith("/v1/auth/"):
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


@app.get("/health")
def health():
    return {"status": "ok"}
