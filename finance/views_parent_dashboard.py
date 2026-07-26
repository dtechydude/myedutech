# finance/views_parent_dashboard.py
"""
An OPTIONAL, self-contained alternative to the existing (payments-app-based)
parent dashboard. Sources financial data - invoices, receipts, balances -
from the `finance` app instead of the legacy `payments` app. Everything
else on the page (academic reports, prep cards, session reports) is copied
verbatim from the original view/template so both dashboards look and
behave identically outside of the financial sections.

Deliberately kept in its own file, its own template, and its own URL:
    - Nothing here is imported by, or imports from, the `payments` app.
    - students/views.py and students/parent_dashboard.html are untouched.
    - Wire finance:parent_dashboard into your nav/urls wherever a given
      school should use the finance-app version instead of the payments-app
      one - the two can coexist indefinitely, per-school, side by side.

If your project's academic apps are named differently, adjust only the
three inline imports below (results, curriculum, prep_reports) - the
finance-specific logic doesn't depend on them at all.
"""
from decimal import Decimal

from django.contrib.auth.decorators import login_required
from django.db.models import Sum
from django.shortcuts import render

from students.models import Student, Parent

from .models import Invoice, InvoiceItem, Payment


@login_required
def parent_dashboard(request):
    from results.models import ResultPublication, SessionResultStatus
    from curriculum.models import Session, Term
    from prep_reports.models import PrepReportCard

    try:
        parent = Parent.objects.get(user=request.user)
        children = Student.objects.filter(parent=parent).prefetch_related('scores__term')
    except Parent.DoesNotExist:
        children = []

    children_with_reports = []

    all_terms = Term.objects.all().order_by('id')
    all_sessions = Session.objects.all().order_by('id')

    current_session = Session.objects.filter(is_current=True).order_by('-name').first()
    current_term = Term.objects.filter(session=current_session, is_current=True).order_by('-start_date').first()

    for child in children:

        # =====================================================
        # FINANCE APP DATA (this is the only part that differs
        # from students.views.parent_dashboard)
        # =====================================================
        invoice_items = InvoiceItem.objects.filter(
            invoice__student=child
        ).exclude(invoice__status=Invoice.Status.CANCELLED).select_related(
            'invoice', 'invoice__term', 'invoice__session', 'fee_category'
        ).order_by('-invoice__issue_date', '-id')

        receipts = Payment.objects.filter(
            student=child, status=Payment.Status.COMPLETED
        ).select_related('fee_category', 'receipt', 'invoice').order_by('-payment_date', '-id')

        child_data = {
            'child': child,
            'termly_reports': [],
            'session_reports': [],
            'invoices': invoice_items,
            'receipts': receipts,
            'grand_payment_summary': {},
            'current_term': current_term,
            'current_session': current_session,
        }

        # =====================================================
        # PREP REPORTS (unchanged from the payments-app version)
        # =====================================================
        published_prep_cards = (
            PrepReportCard.objects.filter(
                student=child,
                status='published'
            )
            .select_related('period', 'period__term', 'period__session')
        )

        prep_term_ids = set()

        for card in published_prep_cards:
            if card.period and card.period.term:
                prep_term_ids.add(card.period.term.id)

                child_data['termly_reports'].append({
                    'is_prep': True,
                    'prep_card': card,
                    'term': card.period.term,
                })

        # =====================================================
        # TERM PUBLICATION (unchanged)
        # =====================================================

        published_term_ids = set(
            ResultPublication.objects.filter(
                student=child,
                is_published=True
            ).values_list('term_id', flat=True)
        )

        for term in all_terms:

            if term.id in prep_term_ids:
                continue

            if term.id not in published_term_ids:
                continue

            if child.scores.filter(term=term).exists():
                child_data['termly_reports'].append({
                    'is_prep': False,
                    'term': term,
                })

        # =====================================================
        # SESSION REPORTS (unchanged)
        # =====================================================

        published_session_ids = set(
            SessionResultStatus.objects.filter(
                student=child,
                is_published=True
            ).values_list('session_id', flat=True)
        )

        for session in all_sessions:
            if (
                session.id in published_session_ids and
                child.scores.filter(term__session=session).exists()
            ):
                child_data['session_reports'].append(session)

        # =====================================================
        # FINANCIAL SUMMARY (finance app - all-time totals, same
        # scope as the payments-app version: not filtered by term)
        # =====================================================

        total_due = invoice_items.aggregate(total=Sum('amount')).get('total') or Decimal('0.00')
        total_paid = receipts.aggregate(total=Sum('amount_received')).get('total') or Decimal('0.00')
        total_balance = total_due - total_paid

        child_data['grand_payment_summary'] = {
            'total_due': total_due,
            'total_paid': total_paid,
            'total_balance': total_balance,
            'is_paid': total_balance <= 0,
        }

        # =====================================================
        # SORT REPORTS (unchanged)
        # =====================================================

        child_data['termly_reports'].sort(
            key=lambda x: (
                x['term'].start_date if x.get('term') else None
            ),
            reverse=True
        )

        children_with_reports.append(child_data)

    context = {
        'children_with_reports': children_with_reports,
    }

    return render(request, 'finance/parent_dashboard.html', context)
