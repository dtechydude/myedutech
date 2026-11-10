# core/l10n_patch.py
"""
Global fix: integers (IDs, pks, years, counts) must never get thousand separators
when rendered in templates. Decimal/float values (money) still do.
If a plain integer must show separators, use {{ value|intcomma }} explicitly.
"""
from django.template import base as template_base
from django.utils import formats

_original_localize = formats.localize


def _localize_without_int_grouping(value, use_l10n=None):
    # bool is a subclass of int, so exclude it and let Django handle it normally
    if isinstance(value, int) and not isinstance(value, bool):
        return str(value)
    return _original_localize(value, use_l10n=use_l10n)


def apply_integer_localization_patch():
    # django.template.base imports `localize` by name, so patch it there.
    # Guard so a second ready() call can't double-wrap it.
    if getattr(template_base.localize, "_kwik_patched", False):
        return
    _localize_without_int_grouping._kwik_patched = True
    template_base.localize = _localize_without_int_grouping