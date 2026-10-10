"""
Google link helpers for the Teacher Lesson Notes feature.

Pure Python (no model imports) so models, forms and views can all use it.
This module is deliberately self-contained: the lesson-notes feature does not
import anything from the rest of the elearning app.
"""
import re
from urllib.parse import parse_qs, urlparse

from django.core.exceptions import ValidationError

_HOSTS = {'docs.google.com', 'drive.google.com'}
_ID = r'([A-Za-z0-9_-]+)'
# `(?:u/\d+/)?` handles links copied while signed in to several Google accounts.
_PATTERNS = (
    (re.compile(r'/document/(?:u/\d+/)?d/' + _ID), 'document', 'Google Doc', 'fa-file-alt'),
    (re.compile(r'/spreadsheets/(?:u/\d+/)?d/' + _ID), 'sheet', 'Google Sheet', 'fa-file-excel'),
    (re.compile(r'/presentation/(?:u/\d+/)?d/' + _ID), 'slides', 'Google Slides', 'fa-file-powerpoint'),
    (re.compile(r'/file/(?:u/\d+/)?d/' + _ID), 'file', 'Drive file', 'fa-file'),
)


def _parse(url):
    try:
        return urlparse((url or '').strip())
    except ValueError:
        return None


def parse_note_link(url):
    """
    Describe a Google Docs/Sheets/Slides/Drive-file link, or None if it is not one.
    Returns {'kind', 'label', 'icon', 'file_id', 'url'}.
    """
    parsed = _parse(url)
    if not parsed or parsed.scheme not in ('http', 'https'):
        return None
    if (parsed.hostname or '').lower() not in _HOSTS:
        return None

    for pattern, kind, label, icon in _PATTERNS:
        match = pattern.search(parsed.path)
        if match:
            return {'kind': kind, 'label': label, 'icon': icon,
                    'file_id': match.group(1), 'url': url.strip()}

    # Older share format: drive.google.com/open?id=...  /uc?id=...
    file_id = parse_qs(parsed.query).get('id', [None])[0]
    if parsed.path in ('/open', '/uc') and file_id and re.fullmatch(r'[A-Za-z0-9_-]+', file_id):
        return {'kind': 'file', 'label': 'Drive file', 'icon': 'fa-file',
                'file_id': file_id, 'url': url.strip()}
    return None


def validate_google_note_link(value):
    """Model/form validator: the link must open a Google Doc, Sheet, Slides or Drive file."""
    parsed = _parse(value)
    if parsed and '/folders/' in parsed.path:
        raise ValidationError(
            'That is a folder link. Open the lesson note file itself and copy ITS link.',
            code='folder_link',
        )
    if parse_note_link(value) is None:
        raise ValidationError(
            'Paste the link of a Google Doc, Sheet, Slides, or a file stored in Google Drive.',
            code='invalid_note_link',
        )