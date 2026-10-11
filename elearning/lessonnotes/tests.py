from io import StringIO
from unittest import mock

from django.apps import apps
from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse

from . import services
from ..notices.models import Notification
from .forms import NoteForm, subject_standard_field
from .links import parse_note_link, validate_google_note_link
from .models import LessonNote, LessonNoteEvent

User = get_user_model()
TEACHER_PATCH = 'elearning.lessonnotes.permissions.is_teacher'
DOC = 'https://docs.google.com/document/d/1AbC_dEf/edit?usp=sharing'


def make_standard():
    """The project's own `curriculum.Standard`; skip (don't fail) if it needs extra required fields."""
    Standard = apps.get_model('curriculum', 'Standard')
    try:
        return Standard.objects.first() or Standard.objects.create(name='JSS 1')
    except Exception as exc:  # pragma: no cover
        raise unittest_skip(f'Cannot create a curriculum.Standard automatically: {exc}')


def make_subject(standard, name='Mathematics'):
    """A curriculum.Subject (tied to the class when the project's Subject has a class link)."""
    Subject = apps.get_model('curriculum', 'Subject')
    kwargs = {'name': name}
    class_field = subject_standard_field(Subject)
    if class_field:
        kwargs[class_field] = standard
    try:
        return Subject.objects.get_or_create(**kwargs)[0]
    except Exception as exc:  # pragma: no cover
        raise unittest_skip(f'Cannot create a curriculum.Subject automatically: {exc}')


def unittest_skip(msg):
    import unittest
    return unittest.SkipTest(msg)


class LinkTests(TestCase):
    def test_accepts_google_files(self):
        cases = {
            DOC: 'document',
            'https://docs.google.com/spreadsheets/d/XYZ123/edit#gid=0': 'sheet',
            'https://docs.google.com/presentation/d/XYZ123/edit': 'slides',
            'https://drive.google.com/file/d/XYZ123/view?usp=sharing': 'file',
            'https://drive.google.com/open?id=XYZ123': 'file',
            'https://docs.google.com/document/u/1/d/XYZ123/edit': 'document',
        }
        for url, kind in cases.items():
            self.assertEqual(parse_note_link(url)['kind'], kind, url)
            validate_google_note_link(url)

    def test_rejects_everything_else(self):
        for url in ('https://example.com/a.docx', 'javascript:alert(1)', 'ftp://docs.google.com/document/d/X',
                    'https://docs.google.com/', 'https://evil.com/docs.google.com/document/d/X', ''):
            with self.assertRaises(ValidationError, msg=url):
                validate_google_note_link(url)

    def test_folder_links_get_a_specific_message(self):
        with self.assertRaises(ValidationError) as ctx:
            validate_google_note_link('https://drive.google.com/drive/folders/ABC')
        self.assertIn('folder', ctx.exception.messages[0])


class CsvSafetyTests(TestCase):
    def test_formula_cells_are_neutralised(self):
        for bad in ('=cmd()', '+1', '-1', '@sum'):
            self.assertTrue(services._csv_safe(bad).startswith("'"))
        self.assertEqual(services._csv_safe('Maths'), 'Maths')


class WorkflowTests(TestCase):
    def setUp(self):
        self.std = make_standard()
        self.maths = make_subject(self.std)
        self.teacher = User.objects.create_user('t1', first_name='Ada', last_name='Obi', password='x')
        self.head = User.objects.create_user('head', is_staff=True, password='x')
        self.boss = User.objects.create_superuser('boss', 'b@x.com', 'x')

    def new_note(self, **kw):
        data = dict(standard=self.std, subject=self.maths, academic_session='2026/2027',
                    term='1', week=3, doc_link=DOC)
        data.update(kw)
        return services.create_note(LessonNote(**data), self.teacher)

    def test_submit_creates_audit_event_and_default_title(self):
        n = self.new_note()
        self.assertEqual(n.status, LessonNote.Status.SUBMITTED)
        self.assertTrue(n.title.startswith('Week 3 – Mathematics'))
        self.assertEqual(list(n.events.values_list('action', flat=True)), ['submitted'])

    def test_subject_name_is_a_snapshot_of_the_selected_subject(self):
        n = self.new_note()
        self.assertEqual(n.subject, self.maths)
        self.assertEqual(n.subject_name, 'Mathematics')

    def test_duplicate_slot_at_save_time_becomes_a_validation_error(self):
        self.new_note()
        with self.assertRaises(ValidationError):
            self.new_note()  # same teacher/class/subject/term/week

    def test_request_changes_needs_a_remark(self):
        n = self.new_note()
        with self.assertRaises(ValidationError):
            services.review_note(n, self.head, 'request_changes', '  ')
        services.review_note(n, self.head, 'request_changes', 'Add objectives')
        n.refresh_from_db()
        self.assertEqual(n.status, LessonNote.Status.REVISION)
        self.assertEqual(n.reviewed_by, self.head)

    def test_resubmit_then_approve_then_locked(self):
        n = self.new_note()
        services.review_note(n, self.head, 'request_changes', 'Fix')
        n.refresh_from_db()
        services.update_note(n, self.teacher)
        n.refresh_from_db()
        self.assertEqual(n.status, LessonNote.Status.SUBMITTED)
        services.review_note(n, self.head, 'approve')
        n.refresh_from_db()
        self.assertTrue(n.is_locked)
        with self.assertRaises(PermissionDenied):
            services.update_note(n, self.teacher)
        self.assertEqual(
            list(n.events.values_list('action', flat=True)),
            ['submitted', 'revision_requested', 'resubmitted', 'approved'])

    def test_staff_cannot_approve_own_note_but_superuser_can(self):
        n = services.create_note(LessonNote(
            standard=self.std, subject_name='Art', academic_session='2026/2027', term='1', week=1,
            doc_link=DOC), self.head)
        with self.assertRaises(PermissionDenied):
            services.review_note(n, self.head, 'approve')
        n2 = services.create_note(LessonNote(
            standard=self.std, subject_name='Art', academic_session='2026/2027', term='1', week=1,
            doc_link=DOC), self.boss)
        services.review_note(n2, self.boss, 'approve')

    def test_teacher_summary_counts_and_includes_non_submitters(self):
        self.new_note(week=1)
        n2 = self.new_note(week=2)
        services.review_note(n2, self.head, 'approve')
        # `quiet` is only listed when they are a teacher; here only submitters are in scope
        rows = {u.username: u for u in services.teacher_summary()}
        self.assertEqual(rows['t1'].total, 2)
        self.assertEqual(rows['t1'].awaiting, 1)
        self.assertEqual(rows['t1'].approved, 1)
        scoped = {u.username: u for u in services.teacher_summary(session='2099/2100')}
        self.assertEqual(scoped['t1'].total, 0)

    def test_csv_export_has_bom_and_rows(self):
        self.new_note(subject=make_subject(self.std, '=HYPERLINK("x")'))
        data = services.notes_csv_bytes(LessonNote.objects.all())
        self.assertTrue(data.startswith(b'\xef\xbb\xbf'))
        self.assertIn(b"'=HYPERLINK", data)


class FormTests(TestCase):
    def setUp(self):
        self.std = make_standard()
        self.maths = make_subject(self.std)
        self.teacher = User.objects.create_user('t1', password='x')

    def data(self, **kw):
        d = dict(standard=self.std.pk, subject=self.maths.pk, academic_session='2026/2027',
                 term='1', week=3, doc_link=DOC, title='', teacher_note='')
        d.update(kw)
        return d

    def test_valid_and_normalised(self):
        form = NoteForm(self.data(), user=self.teacher)
        self.assertTrue(form.is_valid(), form.errors)

    def test_subject_is_required_and_comes_from_the_curriculum(self):
        form = NoteForm(self.data(subject=''), user=self.teacher)
        self.assertFalse(form.is_valid())
        self.assertIn('subject', form.errors)
        self.assertNotIn('subject_name', form.fields)   # no more free typing

    def test_bad_link_and_session_rejected(self):
        form = NoteForm(self.data(doc_link='https://example.com/x', academic_session='2026'), user=self.teacher)
        self.assertFalse(form.is_valid())
        self.assertIn('doc_link', form.errors)
        self.assertIn('academic_session', form.errors)

    def test_same_slot_twice_is_blocked(self):
        services.create_note(LessonNote(standard=self.std, subject=self.maths,
                                        academic_session='2026/2027', term='1', week=3, doc_link=DOC), self.teacher)
        form = NoteForm(self.data(), user=self.teacher)
        self.assertFalse(form.is_valid())
        self.assertIn('already submitted', str(form.errors))

    def test_older_text_only_note_still_counts_as_a_duplicate(self):
        services.create_note(LessonNote(standard=self.std, subject_name='mathematics',   # written before subjects
                                        academic_session='2026/2027', term='1', week=3, doc_link=DOC), self.teacher)
        form = NoteForm(self.data(), user=self.teacher)
        self.assertFalse(form.is_valid())
        self.assertIn('already submitted', str(form.errors))

    def test_subject_must_belong_to_the_selected_class(self):
        if not subject_standard_field():
            self.skipTest('This project\'s Subject is not tied to a class.')
        other_class = apps.get_model('curriculum', 'Standard').objects.create(name='JSS 2')
        form = NoteForm(self.data(standard=other_class.pk), user=self.teacher)
        self.assertFalse(form.is_valid())
        self.assertIn('not taught in the selected class', str(form.errors['subject']))


class ViewAccessTests(TestCase):
    def setUp(self):
        self.std = make_standard()
        self.english = make_subject(self.std, 'English')
        self.teacher = User.objects.create_user('t1', password='x')
        self.other = User.objects.create_user('t2', password='x')
        self.head = User.objects.create_user('head', is_staff=True, password='x')
        self.nobody = User.objects.create_user('pupil', password='x')
        self.note = services.create_note(LessonNote(
            standard=self.std, subject_name='Maths', academic_session='2026/2027', term='1',
            week=1, doc_link=DOC), self.teacher)

    def test_anonymous_goes_to_login(self):
        for name in ('mine', 'all', 'teachers', 'submit', 'export'):
            self.assertEqual(self.client.get(reverse(f'lessonnotes:{name}')).status_code, 302, name)

    def test_non_staff_non_teacher_is_forbidden_everywhere(self):
        self.client.force_login(self.nobody)
        for name in ('mine', 'all', 'teachers', 'submit', 'export'):
            self.assertEqual(self.client.get(reverse(f'lessonnotes:{name}')).status_code, 403, name)
        self.assertEqual(self.client.get(self.note.get_absolute_url()).status_code, 403)

    def test_teacher_cannot_open_reviewer_pages_or_other_peoples_notes(self):
        self.client.force_login(self.teacher)
        with mock.patch(TEACHER_PATCH, return_value=True):
            self.assertEqual(self.client.get(reverse('lessonnotes:mine')).status_code, 200)
            self.assertEqual(self.client.get(reverse('lessonnotes:all')).status_code, 403)
            self.assertEqual(self.client.get(reverse('lessonnotes:export')).status_code, 403)
            self.assertEqual(self.client.post(reverse('lessonnotes:review', args=[self.note.pk]),
                                              {'decision': 'approve'}).status_code, 403)
        self.client.force_login(self.other)
        with mock.patch(TEACHER_PATCH, return_value=True):
            self.assertEqual(self.client.get(self.note.get_absolute_url()).status_code, 403)
            self.assertEqual(self.client.get(reverse('lessonnotes:edit', args=[self.note.pk])).status_code, 404)

    def test_reviewer_pages_render(self):
        self.client.force_login(self.head)
        for name in ('all', 'teachers'):
            r = self.client.get(reverse(f'lessonnotes:{name}'))
            self.assertEqual(r.status_code, 200, name)
        self.assertContains(self.client.get(reverse('lessonnotes:all')), 'Maths')
        self.assertContains(self.client.get(reverse('lessonnotes:teachers')), 't1')
        self.assertContains(self.client.get(reverse('lessonnotes:teacher_notes', args=[self.teacher.pk])), 'Maths')
        detail = self.client.get(self.note.get_absolute_url())
        self.assertContains(detail, 'Open in Google Drive')
        self.assertContains(detail, 'School review')
        csv_resp = self.client.get(reverse('lessonnotes:export') + '?status=submitted')
        self.assertEqual(csv_resp['Content-Type'], 'text/csv; charset=utf-8')

    def test_reviewer_review_flow_over_http(self):
        self.client.force_login(self.head)
        url = reverse('lessonnotes:review', args=[self.note.pk])
        self.client.post(url, {'decision': 'request_changes', 'remark': ''})
        self.note.refresh_from_db()
        self.assertEqual(self.note.status, 'submitted')  # no remark -> refused
        self.client.post(url, {'decision': 'request_changes', 'remark': 'Add aims'})
        self.note.refresh_from_db()
        self.assertEqual(self.note.status, 'revision')
        self.assertEqual(self.client.get(url).status_code, 405)

    def test_teacher_submit_edit_delete_over_http(self):
        self.client.force_login(self.teacher)
        with mock.patch(TEACHER_PATCH, return_value=True):
            r = self.client.post(reverse('lessonnotes:submit'), dict(
                standard=self.std.pk, subject=self.english.pk, academic_session='2026/2027', term='2',
                week=4, title='', doc_link='https://docs.google.com/spreadsheets/d/AAA/edit', teacher_note=''))
            self.assertEqual(r.status_code, 302, getattr(r, 'context', None) and r.context['form'].errors)
            note = LessonNote.objects.get(subject_name='English')
            self.assertEqual(self.client.get(reverse('lessonnotes:edit', args=[note.pk])).status_code, 200)
            self.client.post(reverse('lessonnotes:delete', args=[note.pk]))
            self.assertFalse(LessonNote.objects.filter(pk=note.pk).exists())

    def test_approved_note_is_locked_for_teacher(self):
        services.review_note(self.note, self.head, 'approve')
        self.client.force_login(self.teacher)
        with mock.patch(TEACHER_PATCH, return_value=True):
            for name in ('edit', 'delete'):
                r = self.client.get(reverse(f'lessonnotes:{name}', args=[self.note.pk]))
                self.assertEqual(r.status_code, 302, name)
            self.client.post(reverse('lessonnotes:delete', args=[self.note.pk]))
        self.assertTrue(LessonNote.objects.filter(pk=self.note.pk).exists())


class NotificationTests(TestCase):
    def setUp(self):
        self.std = make_standard()
        self.maths = make_subject(self.std)
        self.teacher = User.objects.create_user('t1', password='x')
        self.head = User.objects.create_user('head', is_staff=True, password='x')
        self.boss = User.objects.create_superuser('boss', 'b@x.com', 'x')
        self.pupil = User.objects.create_user('pupil', password='x')

    def submit(self):
        with self.captureOnCommitCallbacks(execute=True):
            return services.create_note(LessonNote(
                standard=self.std, subject=self.maths, academic_session='2026/2027',
                term='1', week=1, doc_link=DOC), self.teacher)

    def test_submitting_notifies_every_reviewer_but_not_the_teacher_or_others(self):
        note = self.submit()
        got = set(Notification.objects.values_list('recipient__username', flat=True))
        self.assertEqual(got, {'head', 'boss'})
        n = Notification.objects.get(recipient=self.head)
        self.assertEqual(n.category, 'lesson_note')
        self.assertEqual(n.url, note.get_absolute_url())

    def test_a_reviewer_who_submits_does_not_notify_themselves(self):
        with self.captureOnCommitCallbacks(execute=True):
            services.create_note(LessonNote(standard=self.std, subject=self.maths, academic_session='2026/2027',
                                            term='1', week=2, doc_link=DOC), self.head)
        self.assertEqual(set(Notification.objects.values_list('recipient__username', flat=True)), {'boss'})

    def test_review_decisions_notify_the_teacher_and_resubmitting_notifies_reviewers(self):
        note = self.submit()
        Notification.objects.all().delete()
        with self.captureOnCommitCallbacks(execute=True):
            services.review_note(note, self.head, 'request_changes', 'Add the aims')
        n = Notification.objects.get()
        self.assertEqual(n.recipient, self.teacher)
        self.assertIn('Changes requested', n.title)
        self.assertIn('Add the aims', n.message)

        note.refresh_from_db()
        Notification.objects.all().delete()
        with self.captureOnCommitCallbacks(execute=True):
            services.update_note(note, self.teacher)
        self.assertEqual(set(Notification.objects.values_list('recipient__username', flat=True)), {'head', 'boss'})

        note.refresh_from_db()
        Notification.objects.all().delete()
        with self.captureOnCommitCallbacks(execute=True):
            services.review_note(note, self.head, 'approve')
        n = Notification.objects.get()
        self.assertEqual((n.recipient, n.title), (self.teacher, 'Your lesson note was approved'))

    def test_a_rolled_back_submission_notifies_nobody(self):
        self.submit()
        Notification.objects.all().delete()
        with self.captureOnCommitCallbacks(execute=True):
            with self.assertRaises(ValidationError):
                services.create_note(LessonNote(standard=self.std, subject=self.maths,
                                                academic_session='2026/2027', term='1', week=1, doc_link=DOC), self.teacher)
        self.assertEqual(Notification.objects.count(), 0)


class LinkSubjectsCommandTests(TestCase):
    def test_links_by_name_and_leaves_unmatched_as_text(self):
        std = make_standard()
        maths = make_subject(std)
        teacher = User.objects.create_user('t1', password='x')
        old = services.create_note(LessonNote(standard=std, subject_name='  mathematics ', academic_session='2026/2027',
                                              term='1', week=1, doc_link=DOC), teacher)
        odd = services.create_note(LessonNote(standard=std, subject_name='Basket weaving', academic_session='2026/2027',
                                              term='1', week=2, doc_link=DOC), teacher)
        out = StringIO()
        call_command('link_lessonnote_subjects', '--dry-run', stdout=out)
        old.refresh_from_db()
        self.assertIsNone(old.subject)                       # dry run changes nothing
        call_command('link_lessonnote_subjects', stdout=out)
        old.refresh_from_db(); odd.refresh_from_db()
        self.assertEqual(old.subject, maths)
        self.assertEqual(old.subject_name, 'mathematics')    # snapshot left untouched by the command
        self.assertIsNone(odd.subject)
        self.assertIn('Linked 1', out.getvalue())