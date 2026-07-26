# KwikSchools — `finance` App

A complete rebuild of the old `payments` app: formal invoicing, receipts,
a printable/exportable fee table, expense tracking, and Profit & Loss
reporting — all in one modular, K‑12‑ready Django app.

## What's new vs. the old `payments` app

| Area | Old `payments` app | New `finance` app |
|---|---|---|
| Fee setup | `CategoryFee` + `ClassFeeTemplate` (two overlapping models) | Single `FeeStructure` model (class/term/session → amount) |
| Per-student variation | ❌ every student in a class billed identically | `StudentDiscount` (reduce an amount) + `StudentFeeException` (switch a fee on/off for one student) |
| Installment payments | ❌ only ad-hoc partial payments, no schedule | `InstallmentPlan` — defined due tranches with automatic paid/pending/overdue status |
| Invoicing | Implicit, via `StudentFeeAssignment` totals | Explicit `Invoice` + `InvoiceItem` — a real, printable, numbered document |
| Payments | Logic scattered across `views.py`/`utils.py`/model `save()` | Centralized in `services.py`, reused by web, admin, API |
| Receipts | Auto-created in `Payment.save()` | Auto-created via signal, decoupled from the model |
| Ledger | Single cached balance per student/term | Cached balance **plus** an auditable `StudentLedgerEntry` trail |
| Expenses | ❌ none | `ExpenseCategory`, `Vendor`, `Expense` with approval workflow |
| Profit & Loss | ❌ none | `services.get_profit_and_loss()` + printable/PDF report |
| Fee table | Basic HTML table | Grouped, printable, PDF-exportable fee schedule |
| REST API | ❌ none | Full DRF API for mobile app integration |
| Permissions | Django's default `is_staff` only | `finance_staff_required` / `finance_admin_required` + custom perms (`approve_expense`, `view_profit_loss`, `generate_invoices`) |

## 0. Prerequisites — what this app expects to already exist

This app is a drop-in replacement for `payments` and assumes the same
surrounding project shape it did:

- **`curriculum` app** with `Term`, `Session` (both with a boolean
  `is_current` field), and `Standard` (class/grade level) models, plus
  optionally `SchoolIdentity` (for the school name/address/logo shown on
  invoices & receipts — safe to omit, templates fall back gracefully).
- **`students` app** with a `Student` model exposing `get_full_name()`,
  `current_class` (FK to `Standard`), `parent` (FK to a `Parent` model),
  and ideally a `USN`/admission-number field, plus a `Parent` model.
- **A `pages` app** with a `pages:portal-home` URL — used as the "Back to
  Portal" link and various redirect targets. If your project names this
  differently, do a project-wide find/replace of `pages:portal-home` in
  `finance/views.py`, `finance/permissions.py`, and
  `finance/templates/finance/base_finance.html`.

If any of these differ in your project, the fix is almost always a
one-line adjustment in `finance/models.py`'s imports or the affected view
— everything else (services, forms, templates) is independent of those
specifics.

## 1. Install

Copy the `finance/` folder into your project root (next to `students`,
`curriculum`, `payments`, etc.).

```bash
pip install xhtml2pdf djangorestframework django-filter django-import-export --break-system-packages
```

`django-import-export` is optional — the admin gracefully falls back to
plain `ModelAdmin` if it isn't installed.

## 2. `settings.py`

```python
INSTALLED_APPS = [
    ...
    "rest_framework",          # if not already present
    "django_filters",          # if not already present
    "import_export",           # optional
    "finance",
    # You can remove "payments" once you've migrated (see step 6).
]

# Optional — defaults to "₦" if not set.
FINANCE_CURRENCY_SYMBOL = "₦"
```

Make sure `django.template.context_processors.request` and
`django.contrib.messages.context_processors.messages` are in your
`TEMPLATES[0]["OPTIONS"]["context_processors"]` — both are Django defaults
and are required by the finance templates (for the messages framework and
`request.GET` filter forms).

## 3. `urls.py` (project root)

```python
urlpatterns = [
    ...
    path("finance/", include("finance.urls")),
    path("api/finance/", include("finance.api_urls")),   # optional, for the mobile app
]
```

## 4. Migrations

```bash
python manage.py makemigrations finance
python manage.py migrate
```

## 5. Set up permission groups (recommended)

```python
# In the Django admin, or via a data migration:
from django.contrib.auth.models import Group, Permission

bursary = Group.objects.create(name="Bursary Staff")
bursary.permissions.add(
    *Permission.objects.filter(content_type__app_label="finance")
)

finance_admin = Group.objects.create(name="Finance Admin")
finance_admin.permissions.add(
    Permission.objects.get(codename="approve_expense"),
    Permission.objects.get(codename="view_profit_loss"),
    Permission.objects.get(codename="generate_invoices"),
    Permission.objects.get(codename="export_financial_reports"),
)
```

Then assign your bursary/accounts staff to "Bursary Staff", and your
principal/proprietor to "Finance Admin" (who can see Profit & Loss and
approve expenses).

## 6. Migrating data from the old `payments` app (optional)

If you have existing production data in `payments`, run the bundled
one-time migration command (keep the old `payments` app in
`INSTALLED_APPS` until this finishes):

```bash
python manage.py migrate_from_payments --dry-run   # preview counts first
python manage.py migrate_from_payments              # actually migrate
python manage.py sync_finance_ledgers                # recompute balances
```

Once you've verified the data looks right in `/admin/finance/`, you can
remove `payments` from `INSTALLED_APPS` and drop its tables.

## 7. Everyday workflows

**Set up fees for a term** — *Finance → Fee Categories* (e.g. Tuition,
Hostel, Transport) → *Finance → Fee Structure* (how much each class pays,
per category, per term/session).

**Generate invoices for a whole class** — *Finance → Invoices → Bulk
Generate*, or call `finance.services.bulk_generate_invoices(...)`
programmatically (e.g. from a "promote to next class" or "new term"
signal in your `curriculum` app).

**Give a student a discount/scholarship** — *Finance → Discounts &
Concessions → Grant Discount*. This is how two students in the same class
end up owing different amounts: a `StudentDiscount` is a rule ("20% off
Tuition for this student", "50% off everything, every term — staff
ward", "₦15,000 off Hostel this session only") that's applied automatically
whenever that student's invoice is generated or refreshed. Granting or
editing a discount immediately refreshes that student's existing
invoice(s) so the balance is correct right away — no separate "recalculate"
step needed. See `finance/models.py::StudentDiscount` for the exact scope
rules (blank category/term/session = wider match) and note that if a
student qualifies for more than one matching rule, only the single
**largest** reduction is applied (they don't stack).

**Exclude/include a fee for just one student in a class** — *Finance →
Fee Exceptions → Add Exception*. This is separate from discounts (which
reduce an amount) — exceptions switch a fee **on or off** for one student
without touching anyone else's invoice:

- *"New students pay a Registration Fee, returning students don't"* — set
  the `FeeStructure` row to `is_mandatory=True` (so it's billed to the
  whole class by default, since new intakes are usually the majority),
  then add an **Exclude** exception for each returning student. Everyone
  else keeps paying it untouched.
- *"One student requested an extra uniform set mid-term"* — set the
  `FeeStructure` row for that item to `is_mandatory=False` (so nobody is
  billed by default), then add an **Include** exception for just that
  student. No other student's invoice is affected.

Either direction works for either scenario — pick whichever default
(mandatory-with-exclusions, or optional-with-inclusions) matches the
minority/majority split for that particular fee. Adding or removing an
exception refreshes that student's existing invoice for the matching
term/session immediately.

**Set up an installment plan** — open any invoice as staff and click
*Set Up Installments*. Generate an equal-split schedule (e.g. "3
installments, 30 days apart, starting 1 Sept") and fine-tune individual
amounts, labels, or due dates afterward — useful for uneven splits like
"60% at resumption, 40% at mid-term". Parents keep paying exactly the
same way they always would (staff-recorded, self-service, or a verified
bank transfer) — nothing about *how* payments are made changes. The plan
just adds a read-only breakdown to the invoice showing which installment(s)
a student's cumulative payments have covered, and flags anything overdue.
Payments aren't manually assigned to a specific installment — they're
allocated automatically, oldest-due-first, via
`services.get_installment_breakdown()`.

**Record a payment** — *Finance → Record Payment* (staff) or
`/finance/payments/parent/make/` (parents, restricted to their own
children's invoices). Every completed payment automatically:
1. creates a numbered `Receipt`,
2. updates the `Invoice` status (`partial`/`paid`),
3. updates the `StudentAccountLedger` cached balance.

**Print/export the fee table** — *Finance → Printable Fee Table* →
filter by class/term/session → **Print** or **Download PDF**.

**Track expenses** — *Finance → Expenses → Record Expense*. Attach a
scanned receipt/invoice from the vendor. Optionally requires approval via
the `finance.approve_expense` permission.

**View Profit & Loss** — *Finance → Reports → Profit & Loss* (requires
`finance.view_profit_loss`). Filter by date range or term/session; export
to PDF for board/proprietor reports.

## 7b. Staff vs. parent/student experience

**Recording a payment no longer means scrolling a giant student dropdown.**
*Finance → Record Payment* now opens a class-filterable, searchable
student directory (`finance:payment_directory`) with each student's
current-term balance and two action buttons per row: **Record Payment**
(jumps into the payment form with that student already selected and their
invoices pre-loaded) and **Invoices** (jumps to their invoice list). The
bare search-by-name form (`finance:make_payment`) still exists as a
fallback/direct link, and now also accepts `?student=<id>` to arrive
pre-selected — that's what the directory's buttons use.

## 7c. Bug fixes worth knowing about

**Blank invoice numbers.** Numbering used to be assigned by a `post_save`
signal in `signals.py`, registered via `AppConfig.ready()`. If that
registration doesn't fire for any reason in a given project setup
(autoreload timing, an app-loading quirk), the number is silently never
set. Numbering now happens directly inside `Invoice.save()` /
`Receipt.save()` — it runs on every single code path that creates one
(a direct `.save()`, `get_or_create()`, the admin, the API), with no
dependency on signal wiring at all. `signals.py` no longer does any
numbering; it only handles receipt auto-creation, invoice status sync,
and ledger sync.

**Missing Receipt column/link on the invoice list.** Added
`Invoice.latest_receipt` (the receipt for that invoice's most recent
completed payment, if any) and a Receipt column in `invoice_list.html`
linking straight to it. `InvoiceListView` prefetches
`payments__receipt` so this doesn't cost an extra query per row.

**Ledgers not appearing / showing a 0 balance.** Two issues, now both
fixed: (1) `generate_invoice_for_student` now explicitly calls
`sync_student_ledger()` at the end instead of relying purely on the
`InvoiceItem` signal cascade — a student with zero matching fee-structure
rows would otherwise never get a ledger row at all. (2) The Django admin
let staff manually "Add" a `StudentAccountLedger` with just
student/term/session — since nothing recomputes `total_invoiced`/
`total_paid`/`balance` on a bare admin-created row, this always produced
a stuck 0-balance row. Manual creation is now disabled entirely
(`has_add_permission` returns `False`); staff instead select existing
rows and use the **Recalculate balance from invoices/payments** admin
action, or click **Resync Ledgers** on the Debtors Report page for a
one-click, no-shell-access fix.

**Grant Student Discount (and similar) forms showing an empty student
dropdown.** Root cause: `StudentClassFilterMixin` swapped in a new
`StudentClassAwareSelect` widget *after* the field's `queryset` had
already been set. Django only copies `field.choices` onto
`field.widget.choices` at the moment `queryset` is assigned — replacing
the widget afterward leaves it with zero options, regardless of whether
a class filter was applied. Fixed by explicitly re-syncing
`widget.choices = field.choices` right after the swap. This affected
every form using the mixin (Record Payment, Create Invoice, Grant
Discount, Add Fee Exception, staff-submitted Payment Notifications) —
all fixed at once since they share the same mixin.

**Grant Discount / Add Fee Exception now reachable from the Student
Directory.** The same class-filterable student list built for Record
Payment (see below) now also has **Grant Discount** and **Add Fee
Exception** actions per row (under a "More" dropdown), landing on the
respective form with that student already selected via `?student=<id>`
— no more picking from a dropdown for the common case. The sidebar link
is now labeled "Student Directory" since it's the general hub for
per-student actions, not just payments.

## 7d. Mobile navigation & branding

The sidebar is a proper off-canvas drawer on tablet/mobile (≤991px) —
collapsed by default, opened with a hamburger button in the top bar,
closed by tapping the backdrop, the × button, or any nav link. It no
longer dumps the entire menu inline above the page content on small
screens. On desktop it stays as a fixed sidebar, unchanged.

Colors are driven by CSS variables at the top of `base_finance.html` /
`base_finance_portal.html`:

```css
--kw-primary: #13233f;      /* sidebar background */
--kw-accent: #e8483d;       /* buttons, active nav item, badges, focus rings */
--kw-accent-soft: #fdeceb;  /* icon chip backgrounds on dashboard cards */
```

Adjust these three values to re-theme the whole app — they cascade into
Bootstrap's `.btn-primary`, `.btn-outline-primary`, pagination, badges,
and form focus states automatically, so you won't find scattered hard-coded
hex values elsewhere in the templates.

`/finance/` is a single URL that shows a different thing depending on who's
logged in — there's no shared "one dashboard for everyone" screen:

- **Staff** (`is_staff` or superuser) get the full admin dashboard
  (`finance/dashboard.html`) with the complete sidebar
  (`base_finance.html`): fee setup, invoicing, expenses, reports, everything.
- **Parents/students** get a personal "My Finance" summary
  (`finance/student_dashboard.html`) via a separate, minimal sidebar
  (`base_finance_portal.html`) — only their own invoices, payment
  history/receipts, the current term's fee table, and a way to pay or
  submit proof of payment. They never see fee-structure setup, bank
  account details, expenses, or other students' records — those views are
  now gated by `FinanceStaffRequiredMixin` (see below).
- **The printable fee table is locked for non-staff** — parents/students
  always see the current term/session only, with no filter controls;
  staff retain full filtering by class/term/session.

If you add new staff-only views to this app, apply
`finance.permissions.FinanceStaffRequiredMixin` (class-based views) or
the `@finance_staff_required` decorator (function views) — don't rely on
`LoginRequiredMixin`/`@login_required` alone, since those only check that
*someone* is logged in, not *who*.

**Class filter for staff student-pickers** — anywhere staff have to pick
a student out of the whole school (Record Payment, Create Invoice, Grant
Discount, Add Fee Exception, staff-submitted Payment Notification), a
"Filter by Class" dropdown narrows the list instantly with no page reload
— see `finance.forms.StudentClassFilterMixin` / `StudentClassAwareSelect`.
To add this to a new form with a `student` field, mix in
`StudentClassFilterMixin` and call `self._enable_student_class_filter()`
in `__init__`; the corresponding template just needs
`{% if form.classes %}` around a small filter `<select>` (copy the block
from `payment_form.html`).

## 8. Wiring in your real base template

Every "in-app" page (dashboard, lists, forms) extends
`finance/base_finance.html`, a self-contained sidebar shell so the app
works out of the box. To match your existing site chrome instead, either:

- **Edit `finance/base_finance.html` directly** to extend your real
  `pages/portal_home.html` and drop in the finance nav links, **or**
- **Override `BASE_TEMPLATE`** in `finance/views.py` (top of the file) to
  point at your own template — as long as your base template defines a
  `{% block content %}`, everything else keeps working unchanged.

Printable documents (invoices, receipts, the fee table, and the P&L /
debtors reports) are intentionally **standalone** HTML documents (not
extending any base template) so they print/export cleanly.

## 9. Customizing PDF rendering

PDFs are rendered with `xhtml2pdf` via `finance.services.render_to_pdf()`,
kept deliberately simple (table-based CSS, no flexbox/grid) since
`xhtml2pdf` has limited CSS support. If you outgrow it, swap the
implementation for [WeasyPrint](https://weasyprint.org/) — the function
signature (`render_to_pdf(template_src, context_dict, filename=...)`) is
the only thing other code depends on, so it's a one-file change.

## 10. Extending

- **New fee category?** Add it under *Finance → Fee Categories* — no code
  change needed; it will show up in fee structure setup, invoices,
  payments, and P&L breakdowns automatically (it's data-driven).
- **New expense category?** Same — *Finance → Expense Categories*.
- **Automated overdue invoice marking:** call
  `finance.services.sync_invoice_status(invoice)` from a nightly cron/
  management command (or wire up Celery Beat) to flip invoices to
  `overdue` once `due_date` has passed.
- **Online payment gateway (Paystack/Flutterwave, etc.):** have your
  webhook handler call `finance.services.record_payment(...)` with
  `payment_method='online_gateway'` and the gateway's reference as
  `transaction_id` — everything else (receipt, ledger, invoice status) is
  handled for you.

## 10b. Independent parent dashboard (optional, per-school)

If your project already has a parent dashboard built against the old
`payments` app (academic reports + invoices + receipts + balance, all on
one page), `finance/views_parent_dashboard.py` is a drop-in alternative
that sources the *financial* sections from `finance` instead — the
academic sections (mid-term scores, full termly reports, prep cards,
session reports) are copied verbatim so both versions behave identically
outside of the money parts.

This is completely independent of everything else in the app:

- **New file, new template, new URL** — `finance/views_parent_dashboard.py`,
  `finance/templates/finance/parent_dashboard.html`,
  `finance:parent_dashboard` (`/finance/parent-dashboard/`).
- **Nothing in `students`/`payments` is touched.** Your existing
  payments-app dashboard keeps working exactly as it does today.
- **You choose which one a given school uses** — point that school's nav
  link/menu item at `finance:parent_dashboard` instead of the old one, or
  run both side by side (e.g. behind a feature flag, a school-level
  setting, or just two different nav items) and decide per deployment.

What it does differently from the payments-app version:
- Invoices tab reads from `InvoiceItem`/`Invoice` instead of
  `StudentFeeAssignment`, and adds a status badge + "View" link to the
  full printable invoice.
- Receipts tab reads from `Payment`/`Receipt` instead of the old
  `Payment` model, with the same defensive `{% if payment.receipt %}`
  guard used throughout the rest of the app (a completed payment without
  a receipt shows "Processing…" instead of crashing).
- Adds a **Pay Now** button per child (routes to
  `finance:make_parent_payment?student=<id>`, arriving with that child
  already selected) and a **Make a Payment** link in the top nav,
  alongside the existing **Submit Payment Proof** link — parents can
  either pay through the portal directly or submit proof of an offline
  bank transfer, same as everywhere else in the app.
- Total billed/paid/balance are all-time totals (not filtered by term),
  matching the original's exact scope.

If your `results`/`curriculum`/`prep_reports` apps are named or shaped
differently than assumed, the only thing to adjust is the three inline
imports at the top of `parent_dashboard()` in
`finance/views_parent_dashboard.py` — none of the finance-specific logic
depends on them.

## 11. Tests

```bash
python manage.py test finance
```

Covers invoice generation, partial/full payment recording, receipt
numbering, ledger sync, debtor listing, and Profit & Loss totals.
