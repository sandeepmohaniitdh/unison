"""Serving stored files safely.

Every file is a download (Content-Disposition: attachment), with the content
type from our allowlist and X-Content-Type-Options: nosniff, so a browser
never runs an uploaded file as a page.
"""

from pathlib import Path
from urllib.parse import quote

from fastapi.responses import FileResponse

from app.core.errors import not_found


def file_download(path: Path, file_name: str, mime_type: str) -> FileResponse:
    if not path.exists():
        raise not_found("File")
    ascii_name = file_name.encode("ascii", "replace").decode().replace("?", "_").replace('"', "_")
    return FileResponse(
        path,
        media_type=mime_type,
        headers={
            "Content-Disposition": f"attachment; filename=\"{ascii_name}\"; filename*=UTF-8''{quote(file_name)}",
            "X-Content-Type-Options": "nosniff",
            "Cache-Control": "private, no-store",
        },
    )


FILE_RESPONSE = {
    200: {
        "content": {"application/octet-stream": {"schema": {"type": "string", "format": "binary"}}},
        "description": "The file, as a download",
    }
}
