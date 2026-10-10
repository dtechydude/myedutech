"""
Link helpers for the elearning app.

Everything here is pure Python (no model imports) so it can be used from
models, forms, views and template tags without circular imports.
"""
import re
from urllib.parse import parse_qs, urlparse

from django.core.exceptions import ValidationError

_YOUTUBE_HOSTS = {
    "youtube.com", "www.youtube.com", "m.youtube.com", "music.youtube.com",
    "youtube-nocookie.com", "www.youtube-nocookie.com", "youtu.be",
}
_YOUTUBE_ID_RE = re.compile(r"^[A-Za-z0-9_-]{11}$")

_DRIVE_HOSTS = {"drive.google.com", "docs.google.com"}
_ID = r"([A-Za-z0-9_-]+)"
# (path pattern, kind, embeddable preview URL template or None)
_DRIVE_PATHS = (
    (re.compile(r"/file/d/" + _ID), "file", "https://drive.google.com/file/d/{id}/preview"),
    (re.compile(r"/document/d/" + _ID), "document", "https://docs.google.com/document/d/{id}/preview"),
    (re.compile(r"/presentation/d/" + _ID), "slides", "https://docs.google.com/presentation/d/{id}/embed"),
    (re.compile(r"/spreadsheets/d/" + _ID), "sheet", "https://docs.google.com/spreadsheets/d/{id}/preview"),
    (re.compile(r"/folders/" + _ID), "folder", None),  # folders open in Drive, not embedded
)


def _parse(url):
    try:
        return urlparse((url or "").strip())
    except ValueError:
        return None


def validate_web_link(value):
    """Model/form validator: only plain http(s) web links are accepted."""
    parsed = _parse(value)
    if not parsed or parsed.scheme not in ("http", "https") or not parsed.netloc:
        raise ValidationError(
            "Enter a valid web link starting with http:// or https://",
            code="invalid_link",
        )


def extract_youtube_id(url):
    """Return the 11-character YouTube video id for any common YouTube URL, else None."""
    parsed = _parse(url)
    if not parsed:
        return None
    host = (parsed.hostname or "").lower()
    if host not in _YOUTUBE_HOSTS:
        return None

    candidate = None
    if host == "youtu.be":
        candidate = parsed.path.lstrip("/").split("/")[0]
    elif parsed.path.startswith("/watch"):
        candidate = parse_qs(parsed.query).get("v", [None])[0]
    else:
        parts = [p for p in parsed.path.split("/") if p]
        if len(parts) > 1 and parts[0] in {"embed", "shorts", "live", "v"}:
            candidate = parts[1]

    return candidate if candidate and _YOUTUBE_ID_RE.match(candidate) else None


def parse_drive_link(url):
    """
    Describe a Google Drive/Docs link, or return None if it is not one.
    `preview_url` is built only from a regex-validated id on a fixed Google
    host, so it is safe to place in an <iframe src>.
    """
    parsed = _parse(url)
    if not parsed or parsed.scheme not in ("http", "https"):
        return None
    if (parsed.hostname or "").lower() not in _DRIVE_HOSTS:
        return None

    clean_url = url.strip()
    for pattern, kind, template in _DRIVE_PATHS:
        match = pattern.search(parsed.path)
        if match:
            return {
                "url": clean_url, "is_drive": True, "kind": kind,
                "preview_url": template.format(id=match.group(1)) if template else None,
            }

    # Older share formats: drive.google.com/open?id=...  /uc?id=...
    file_id = parse_qs(parsed.query).get("id", [None])[0]
    if parsed.path in ("/open", "/uc") and file_id and re.fullmatch(r"[A-Za-z0-9_-]+", file_id):
        return {
            "url": clean_url, "is_drive": True, "kind": "file",
            "preview_url": f"https://drive.google.com/file/d/{file_id}/preview",
        }
    return {"url": clean_url, "is_drive": True, "kind": "link", "preview_url": None}


def resource_info(url):
    """Normalised description of any external resource link (None if unusable/unsafe)."""
    parsed = _parse(url)
    if not parsed or parsed.scheme not in ("http", "https") or not parsed.netloc:
        return None
    return parse_drive_link(url) or {
        "url": url.strip(), "is_drive": False, "kind": "link", "preview_url": None,
    }