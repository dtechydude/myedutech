from django.test import TestCase

# Create your tests here.
from decimal import Decimal

from django.template import Context, Template
from django.test import RequestFactory, SimpleTestCase, override_settings

from pages.middleware import NormalizeIdParamsMiddleware


@override_settings(USE_THOUSAND_SEPARATOR=True)
class IntegerLocalizationTests(SimpleTestCase):
    def render(self, value):
        return Template("{{ v }}").render(Context({"v": value}))

    def test_integer_has_no_separator(self):
        self.assertEqual(self.render(1520), "1520")

    def test_decimal_money_keeps_separator(self):
        self.assertEqual(self.render(Decimal("1520.50")), "1,520.50")


class NormalizeIdParamsTests(SimpleTestCase):
    def test_grouped_id_is_cleaned(self):
        seen = {}
        mw = NormalizeIdParamsMiddleware(lambda r: seen.update(r.GET.dict()) or None)
        mw(RequestFactory().get("/finance/payments/make/", {"student": "1,520", "q": "1,520"}))
        self.assertEqual(seen["student"], "1520")
        self.assertEqual(seen["q"], "1,520")  # non-ID params untouched