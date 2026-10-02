import hashlib
from pathlib import PurePosixPath
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from python_multipart import MultipartParser
from python_multipart.exceptions import MultipartParseError
from python_multipart.multipart import parse_options_header

from ..models import User
from ..security import current_user
from .uploads import ALLOWED_TYPES, RISKY_EXTENSIONS

router = APIRouter(prefix="/analysis", tags=["analysis"])
MAX_MEDIA_BYTES = 20 * 1024 * 1024
MAX_OVERHEAD_BYTES = 16 * 1024


class MediaResponse(BaseModel):
    filename: str
    content_type: str
    size_bytes: int
    sha256: str
    verdict: Literal["unverified", "review"]
    flags: list[str]
    actions: list[str]
    malware_scanned: Literal[False] = False


def matches_signature(content_type: str, header: bytes) -> bool:
    signatures = {
        "image/jpeg": (b"\xff\xd8\xff",),
        "image/png": (b"\x89PNG\r\n\x1a\n",),
        "image/gif": (b"GIF87a", b"GIF89a"),
        "image/bmp": (b"BM",),
        "image/tiff": (b"II\x2a\x00", b"MM\x00\x2a"),
        "video/webm": (b"\x1a\x45\xdf\xa3",),
        "video/x-matroska": (b"\x1a\x45\xdf\xa3",),
        "video/mpeg": (b"\x00\x00\x01\xba", b"\x00\x00\x01\xb3"),
    }
    if content_type in signatures:
        return header.startswith(signatures[content_type])
    if content_type in {"image/webp", "video/x-msvideo"}:
        return header[:4] == b"RIFF" and header[8:12] == (b"WEBP" if content_type == "image/webp" else b"AVI ")
    if len(header) < 16 or header[4:8] != b"ftyp":
        return False
    brand = header[8:12]
    if content_type == "image/avif":
        return brand in {b"avif", b"avis"}
    if content_type == "video/quicktime":
        return brand == b"qt  "
    return content_type == "video/mp4" and brand in {b"isom", b"iso2", b"mp41", b"mp42", b"avc1", b"M4V ", b"MSNV", b"dash"}


@router.post("/media", response_model=MediaResponse)
async def screen_media(request: Request, user: User = Depends(current_user)):
    """Stream metadata screening without spooling or retaining the uploaded file."""
    media_type, options = parse_options_header(request.headers.get("content-type", ""))
    boundary = options.get(b"boundary", b"")
    if media_type != b"multipart/form-data" or not boundary or len(boundary) > 200:
        raise HTTPException(415, "Expected multipart/form-data with a valid boundary")
    digest = hashlib.sha256()
    size = 0
    prefix = bytearray()
    headers = {}
    header_name = bytearray()
    header_value = bytearray()
    header_bytes = 0
    parts = 0
    finished = False
    filename = ""
    content_type = ""

    def part_begin():
        nonlocal parts
        parts += 1
        if parts != 1:
            raise HTTPException(422, "Exactly one file part named 'file' is required")

    def header_data(target, data, start, end):
        nonlocal header_bytes
        header_bytes += end - start
        if header_bytes > MAX_OVERHEAD_BYTES:
            raise HTTPException(413, "Multipart headers are too large")
        target.extend(data[start:end])

    def header_end():
        key = bytes(header_name).lower()
        if key in headers:
            raise HTTPException(422, "Duplicate multipart header")
        headers[key] = bytes(header_value)
        header_name.clear()
        header_value.clear()

    def headers_finished():
        nonlocal filename, content_type
        disposition, fields = parse_options_header(headers.get(b"content-disposition", b""))
        if disposition != b"form-data" or fields.get(b"name") != b"file" or not fields.get(b"filename"):
            raise HTTPException(422, "A file part named 'file' with a filename is required")
        filename = PurePosixPath(fields[b"filename"].decode("utf-8", errors="replace").replace("\\", "/")).name
        content_type = headers.get(b"content-type", b"").decode("ascii", errors="replace").lower().strip()
        if content_type not in ALLOWED_TYPES or PurePosixPath(filename.lower()).suffix not in ALLOWED_TYPES[content_type]:
            raise HTTPException(415, "Unsupported or mismatched image/video extension and MIME type")

    def part_data(data, start, end):
        nonlocal size
        size += end - start
        if size > MAX_MEDIA_BYTES:
            raise HTTPException(413, "Upload exceeds the 20 MiB limit")
        digest.update(memoryview(data)[start:end])
        prefix.extend(data[start:min(end, start + 64 - len(prefix))])

    def end():
        nonlocal finished
        finished = True

    parser = MultipartParser(boundary, {
        "on_part_begin": part_begin,
        "on_header_field": lambda data, start, end: header_data(header_name, data, start, end),
        "on_header_value": lambda data, start, end: header_data(header_value, data, start, end),
        "on_header_end": header_end,
        "on_headers_finished": headers_finished,
        "on_part_data": part_data,
        "on_end": end,
    })
    received = 0
    try:
        async for chunk in request.stream():
            received += len(chunk)
            if received > MAX_MEDIA_BYTES + MAX_OVERHEAD_BYTES:
                raise HTTPException(413, "Upload exceeds the 20 MiB limit or multipart overhead limit")
            # Bound parser slices even if the ASGI server provides a large chunk.
            for offset in range(0, len(chunk), 64 * 1024):
                parser.write(chunk[offset:offset + 64 * 1024])
        parser.finalize()
    except MultipartParseError:
        raise HTTPException(422, "Malformed multipart upload")
    if not finished or parts != 1:
        raise HTTPException(422, "Incomplete multipart upload")
    if not size:
        raise HTTPException(422, "Empty uploads are not supported")
    if not matches_signature(content_type, bytes(prefix)):
        raise HTTPException(415, "File signature does not match the declared media type")
    flags = ["Metadata screening cannot establish malware-free status; file contents were not scanned for malware."]
    actions = ["Scan with trusted antivirus before opening; verify the source."]
    risky = bool(RISKY_EXTENSIONS.intersection(PurePosixPath(filename.lower()).suffixes))
    if risky:
        flags.append("Filename contains a potentially executable or active-content extension.")
        actions.append("Do not open until the filename and actual file type have been verified.")
    else:
        flags.append("Extension, declared MIME type, and basic magic signature are consistent; this does not establish safety.")
    return MediaResponse(filename=filename, content_type=content_type, size_bytes=size,
                         sha256=digest.hexdigest(), verdict="review" if risky else "unverified",
                         flags=flags, actions=actions)
