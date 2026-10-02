from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .database import Base, engine
from .routes import analysis, auth, media, uploads

Base.metadata.create_all(bind=engine)
from .config import settings

app = FastAPI(title="ScamShield API", version="2.0.0")
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
