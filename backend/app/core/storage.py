"""Uploaded files.

Files are stored under random 32-character names on the uploads volume, never
under the name the user gave. Each upload is checked against an allowlist by
extension and by the file's first bytes (its signature), its size is limited
while it streams, and its SHA-256 is computed on the way.
ZIP files are stored as they are and never extracted.
"""

import hashlib
import os
import secrets
from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO

from app.core.errors import AppError, unprocessable

PDF = "application/pdf"
ZIP = "application/zip"

# extension -> (MIME type, accepted signatures)
_OLE = (b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1",)
_ZIPSIG = (b"PK\x03\x04", b"PK\x05\x06")
FILE_TYPES = {
    ".pdf": (PDF, (b"%PDF-",)),
    ".zip": (ZIP, _ZIPSIG),
    ".doc": ("application/msword", _OLE),
    ".docx": ("application/vnd.openxmlformats-officedocument.wordprocessingml.document", _ZIPSIG),
    ".ppt": ("application/vnd.ms-powerpoint", _OLE),
    ".pptx": ("application/vnd.openxmlformats-officedocument.presentationml.presentation", _ZIPSIG),
    ".xls": ("application/vnd.ms-excel", _OLE),
    ".xlsx": ("application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", _ZIPSIG),
    ".txt": ("text/plain", None),  # checked separately: valid UTF-8, no NUL bytes
    ".png": ("image/png", (b"\x89PNG\r\n\x1a\n",)),
    ".jpg": ("image/jpeg", (b"\xff\xd8\xff",)),
    ".jpeg": ("image/jpeg", (b"\xff\xd8\xff",)),
}

SUBMISSION_EXTENSIONS = {".pdf", ".zip"}
RESOURCE_EXTENSIONS = set(FILE_TYPES)

MB = 1024 * 1024


@dataclass
class StoredFile:
    key: str
    file_name: str
    mime_type: str
    size_bytes: int
    sha256: str


def safe_file_name(name: str | None) -> str:
    base = os.path.basename((name or "file").replace("\\", "/")).strip()
    cleaned = "".join(ch for ch in base if ch.isprintable() and ch not in '"<>|:*?')
    return (cleaned or "file")[:255]


def _check_signature(ext: str, head: bytes, text_sample: bytes) -> None:
    mime, signatures = FILE_TYPES[ext]
    if signatures is None:
        if b"\x00" in text_sample:
            raise unprocessable("FILE_TYPE_MISMATCH", "This does not look like a plain text file.")
        try:
            text_sample.decode("utf-8")
        except UnicodeDecodeError as exc:
            # A multi-byte character may be cut at the end of the sample.
            if exc.start < len(text_sample) - 3:
                raise unprocessable("FILE_TYPE_MISMATCH", "Text files must be UTF-8.") from exc
        return
    if not any(head.startswith(sig) for sig in signatures):
        raise unprocessable(
            "FILE_TYPE_MISMATCH",
            f"The file's content does not match its {ext} extension.",
        )


class LocalStorage:
    def __init__(self, base_dir: str):
        self.base = Path(base_dir)

    def path(self, key: str) -> Path:
        if len(key) != 32 or not key.isalnum():
            raise ValueError("bad storage key")
        return self.base / key[:2] / key

    def save(self, stream: BinaryIO, file_name: str | None, allowed: set[str], max_bytes: int) -> StoredFile:
        name = safe_file_name(file_name)
        ext = os.path.splitext(name)[1].lower()
        if ext not in allowed:
            raise unprocessable(
                "FILE_TYPE_NOT_ALLOWED",
                f"{ext or 'Files without an extension'} not allowed. Allowed: {', '.join(sorted(allowed))}.",
            )
        key = secrets.token_hex(16)
        target = self.path(key)
        target.parent.mkdir(parents=True, exist_ok=True)
        digest = hashlib.sha256()
        size = 0
        head = b""
        try:
            with open(target, "wb") as out:
                while chunk := stream.read(64 * 1024):
                    if len(head) < 4096:
                        head += chunk[: 4096 - len(head)]
                    size += len(chunk)
                    if size > max_bytes:
                        raise AppError(
                            413,
                            "FILE_TOO_LARGE",
                            f"{name} is larger than {max_bytes // MB} MB.",
                        )
                    digest.update(chunk)
                    out.write(chunk)
            if size == 0:
                raise unprocessable("FILE_EMPTY", f"{name} is empty.")
            _check_signature(ext, head, head)
        except Exception:
            target.unlink(missing_ok=True)
            raise
        return StoredFile(key, name, FILE_TYPES[ext][0], size, digest.hexdigest())

    def save_bytes(self, data: bytes, file_name: str, mime_type: str) -> StoredFile:
        """For the seed script: store known-good bytes without checks."""
        key = secrets.token_hex(16)
        target = self.path(key)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        return StoredFile(key, file_name, mime_type, len(data), hashlib.sha256(data).hexdigest())

    def read_bytes(self, key: str) -> bytes:
        return self.path(key).read_bytes()

    def delete(self, key: str) -> None:
        self.path(key).unlink(missing_ok=True)
