import hashlib
from pathlib import PurePosixPath

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from pydantic import BaseModel

from ..models import User
from ..security import current_user

router = APIRouter(prefix="/analysis", tags=["analysis"])
MAX_UPLOAD_BYTES = 25 * 1024 * 1024
ALLOWED_TYPES = {
    "image/jpeg": {".jpg", ".jpeg"},
    "image/png": {".png"},
    "image/gif": {".gif"},
    "image/webp": {".webp"},
    "image/bmp": {".bmp"},
    "image/tiff": {".tif", ".tiff"},
    "image/avif": {".avif"},
    "video/mp4": {".mp4", ".m4v"},
    "video/webm": {".webm"},
    "video/quicktime": {".mov"},
    "video/x-msvideo": {".avi"},
    "video/mpeg": {".mpeg", ".mpg"},
    "video/x-matroska": {".mkv"},
}
RISKY_EXTENSIONS = {".exe", ".com", ".bat", ".cmd", ".ps1", ".js", ".vbs", ".scr", ".msi", ".html", ".svg"}


class UploadResponse(BaseModel):
    filename: str
    content_type: str
    size: int
    hash: str
    risk: int
    verdict: str
    flags: list[str]
    actions: list[str]


@router.post("/upload", response_model=UploadResponse)
async def screen_upload(file: UploadFile = File(...), user: User = Depends(current_user)):
    """Deterministic metadata screening only; not antivirus or media-content detection."""
    try:
        content_type = (file.content_type or "").lower()
        if content_type not in ALLOWED_TYPES:
            raise HTTPException(status_code=415, detail="Unsupported image or video MIME type")
        size = 0
        digest = hashlib.sha256()
        while chunk := await file.read(1024 * 1024):
            size += len(chunk)
            if size > MAX_UPLOAD_BYTES:
                raise HTTPException(status_code=413, detail="Upload exceeds the 25 MiB limit")
            digest.update(chunk)
        if size == 0:
            raise HTTPException(status_code=422, detail="Empty uploads are not supported")

        filename = PurePosixPath((file.filename or "upload").replace("\\", "/")).name
        suffixes = PurePosixPath(filename.lower()).suffixes
        flags = ["Metadata-only screening; file contents were not scanned for malware or harmful imagery."]
        actions = ["Scan with trusted antivirus before opening; verify the source."]
        risk = 0
        if not suffixes or suffixes[-1] not in ALLOWED_TYPES[content_type]:
            risk += 40
            flags.append("Filename extension does not match the declared MIME type.")
        if RISKY_EXTENSIONS.intersection(suffixes):
            risk += 60
            flags.append("Filename contains a potentially executable or active-content extension.")
        if risk:
            actions.append("Do not open until the filename and actual file type have been verified.")
        else:
            flags.append("No filename/MIME inconsistencies found; this does not establish safety.")
        return UploadResponse(
            filename=filename, content_type=content_type, size=size, hash=digest.hexdigest(),
            risk=risk, verdict="high-risk" if risk >= 60 else "review" if risk else "unverified",
            flags=flags, actions=actions,
        )
    finally:
        await file.close()
