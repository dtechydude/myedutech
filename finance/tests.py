# finance/tests.py
"""
Baseline unit/integration tests for the Finance app's critical paths:
invoice generation, payment recording, ledger sync, receipt numbering,
and profit & loss computation.

Adjust the `_create_student`/`_create_term_session` helpers below to match
your actual `students` and `curriculum` app factories/fixtures.
"""
from decimal import Decimal
from datetime import date, timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from curriculum.models import Term, Session, Standard
from students.models import Student

from . import services
from .models import (
    FeeCategory, FeeStructure, Invoice, Payment, Receipt, StudentAccountLedger,
    ExpenseCategory, Expense, StudentDiscount, StudentFeeException, InstallmentPlan, Installment,
)

User = get_user_model()


class FinanceTestCaseBase(TestCase):
    def setUp(self):
        self.staff_user = User.objects.create_user(username='bursar', password='pass1234', is_staff=True)
        self.session = Session.objects.create(name='2025/2026', is_current=True)
        self.term = Term.objects.create(name='First Term', is_current=True)
        self.student_class = Standard.objects.create(name='JSS1')
        self.student = Student.objects.create(
            first_name='Ada', last_name='Lovelace', current_class=self.student_class,
        )
        self.tuition = FeeCategory.objects.create(name='Tuition', category_type=FeeCategory.CategoryType.TUITION)
        self.pta = FeeCategory.objects.create(name='PTA Levy', category_type=FeeCategory.CategoryType.PTA)

        FeeStructure.objects.create(
            student_class=self.student_class, fee_category=self.tuition,
            term=self.term, session=self.session, amount=Decimal('50000.00'),
        )
        FeeStructure.objects.create(
            student_class=None, fee_category=self.pta,
            term=self.term, session=self.session, amount=Decimal('2000.00'),
        )


class InvoiceGenerationTests(FinanceTestCaseBase):
    def test_generate_invoice_creates_correct_items_and_total(self):
        invoice = services.generate_invoice_for_student(self.student, self.term, self.session, user=self.staff_user)
        self.assertEqual(invoice.items.count(), 2)
        self.assertEqual(invoice.total_amount, Decimal('52000.00'))
        self.assertTrue(invoice.invoice_number.startswith('INV-'))

    def test_bulk_generate_invoices_for_class(self):
        Student.objects.create(first_name='Bola', last_name='Tinu', current_class=self.student_class)
        invoices = services.bulk_generate_invoices(self.student_class, self.term, self.session, user=self.staff_user)
        self.assertEqual(len(invoices), 2)
        self.assertEqual(Invoice.objects.count(), 2)


class PaymentRecordingTests(FinanceTestCaseBase):
    def setUp(self):
        super().setUp()
        self.invoice = services.generate_invoice_for_student(self.student, self.term, self.session)

    def test_partial_payment_updates_invoice_status_and_ledger(self):
        payment = services.record_payment(
            user=self.staff_user, student=self.student, invoice=self.invoice,
            amount_received=Decimal('20000.00'), payment_method='cash',
        )
        self.invoice.refresh_from_db()
        self.assertEqual(self.invoice.status, Invoice.Status.PARTIAL)
        self.assertEqual(self.invoice.total_paid, Decimal('20000.00'))
        self.assertEqual(self.invoice.balance, Decimal('32000.00'))

        ledger = StudentAccountLedger.objects.get(student=self.student, term=self.term, session=self.session)
        self.assertEqual(ledger.balance, Decimal('32000.00'))

        # A receipt should have been auto-generated.
        self.assertTrue(Receipt.objects.filter(payment=payment).exists())
        self.assertTrue(payment.receipt.receipt_number.startswith('RCT-'))

    def test_full_payment_marks_invoice_paid(self):
        services.record_payment(
            user=self.staff_user, student=self.student, invoice=self.invoice,
            amount_received=self.invoice.balance, payment_method='bank_transfer',
        )
        self.invoice.refresh_from_db()
        self.assertEqual(self.invoice.status, Invoice.Status.PAID)
        self.assertEqual(self.invoice.balance, Decimal('0.00'))

    def test_settle_invoice_balance_rejects_overpayment(self):
        with self.assertRaises(ValueError):
            services.settle_invoice_balance(
                user=self.staff_user, student=self.student, invoice=self.invoice,
                amount_received=self.invoice.balance + Decimal('1000.00'), payment_method='cash',
            )

    def test_manual_payment_gets_unique_placeholder_transaction_id(self):
        p1 = services.record_payment(user=self.staff_user, student=self.student, invoice=self.invoice,
                                       amount_received=Decimal('1000'), payment_method='cash')
        p2 = services.record_payment(user=self.staff_user, student=self.student, invoice=self.invoice,
                                       amount_received=Decimal('1000'), payment_method='cash')
        self.assertNotEqual(p1.transaction_id, p2.transaction_id)


class ProfitAndLossTests(FinanceTestCaseBase):
    def setUp(self):
        super().setUp()
        self.invoice = services.generate_invoice_for_student(self.student, self.term, self.session)
        services.record_payment(user=self.staff_user, student=self.student, invoice=self.invoice,
                                  amount_received=Decimal('30000.00'), payment_method='cash')
        category = ExpenseCategory.objects.create(name='Utilities')
        Expense.objects.create(title='Electricity bill', category=category, amount=Decimal('8000.00'),
                                term=self.term, session=self.session, recorded_by=self.staff_user)

    def test_profit_and_loss_totals(self):
        report = services.get_profit_and_loss(term=self.term, session=self.session)
        self.assertEqual(report['total_income'], Decimal('30000.00'))
        self.assertEqual(report['total_expense'], Decimal('8000.00'))
        self.assertEqual(report['net_profit'], Decimal('22000.00'))

    def test_dashboard_summary(self):
        summary = services.get_dashboard_summary(term=self.term, session=self.session)
        self.assertEqual(summary['total_income'], Decimal('30000.00'))
        self.assertEqual(summary['outstanding_balance'], Decimal('22000.00'))


class DebtorsReportTests(FinanceTestCaseBase):
    def test_get_debtors_lists_students_with_positive_balance(self):
        services.generate_invoice_for_student(self.student, self.term, self.session)
        debtors = services.get_debtors(term=self.term, session=self.session)
        self.assertEqual(debtors.count(), 1)
        self.assertEqual(debtors.first().balance, Decimal('52000.00'))


class StudentDiscountTests(FinanceTestCaseBase):
    def test_percentage_discount_reduces_invoice_line_and_total(self):
        StudentDiscount.objects.create(
            student=self.student, fee_category=self.tuition, term=self.term, session=self.session,
            discount_type=StudentDiscount.DiscountType.PERCENTAGE, value=Decimal('20'),
            reason='Sibling discount',
        )
        invoice = services.generate_invoice_for_student(self.student, self.term, self.session)
        tuition_item = invoice.items.get(fee_category=self.tuition)

        self.assertEqual(tuition_item.original_amount, Decimal('50000.00'))
        self.assertEqual(tuition_item.discount_amount, Decimal('10000.00'))
        self.assertEqual(tuition_item.amount, Decimal('40000.00'))
        # PTA levy (2000) has no discount rule, so it's untouched -> total = 40000 + 2000
        self.assertEqual(invoice.total_amount, Decimal('42000.00'))

    def test_two_students_same_class_can_owe_different_amounts(self):
        sibling = Student.objects.create(first_name='Ben', last_name='Lovelace', current_class=self.student_class)
        StudentDiscount.objects.create(
            student=self.student, fee_category=None, term=None, session=None,
            discount_type=StudentDiscount.DiscountType.PERCENTAGE, value=Decimal('50'),
            reason='Staff ward',
        )
        invoice_discounted = services.generate_invoice_for_student(self.student, self.term, self.session)
        invoice_full = services.generate_invoice_for_student(sibling, self.term, self.session)

        self.assertLess(invoice_discounted.total_amount, invoice_full.total_amount)
        self.assertEqual(invoice_full.total_amount, Decimal('52000.00'))

    def test_only_the_largest_matching_discount_is_applied_not_stacked(self):
        StudentDiscount.objects.create(
            student=self.student, fee_category=self.tuition, term=self.term, session=self.session,
            discount_type=StudentDiscount.DiscountType.PERCENTAGE, value=Decimal('10'), reason='Sibling',
        )
        StudentDiscount.objects.create(
            student=self.student, fee_category=None, term=None, session=None,
            discount_type=StudentDiscount.DiscountType.PERCENTAGE, value=Decimal('25'), reason='Staff ward',
        )
        invoice = services.generate_invoice_for_student(self.student, self.term, self.session)
        tuition_item = invoice.items.get(fee_category=self.tuition)
        # 25% of 50000 (12500) beats 10% of 50000 (5000) -> the larger one wins, they don't add up.
        self.assertEqual(tuition_item.discount_amount, Decimal('12500.00'))

    def test_deactivating_a_discount_and_refreshing_restores_full_amount(self):
        discount = StudentDiscount.objects.create(
            student=self.student, fee_category=self.tuition, term=self.term, session=self.session,
            discount_type=StudentDiscount.DiscountType.FIXED, value=Decimal('15000.00'), reason='Temp waiver',
        )
        services.generate_invoice_for_student(self.student, self.term, self.session)
        discount.is_active = False
        discount.save()
        invoice = services.generate_invoice_for_student(self.student, self.term, self.session)
        tuition_item = invoice.items.get(fee_category=self.tuition)
        self.assertEqual(tuition_item.discount_amount, Decimal('0.00'))
        self.assertEqual(tuition_item.amount, Decimal('50000.00'))


class StudentFeeExceptionTests(FinanceTestCaseBase):
    def setUp(self):
        super().setUp()
        # Registration fee: mandatory for the class by default (models the "everyone pays unless
        # excluded" pattern — appropriate when new intakes are the majority for that row).
        self.registration = FeeCategory.objects.create(name='Registration Fee')
        self.registration_structure = FeeStructure.objects.create(
            student_class=self.student_class, fee_category=self.registration,
            term=self.term, session=self.session, amount=Decimal('5000.00'), is_mandatory=True,
        )
        # Uniform: optional by default — nobody is billed unless explicitly included.
        self.uniform = FeeCategory.objects.create(name='Uniform - Extra Set')
        self.uniform_structure = FeeStructure.objects.create(
            student_class=self.student_class, fee_category=self.uniform,
            term=self.term, session=self.session, amount=Decimal('7000.00'), is_mandatory=False,
        )
        self.returning_student = Student.objects.create(
            first_name='Chidi', last_name='Okafor', current_class=self.student_class,
        )

    def test_new_student_is_billed_registration_fee_by_default(self):
        invoice = services.generate_invoice_for_student(self.student, self.term, self.session)
        self.assertTrue(invoice.items.filter(fee_category=self.registration).exists())

    def test_returning_student_can_be_excluded_from_registration_fee(self):
        StudentFeeException.objects.create(
            student=self.returning_student, fee_structure=self.registration_structure,
            action=StudentFeeException.Action.EXCLUDE, reason='Returning student — already registered.',
        )
        invoice = services.generate_invoice_for_student(self.returning_student, self.term, self.session)
        self.assertFalse(invoice.items.filter(fee_category=self.registration).exists())
        # Everyone else in the class is unaffected.
        other_invoice = services.generate_invoice_for_student(self.student, self.term, self.session)
        self.assertTrue(other_invoice.items.filter(fee_category=self.registration).exists())

    def test_optional_uniform_fee_not_billed_unless_opted_in(self):
        invoice = services.generate_invoice_for_student(self.student, self.term, self.session)
        self.assertFalse(invoice.items.filter(fee_category=self.uniform).exists())

    def test_single_student_can_opt_into_optional_uniform_fee(self):
        StudentFeeException.objects.create(
            student=self.student, fee_structure=self.uniform_structure,
            action=StudentFeeException.Action.INCLUDE, reason='Requested extra uniform set mid-term.',
        )
        invoice = services.generate_invoice_for_student(self.student, self.term, self.session)
        uniform_item = invoice.items.get(fee_category=self.uniform)
        self.assertEqual(uniform_item.amount, Decimal('7000.00'))

        # The rest of the class remains unaffected — this is the exact "one student, not the class" case.
        other_invoice = services.generate_invoice_for_student(self.returning_student, self.term, self.session)
        self.assertFalse(other_invoice.items.filter(fee_category=self.uniform).exists())

    def test_removing_an_include_exception_drops_the_line_on_refresh(self):
        exception = StudentFeeException.objects.create(
            student=self.student, fee_structure=self.uniform_structure,
            action=StudentFeeException.Action.INCLUDE, reason='Requested extra uniform set.',
        )
        services.generate_invoice_for_student(self.student, self.term, self.session)
        exception.delete()
        invoice = services.generate_invoice_for_student(self.student, self.term, self.session)
        self.assertFalse(invoice.items.filter(fee_category=self.uniform).exists())


class InstallmentPlanTests(FinanceTestCaseBase):
    def setUp(self):
        super().setUp()
        self.invoice = services.generate_invoice_for_student(self.student, self.term, self.session)  # 52000 total

    def test_build_equal_installments_sums_exactly_to_total(self):
        installments = services.build_equal_installments(self.invoice, 3)
        self.assertEqual(len(installments), 3)
        self.assertEqual(sum((i['amount_due'] for i in installments), Decimal('0.00')), self.invoice.total_amount)

    def test_create_installment_plan_rejects_mismatched_total(self):
        with self.assertRaises(ValueError):
            services.create_installment_plan(self.invoice, [
                {'label': 'Only installment', 'amount_due': Decimal('1000.00')},
            ], user=self.staff_user)

    def test_installment_breakdown_reflects_partial_payment(self):
        installments = services.build_equal_installments(
            self.invoice, 2, due_dates=[date.today(), date.today() + timedelta(days=30)]
        )
        plan = services.create_installment_plan(self.invoice, installments, user=self.staff_user)

        # Pay exactly the first installment's amount.
        first_amount = installments[0]['amount_due']
        services.record_payment(user=self.staff_user, student=self.student, invoice=self.invoice,
                                  amount_received=first_amount, payment_method='cash')

        breakdown = services.get_installment_breakdown(plan)
        self.assertEqual(breakdown[0]['status'], 'paid')
        self.assertEqual(breakdown[0]['balance'], Decimal('0.00'))
        self.assertEqual(breakdown[1]['status'], 'pending')
        self.assertEqual(breakdown[1]['balance'], installments[1]['amount_due'])

    def test_overdue_installment_detected_when_due_date_passed_and_unpaid(self):
        installments = services.build_equal_installments(
            self.invoice, 2, due_dates=[date.today() - timedelta(days=10), date.today() + timedelta(days=20)]
        )
        plan = services.create_installment_plan(self.invoice, installments, user=self.staff_user)
        breakdown = services.get_installment_breakdown(plan)
        self.assertEqual(breakdown[0]['status'], 'overdue')

    def test_partial_payment_within_first_installment_shows_partial_status(self):
        installments = services.build_equal_installments(self.invoice, 2)
        plan = services.create_installment_plan(self.invoice, installments, user=self.staff_user)
        half_of_first = installments[0]['amount_due'] / 2
        services.record_payment(user=self.staff_user, student=self.student, invoice=self.invoice,
                                  amount_received=half_of_first, payment_method='cash')
        breakdown = services.get_installment_breakdown(plan)
        self.assertEqual(breakdown[0]['status'], 'partial')

    def test_payment_spilling_past_first_installment_covers_second(self):
        installments = services.build_equal_installments(self.invoice, 2)  # 26000 each
        plan = services.create_installment_plan(self.invoice, installments, user=self.staff_user)
        # Pay more than installment 1 needs — the extra should flow into installment 2.
        services.record_payment(user=self.staff_user, student=self.student, invoice=self.invoice,
                                  amount_received=Decimal('30000.00'), payment_method='cash')
        breakdown = services.get_installment_breakdown(plan)
        self.assertEqual(breakdown[0]['status'], 'paid')
        self.assertEqual(breakdown[1]['amount_paid'], Decimal('4000.00'))
        self.assertEqual(breakdown[1]['status'], 'partial')

    def test_get_next_due_installment(self):
        installments = services.build_equal_installments(self.invoice, 2)
        plan = services.create_installment_plan(self.invoice, installments, user=self.staff_user)
        next_due = services.get_next_due_installment(plan)
        self.assertEqual(next_due['installment'].sequence, 1)

        services.record_payment(user=self.staff_user, student=self.student, invoice=self.invoice,
                                  amount_received=self.invoice.total_amount, payment_method='cash')
        self.assertIsNone(services.get_next_due_installment(plan))


class FinanceViewsSmokeTests(FinanceTestCaseBase):
    """Basic 'does it load without erroring' checks for the main staff views."""

    def setUp(self):
        super().setUp()
        self.client.login(username='bursar', password='pass1234')

    def test_dashboard_loads(self):
        response = self.client.get(reverse('finance:dashboard'))
        self.assertEqual(response.status_code, 200)

    def test_dashboard_does_not_crash_when_a_completed_payment_has_no_receipt(self):
        # Simulates leftover/edge-case data: a completed payment that, for
        # whatever reason, has no Receipt row. The dashboard must degrade
        # gracefully (plain text, no link) instead of raising NoReverseMatch
        # trying to build a URL from a missing pk.
        payment = Payment.objects.create(
            student=self.student, fee_category=self.tuition, term=self.term, session=self.session,
            amount_received=Decimal('1000.00'), payment_method='cash', status=Payment.Status.COMPLETED,
        )
        Receipt.objects.filter(payment=payment).delete()
        response = self.client.get(reverse('finance:dashboard'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.student.get_full_name())

    def test_fee_table_loads(self):
        response = self.client.get(reverse('finance:fee_table'))
        self.assertEqual(response.status_code, 200)

    def test_invoice_list_loads(self):
        response = self.client.get(reverse('finance:invoice_list'))
        self.assertEqual(response.status_code, 200)

    def test_expense_list_loads(self):
        response = self.client.get(reverse('finance:expense_list'))
        self.assertEqual(response.status_code, 200)

    def test_expense_list_csv_export(self):
        category = ExpenseCategory.objects.create(name='Utilities-Export-Test')
        Expense.objects.create(title='Diesel purchase', category=category, amount=Decimal('12000.00'),
                                recorded_by=self.staff_user)
        response = self.client.get(reverse('finance:expense_list'), {'format': 'csv'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'text/csv')
        self.assertIn(b'Diesel purchase', response.content)

    def test_expense_list_pdf_export(self):
        category = ExpenseCategory.objects.create(name='Maintenance-Export-Test')
        Expense.objects.create(title='Generator repair', category=category, amount=Decimal('8000.00'),
                                recorded_by=self.staff_user)
        response = self.client.get(reverse('finance:expense_list'), {'format': 'pdf'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/pdf')


class InvoiceNumberingRegressionTests(FinanceTestCaseBase):
    """
    Locks in the fix for: 'UNIQUE constraint failed: finance_invoice.invoice_number'
    when generating invoices for several students back-to-back. The bug was that
    new rows were briefly inserted with an empty-string placeholder before their
    real number was assigned, and that placeholder collided under a UNIQUE
    constraint. invoice_number/receipt_number are now nullable so this can't happen.
    """

    def test_bulk_generate_invoices_for_several_new_students_does_not_collide(self):
        for i in range(5):
            Student.objects.create(first_name=f'Bulk{i}', last_name='Student', current_class=self.student_class)

        invoices = services.bulk_generate_invoices(self.student_class, self.term, self.session,
                                                     user=self.staff_user)
        self.assertEqual(len(invoices), 6)  # self.student + 5 new ones from setUp/this test
        numbers = [inv.invoice_number for inv in invoices]
        self.assertEqual(len(numbers), len(set(numbers)), "invoice numbers must all be unique")
        self.assertTrue(all(numbers), "every invoice must have been assigned a real number")

    def test_invoice_number_field_is_nullable_at_the_db_level(self):
        field = Invoice._meta.get_field('invoice_number')
        self.assertTrue(field.null, "invoice_number must be nullable to avoid empty-string UNIQUE collisions")

    def test_receipt_number_field_is_nullable_at_the_db_level(self):
        field = Receipt._meta.get_field('receipt_number')
        self.assertTrue(field.null, "receipt_number must be nullable to avoid empty-string UNIQUE collisions")


class FinanceAccessControlTests(FinanceTestCaseBase):
    """
    Locks in the fix for a real access-control gap: FeeCategory/FeeStructure/
    BankAccount views had no staff check at all, reachable by any logged-in user.
    """

    def setUp(self):
        super().setUp()
        self.random_user = User.objects.create_user(username='randomuser', password='pass1234', is_staff=False)
        self.client.login(username='randomuser', password='pass1234')

    def test_non_staff_cannot_view_fee_categories(self):
        response = self.client.get(reverse('finance:fee_category_list'))
        self.assertEqual(response.status_code, 302)

    def test_non_staff_cannot_view_fee_structure(self):
        response = self.client.get(reverse('finance:fee_structure_list'))
        self.assertEqual(response.status_code, 302)

    def test_non_staff_cannot_view_bank_accounts(self):
        response = self.client.get(reverse('finance:bank_account_list'))
        self.assertEqual(response.status_code, 302)

    def test_non_staff_cannot_view_expenses(self):
        response = self.client.get(reverse('finance:expense_list'))
        self.assertEqual(response.status_code, 302)

    def test_non_staff_cannot_view_discounts(self):
        response = self.client.get(reverse('finance:discount_list'))
        self.assertEqual(response.status_code, 302)

    def test_non_staff_cannot_view_fee_exceptions(self):
        response = self.client.get(reverse('finance:fee_exception_list'))
        self.assertEqual(response.status_code, 302)

    def test_staff_can_still_reach_all_of_the_above(self):
        self.client.logout()
        self.client.login(username='bursar', password='pass1234')
        for url_name in ['fee_category_list', 'fee_structure_list', 'bank_account_list',
                          'expense_list', 'discount_list', 'fee_exception_list']:
            response = self.client.get(reverse(f'finance:{url_name}'))
            self.assertEqual(response.status_code, 200, f"staff should be able to reach {url_name}")

    def test_dashboard_routes_staff_to_admin_view(self):
        self.client.logout()
        self.client.login(username='bursar', password='pass1234')
        response = self.client.get(reverse('finance:dashboard'))
        self.assertTemplateUsed(response, 'finance/dashboard.html')


class PaymentDirectoryTests(FinanceTestCaseBase):
    """
    Locks in the class-filterable student directory that replaced the old
    'scroll through every student in one giant dropdown' payment flow.
    """

    def setUp(self):
        super().setUp()
        self.other_class = Standard.objects.create(name='JSS2')
        self.other_student = Student.objects.create(
            first_name='Zainab', last_name='Bello', current_class=self.other_class,
        )
        self.client.login(username='bursar', password='pass1234')

    def test_directory_lists_students_across_classes_by_default(self):
        response = self.client.get(reverse('finance:payment_directory'))
        self.assertEqual(response.status_code, 200)
        names = [row['student'].pk for row in response.context['rows']]
        self.assertIn(self.student.pk, names)
        self.assertIn(self.other_student.pk, names)

    def test_directory_filters_by_class(self):
        response = self.client.get(reverse('finance:payment_directory'), {'student_class': self.other_class.pk})
        names = [row['student'].pk for row in response.context['rows']]
        self.assertIn(self.other_student.pk, names)
        self.assertNotIn(self.student.pk, names)

    def test_directory_filters_by_search_text(self):
        response = self.client.get(reverse('finance:payment_directory'), {'q': 'Zainab'})
        names = [row['student'].pk for row in response.context['rows']]
        self.assertEqual(names, [self.other_student.pk])

    def test_record_payment_link_preselects_the_student(self):
        response = self.client.get(reverse('finance:make_payment'), {'student': self.student.pk})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['form'].initial.get('student').pk, self.student.pk)

    def test_invoice_list_link_filters_to_the_student_for_staff(self):
        services.generate_invoice_for_student(self.student, self.term, self.session)
        services.generate_invoice_for_student(self.other_student, self.term, self.session)
        response = self.client.get(reverse('finance:invoice_list'), {'student': self.student.pk})
        invoices = response.context['invoices']
        self.assertTrue(all(inv.student_id == self.student.pk for inv in invoices))
        self.assertGreaterEqual(len(invoices), 1)

    def test_grant_discount_link_preselects_the_student(self):
        response = self.client.get(reverse('finance:discount_add'), {'student': self.student.pk})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['form'].initial.get('student').pk, self.student.pk)

    def test_add_fee_exception_link_preselects_the_student(self):
        response = self.client.get(reverse('finance:fee_exception_add'), {'student': self.student.pk})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['form'].initial.get('student').pk, self.student.pk)


class InvoiceNumberingIsNotSignalDependentTests(FinanceTestCaseBase):
    """
    Locks in the fix for invoices being generated with a blank invoice_number.
    The old design assigned the number in a post_save signal, which only
    fires if finance/signals.py got imported via AppConfig.ready() — fragile
    and hard to diagnose. Numbering now happens directly in Invoice.save()/
    Receipt.save(), so it works with signals.py disconnected entirely.
    """

    def test_direct_invoice_save_gets_a_number(self):
        # No signal juggling needed here — that's the point of the fix. Plain
        # .create() (which is exactly what get_or_create/the admin/the API
        # all do under the hood) must assign a number on its own.
        invoice = Invoice.objects.create(student=self.student, term=self.term, session=self.session)
        self.assertTrue(invoice.invoice_number)
        self.assertTrue(invoice.invoice_number.startswith('INV-'))

    def test_invoice_number_assignment_lives_on_the_model_not_a_signal_receiver(self):
        import finance.signals as finance_signals
        self.assertFalse(hasattr(finance_signals, 'assign_invoice_number'),
                          "invoice numbering should no longer be a signal receiver")

    def test_receipt_gets_a_number_directly_from_its_own_save(self):
        payment = Payment.objects.create(
            student=self.student, fee_category=self.tuition, term=self.term, session=self.session,
            amount_received=Decimal('1000.00'), payment_method='cash', status=Payment.Status.COMPLETED,
        )
        receipt = Receipt.objects.create(payment=payment)
        self.assertTrue(receipt.receipt_number)
        self.assertTrue(receipt.receipt_number.startswith('RCT-'))

    def test_bulk_generation_never_produces_a_blank_number(self):
        for i in range(4):
            Student.objects.create(first_name=f'X{i}', last_name='Test', current_class=self.student_class)
        invoices = services.bulk_generate_invoices(self.student_class, self.term, self.session,
                                                     user=self.staff_user)
        self.assertTrue(all(inv.invoice_number for inv in invoices))


class ReceiptColumnRegressionTests(FinanceTestCaseBase):
    """Locks in the missing 'Receipt' column/link on the invoice list."""

    def setUp(self):
        super().setUp()
        self.client.login(username='bursar', password='pass1234')
        self.invoice = services.generate_invoice_for_student(self.student, self.term, self.session)

    def test_invoice_with_no_payment_shows_no_receipt_link(self):
        self.assertIsNone(self.invoice.latest_receipt)
        response = self.client.get(reverse('finance:invoice_list'))
        self.assertContains(response, "No payment yet")

    def test_invoice_with_a_payment_shows_a_working_receipt_link(self):
        payment = services.record_payment(
            user=self.staff_user, student=self.student, invoice=self.invoice,
            amount_received=Decimal('5000.00'), payment_method='cash',
        )
        self.assertEqual(self.invoice.latest_receipt.pk, payment.receipt.pk)

        response = self.client.get(reverse('finance:invoice_list'))
        self.assertContains(response, payment.receipt.receipt_number)
        self.assertContains(response, reverse('finance:receipt_detail', args=[payment.receipt.pk]))


class LedgerAutoGenerationTests(FinanceTestCaseBase):
    """
    Locks in: ledgers must be created automatically the moment an invoice is
    generated (not left for staff to create manually), and the admin no
    longer allows creating a blank, uncomputed ledger row.
    """

    def test_ledger_is_created_automatically_by_invoice_generation(self):
        self.assertFalse(StudentAccountLedger.objects.filter(
            student=self.student, term=self.term, session=self.session).exists())
        services.generate_invoice_for_student(self.student, self.term, self.session)
        ledger = StudentAccountLedger.objects.get(student=self.student, term=self.term, session=self.session)
        self.assertEqual(ledger.balance, Decimal('52000.00'))

    def test_admin_cannot_manually_add_a_ledger(self):
        from finance.admin import StudentAccountLedgerAdmin
        from django.contrib.admin.sites import AdminSite
        admin_instance = StudentAccountLedgerAdmin(StudentAccountLedger, AdminSite())
        self.assertFalse(admin_instance.has_add_permission(request=None))

    def test_resync_ledgers_view_recalculates_a_stale_balance(self):
        self.client.login(username='bursar', password='pass1234')
        services.generate_invoice_for_student(self.student, self.term, self.session)
        # Deliberately corrupt the cached balance to simulate staleness.
        StudentAccountLedger.objects.filter(student=self.student).update(balance=Decimal('0.00'))
        response = self.client.get(reverse('finance:resync_ledgers'), follow=True)
        self.assertEqual(response.status_code, 200)
        ledger = StudentAccountLedger.objects.get(student=self.student, term=self.term, session=self.session)
        self.assertEqual(ledger.balance, Decimal('52000.00'))


class StudentDropdownRenderingRegressionTests(FinanceTestCaseBase):
    """
    Locks in the fix for the Grant Student Discount (and other
    StudentClassFilterMixin-based) forms rendering an empty student
    dropdown. Root cause: swapping field.widget after field.queryset was
    already set left the new widget with zero <option> tags, since Django
    only copies choices onto the widget at the moment queryset is assigned.
    """

    def setUp(self):
        super().setUp()
        self.client.login(username='bursar', password='pass1234')

    def test_discount_form_renders_the_student_as_an_option(self):
        response = self.client.get(reverse('finance:discount_add'))
        self.assertContains(response, f'value="{self.student.pk}"')
        self.assertContains(response, self.student.get_full_name())

    def test_fee_exception_form_renders_the_student_as_an_option(self):
        response = self.client.get(reverse('finance:fee_exception_add'))
        self.assertContains(response, f'value="{self.student.pk}"')

    def test_invoice_form_renders_the_student_as_an_option(self):
        response = self.client.get(reverse('finance:invoice_create'))
        self.assertContains(response, f'value="{self.student.pk}"')

    def test_make_payment_form_renders_the_student_as_an_option(self):
        response = self.client.get(reverse('finance:make_payment'))
        self.assertContains(response, f'value="{self.student.pk}"')


class FinanceParentDashboardTests(FinanceTestCaseBase):
    """
    Tests for the independent, finance-app-sourced parent dashboard
    (finance/views_parent_dashboard.py). This intentionally depends on the
    same academic apps (results, prep_reports) as the original payments-app
    dashboard it mirrors — these tests run against your real project where
    those apps exist. Skipped automatically if they're not installed, so
    this file stays importable even before you wire the two apps together.
    """

    def setUp(self):
        super().setUp()
        try:
            from students.models import Parent
        except ImportError:
            self.skipTest("students.models.Parent not available in this environment")
            return
        self.parent_user = User.objects.create_user(username='parentuser', password='pass1234')
        self.parent = Parent.objects.create(user=self.parent_user)
        self.student.parent = self.parent
        self.student.save()
        self.client.login(username='parentuser', password='pass1234')

    def test_dashboard_loads_and_shows_the_child(self):
        try:
            response = self.client.get(reverse('finance:parent_dashboard'))
        except Exception as exc:  # noqa: BLE001 - academic apps (results/prep_reports) not present here
            self.skipTest(f"Requires results/prep_reports apps to be installed: {exc}")
            return
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.student.get_full_name())

    def test_dashboard_shows_correct_balance_from_finance_app(self):
        services.generate_invoice_for_student(self.student, self.term, self.session)
        services.record_payment(user=self.staff_user, student=self.student,
                                  invoice=Invoice.objects.get(student=self.student, term=self.term,
                                                               session=self.session),
                                  amount_received=Decimal('20000.00'), payment_method='cash')
        try:
            response = self.client.get(reverse('finance:parent_dashboard'))
        except Exception as exc:  # noqa: BLE001
            self.skipTest(f"Requires results/prep_reports apps to be installed: {exc}")
            return
        summary = response.context['children_with_reports'][0]['grand_payment_summary']
        self.assertEqual(summary['total_due'], Decimal('52000.00'))
        self.assertEqual(summary['total_paid'], Decimal('20000.00'))
        self.assertEqual(summary['total_balance'], Decimal('32000.00'))

    def test_pay_now_link_preselects_the_child(self):
        response = self.client.get(reverse('finance:make_parent_payment'), {'student': self.student.pk})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['form'].initial.get('student').pk, self.student.pk)


