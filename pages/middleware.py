# core/middleware.py
import re

from django.conf import settings

# Matches digit groups like "1,520" or "12,345,678" (comma, space, NBSP, narrow NBSP)
_GROUPED_INT = re.compile(r"^\d{1,3}(?:[,\u00a0\u202f ]\d{3})+$")
_SEPARATORS = re.compile(r"[,\u00a0\u202f ]")

DEFAULT_ID_PARAM_NAMES = {
    "id", "pk", "student", "invoice", "payment", "receipt", "fee", "class",
    "classroom", "session", "term", "parent", "teacher", "staff", "subject",
    "item", "hostel", "route", "exam", "assignment", "lesson", "course",
}


class NormalizeIdParamsMiddleware:
    """
    Strips thousand separators from ID-like GET/POST params
    (e.g. ?student=1,520 -> ?student=1520) before any view runs.
    Extend the list with ID_PARAM_NAMES in settings.py.
    """

    def __init__(self, get_response):
        self.get_response = get_response
        self.id_names = set(getattr(settings, "ID_PARAM_NAMES", DEFAULT_ID_PARAM_NAMES))

    def __call__(self, request):
        request.GET = self._clean(request.GET)
        if request.method == "POST" and request.content_type in (
            "application/x-www-form-urlencoded",
            "multipart/form-data",
        ):
            request.POST = self._clean(request.POST)
        return self.get_response(request)

    def _is_id_key(self, key):
        return key in self.id_names or key.endswith(("_id", "_pk"))

    def _clean(self, querydict):
        cleaned = None
        for key in list(querydict.keys()):
            if not self._is_id_key(key):
                continue
            values = querydict.getlist(key)
            new_values = [
                _SEPARATORS.sub("", v) if _GROUPED_INT.match(v.strip()) else v
                for v in values
            ]
            if new_values != values:
                if cleaned is None:
                    cleaned = querydict.copy()  # QueryDict.copy() is mutable
                cleaned.setlist(key, new_values)
        return cleaned if cleaned is not None else querydict