from django.test import TestCase

# Create your tests here.
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.messages import get_messages
from django.core.exceptions import PermissionDenied
from django.shortcuts import resolve_url
from django.test import TestCase, override_settings
from django.urls import reverse

from students.models import Student

from . import services
from .constants import (
    ACTIVE, DROPPED, EXPELLED, GRADUATED, INACTIVE, LOGIN_BLOCKED_STATUSES, SUSPENDED,
)
from .forms import StatusChangeForm
from .models import StudentStatusLog

User = get_user_model()
PASSWORD = 'S3cure-pass!'

# Explicit so these tests pass whatever the project's own settings say.
TEST_MIDDLEWARE = [
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'studentstatus.middleware.StudentStatusAccessMiddleware',
]
TEST_BACKENDS = [
    'studentstatus.backends.StudentStatusGuardBackend',
    'django.contrib.auth.backends.ModelBackend',
]
# Fast hasher for tests only — keeps the suite quick.
FAST_HASHER = override_settings(PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])


def make_student(username, status=ACTIVE, **user_kwargs):
    user = User.objects.create_user(username=username, password=PASSWORD, **user_kwargs)
    student = Student.objects.create(
        user=user, USN=username, first_name='Ada', last_name=username.title(),
        student_status=status,
    )
    return student


def make_admin(username='admin1', superuser=False):
    if superuser:
        return User.objects.create_superuser(username, f'{username}@x.com', PASSWORD)
    return User.objects.create_user(username, password=PASSWORD, is_staff=True)


@FAST_HASHER
class ServiceTests(TestCase):
    def setUp(self):
        self.admin = make_admin()
        self.student = make_student('stu1')

    def change(self, status, reason='Because', student=None, by=None):
        return services.change_student_status(
            student_id=(student or self.student).pk, new_status=status,
            changed_by=by or self.admin, reason=reason, ip_address='10.0.0.5',
        )

    def test_change_updates_student_and_writes_log(self):
        log = self.change(SUSPENDED, reason='  Fighting  ')
        self.student.refresh_from_db()
        self.assertEqual(self.student.student_status, SUSPENDED)
        self.assertEqual(log.old_status, ACTIVE)
        self.assertEqual(log.new_status, SUSPENDED)
        self.assertEqual(log.reason, 'Fighting')
        self.assertEqual(log.changed_by, self.admin)
        self.assertEqual(log.changed_by_name, 'admin1')
        self.assertEqual(log.student_usn, 'stu1')
        self.assertEqual(log.ip_address, '10.0.0.5')

    def test_all_assignable_statuses_work_and_can_return_to_active(self):
        for status in (INACTIVE, SUSPENDED, DROPPED, EXPELLED):
            with self.subTest(status=status):
                self.change(status)
                self.student.refresh_from_db()
                self.assertEqual(self.student.student_status, status)
                self.change(ACTIVE, reason='')  # reason optional when restoring
                self.student.refresh_from_db()
                self.assertEqual(self.student.student_status, ACTIVE)

    def test_reason_required_for_restrictions(self):
        with self.assertRaises(services.StatusChangeError):
            self.change(SUSPENDED, reason='   ')
        self.student.refresh_from_db()
        self.assertEqual(self.student.student_status, ACTIVE)
        self.assertEqual(StudentStatusLog.objects.count(), 0)

    def test_same_status_refused(self):
        with self.assertRaises(services.StatusChangeError):
            self.change(ACTIVE, reason='x')

    def test_graduated_cannot_be_assigned(self):
        with self.assertRaises(services.StatusChangeError):
            self.change(GRADUATED)

    def test_graduated_student_is_protected(self):
        grad = make_student('grad1', status=GRADUATED)
        for target in (ACTIVE, SUSPENDED):
            with self.assertRaises(services.StatusChangeError):
                self.change(target, student=grad)
        grad.refresh_from_db()
        self.assertEqual(grad.student_status, GRADUATED)

    def test_non_admin_is_refused(self):
        teacher = User.objects.create_user('teach', password=PASSWORD)
        with self.assertRaises(PermissionDenied):
            self.change(SUSPENDED, by=teacher)
        self.student.refresh_from_db()
        self.assertEqual(self.student.student_status, ACTIVE)

    def test_log_survives_student_deletion(self):
        self.change(SUSPENDED)
        self.student.delete()
        log = StudentStatusLog.objects.get()
        self.assertIsNone(log.student)
        self.assertEqual(log.student_usn, 'stu1')


@FAST_HASHER
class FormTests(TestCase):
    def test_current_status_not_offered(self):
        student = make_student('stu2', status=SUSPENDED)
        form = StatusChangeForm(student=student)
        values = [v for v, _ in form.fields['new_status'].choices]
        self.assertNotIn(SUSPENDED, values)
        self.assertNotIn(GRADUATED, values)
        self.assertIn(ACTIVE, values)

    def test_reason_required_unless_active(self):
        student = make_student('stu3')
        self.assertFalse(StatusChangeForm({'new_status': EXPELLED, 'reason': ' '}, student=student).is_valid())
        self.assertTrue(StatusChangeForm({'new_status': EXPELLED, 'reason': 'Serious offence'}, student=student).is_valid())
        suspended = make_student('stu4', status=SUSPENDED)
        self.assertTrue(StatusChangeForm({'new_status': ACTIVE, 'reason': ''}, student=suspended).is_valid())


@FAST_HASHER
class ViewTests(TestCase):
    def setUp(self):
        self.admin = make_admin()
        self.student = make_student('stu5')
        self.url = reverse('studentstatus:change', kwargs={'pk': self.student.pk})

    def test_anonymous_redirected_to_login(self):
        for name in ('studentstatus:list', 'studentstatus:log'):
            r = self.client.get(reverse(name))
            self.assertEqual(r.status_code, 302)
            self.assertIn(settings.LOGIN_URL, r.url)

    def test_non_admin_gets_403(self):
        teacher = User.objects.create_user('teach2', password=PASSWORD)
        self.client.force_login(teacher)
        self.assertEqual(self.client.get(reverse('studentstatus:list')).status_code, 403)
        self.assertEqual(self.client.get(self.url).status_code, 403)
        r = self.client.post(self.url, {'new_status': SUSPENDED, 'reason': 'x'})
        self.assertEqual(r.status_code, 403)
        self.student.refresh_from_db()
        self.assertEqual(self.student.student_status, ACTIVE)

    def test_student_cannot_change_own_status(self):
        self.client.force_login(self.student.user)
        r = self.client.post(self.url, {'new_status': SUSPENDED, 'reason': 'x'})
        self.assertEqual(r.status_code, 403)

    def test_superuser_and_staff_can_open_pages(self):
        for admin in (self.admin, make_admin('root1', superuser=True)):
            self.client.force_login(admin)
            for name in ('studentstatus:list', 'studentstatus:log'):
                self.assertEqual(self.client.get(reverse(name)).status_code, 200)
            self.assertEqual(self.client.get(self.url).status_code, 200)

    def test_list_search_and_status_filter(self):
        make_student('other1', status=SUSPENDED)
        self.client.force_login(self.admin)
        r = self.client.get(reverse('studentstatus:list'), {'status': SUSPENDED})
        self.assertEqual([s.USN for s in r.context['students']], ['other1'])
        r = self.client.get(reverse('studentstatus:list'), {'q': 'stu5'})
        self.assertEqual([s.USN for s in r.context['students']], ['stu5'])
        counts = {c['status']: c['count'] for c in r.context['status_counts']}
        self.assertEqual(counts[ACTIVE], 1)
        self.assertEqual(counts[SUSPENDED], 1)
        self.assertEqual(counts[EXPELLED], 0)

    def test_pagination_keeps_filters(self):
        for i in range(30):
            make_student(f'bulk{i}')
        self.client.force_login(self.admin)
        r = self.client.get(reverse('studentstatus:list'), {'status': ACTIVE, 'page': 1})
        self.assertEqual(r.context['filter_qs'], 'status=active')
        self.assertContains(r, 'status=active&amp;page=2')


        def test_page_numbers_summary_and_footer(self):
        for i in range(30):
            make_student(f'pg{i}')
        self.client.force_login(self.admin)
        r = self.client.get(reverse('studentstatus:list'), {'status': ACTIVE})
        self.assertContains(r, 'Showing 1–25 of 31 students')
        self.assertContains(r, 'status=active&amp;page=2')
        self.assertContains(r, 'Powered by <strong>KwikSchools</strong>')
        self.assertEqual([i['number'] for i in r.context['page_items']], [1, 2])

    def test_summary_shown_even_with_a_single_page(self):
        self.client.force_login(self.admin)
        r = self.client.get(reverse('studentstatus:list'))
        self.assertContains(r, 'Showing 1–1 of 1 students')
        self.assertNotIn('page_items', r.context)

    def test_per_page_option_and_invalid_value(self):
        for i in range(14):
            make_student(f'pp{i}')
        self.client.force_login(self.admin)
        r = self.client.get(reverse('studentstatus:list'), {'per_page': 10})
        self.assertEqual(len(r.context['students']), 10)
        self.assertEqual(r.context['per_page'], 10)
        for bad in ('7', 'abc', '100000', '-5'):
            r = self.client.get(reverse('studentstatus:list'), {'per_page': bad})
            self.assertEqual(r.context['per_page'], 25, bad)

    def test_per_page_survives_paging(self):
        for i in range(14):
            make_student(f'pk{i}')
        self.client.force_login(self.admin)
        r = self.client.get(reverse('studentstatus:list'), {'per_page': 10})
        self.assertContains(r, 'per_page=10&amp;page=2')

    def test_long_page_range_is_elided(self):
        for i in range(300):
            make_student(f'many{i}')
        self.client.force_login(self.admin)
        r = self.client.get(reverse('studentstatus:list'), {'per_page': 10, 'page': 15})
        items = r.context['page_items']
        self.assertTrue(any(i['gap'] for i in items))
        self.assertEqual([i['number'] for i in items if i['current']], [15])

    def test_post_changes_status_and_logs(self):
        self.client.force_login(self.admin)
        r = self.client.post(self.url, {'new_status': SUSPENDED, 'reason': 'Two-week suspension'})
        self.assertRedirects(r, self.url)
        self.student.refresh_from_db()
        self.assertEqual(self.student.student_status, SUSPENDED)
        log = StudentStatusLog.objects.get()
        self.assertEqual((log.old_status, log.new_status, log.changed_by), (ACTIVE, SUSPENDED, self.admin))
        r = self.client.get(self.url)
        self.assertContains(r, 'Two-week suspension')
        self.assertContains(r, 'Blocked')

    def test_success_message_and_layout_render(self):
        self.client.force_login(self.admin)
        r = self.client.post(self.url, {'new_status': DROPPED, 'reason': 'Left the school'}, follow=True)
        self.assertContains(r, 'alert-success')
        self.assertContains(r, 'can no longer log in')
        self.assertContains(r, 'Change log')  # navbar from studentstatus/base.html

    def test_post_without_reason_is_rejected(self):
        self.client.force_login(self.admin)
        r = self.client.post(self.url, {'new_status': EXPELLED, 'reason': ''})
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.context['form'].errors['reason'])
        self.student.refresh_from_db()
        self.assertEqual(self.student.student_status, ACTIVE)

    def test_graduated_student_cannot_be_changed(self):
        grad = make_student('grad2', status=GRADUATED)
        url = reverse('studentstatus:change', kwargs={'pk': grad.pk})
        self.client.force_login(self.admin)
        page = self.client.get(url)
        self.assertEqual(page.status_code, 200)
        self.assertTrue(page.context['is_protected'])
        self.assertNotContains(page, 'Save status')
        r = self.client.post(url, {'new_status': ACTIVE, 'reason': 'x'})
        self.assertEqual(r.status_code, 200)  # form re-rendered with error
        grad.refresh_from_db()
        self.assertEqual(grad.student_status, GRADUATED)
        self.assertEqual(StudentStatusLog.objects.count(), 0)

    def test_unknown_student_404(self):
        self.client.force_login(self.admin)
        self.assertEqual(self.client.get(reverse('studentstatus:change', kwargs={'pk': 99999})).status_code, 404)


@FAST_HASHER
@override_settings(MIDDLEWARE=TEST_MIDDLEWARE, AUTHENTICATION_BACKENDS=TEST_BACKENDS)
class AccessBlockingTests(TestCase):
    def setUp(self):
        self.admin = make_admin()

    def set_status(self, student, status):
        services.change_student_status(
            student_id=student.pk, new_status=status, changed_by=self.admin, reason='test')

    def test_active_student_can_log_in(self):
        make_student('okstu')
        self.assertTrue(self.client.login(username='okstu', password=PASSWORD))

    def test_every_blocked_status_prevents_login(self):
        for status in LOGIN_BLOCKED_STATUSES:
            with self.subTest(status=status):
                make_student(f'blk_{status}', status=status)
                self.assertFalse(self.client.login(username=f'blk_{status}', password=PASSWORD))

    def test_login_works_again_after_status_restored(self):
        student = make_student('back1')
        self.set_status(student, SUSPENDED)
        self.assertFalse(self.client.login(username='back1', password=PASSWORD))
        self.set_status(student, ACTIVE)
        self.assertTrue(self.client.login(username='back1', password=PASSWORD))

    def test_username_match_is_case_insensitive(self):
        make_student('CaseStu', status=SUSPENDED)
        self.assertFalse(self.client.login(username='casestu', password=PASSWORD))

    def test_staff_with_student_record_is_never_blocked(self):
        make_student('adm_stu', status=SUSPENDED, is_staff=True)
        self.assertTrue(self.client.login(username='adm_stu', password=PASSWORD))

    def test_non_student_users_unaffected(self):
        User.objects.create_user('parent1', password=PASSWORD)
        self.assertTrue(self.client.login(username='parent1', password=PASSWORD))

    def test_open_session_is_ended_when_student_is_suspended(self):
        student = make_student('live1')
        self.client.force_login(student.user)
        url = reverse('studentstatus:list')
        self.assertEqual(self.client.get(url).status_code, 403)   # logged in, just not an admin

        self.set_status(student, SUSPENDED)
        r = self.client.get(url)
        self.assertRedirects(r, resolve_url(settings.LOGIN_URL), fetch_redirect_response=False)
        self.assertNotIn('_auth_user_id', self.client.session)

    def test_blocked_student_is_told_why(self):
        student = make_student('msg1')
        self.client.force_login(student.user)
        self.set_status(student, EXPELLED)
        r = self.client.get(reverse('studentstatus:list'))
        texts = [str(m) for m in get_messages(r.wsgi_request)]
        self.assertTrue(any('access to this portal has been withdrawn' in t for t in texts), texts)

    def test_blocked_login_attempt_is_told_why(self):
        make_student('msg2', status=SUSPENDED)
        from django.contrib.auth import authenticate
        from django.test import RequestFactory
        from django.contrib.messages.storage.fallback import FallbackStorage
        request = RequestFactory().post('/login/')
        request.session = self.client.session
        request._messages = FallbackStorage(request)
        self.assertIsNone(authenticate(request, username='msg2', password=PASSWORD))
        self.assertTrue(any('suspended' in str(m) for m in request._messages))

    def test_ajax_request_gets_json_403(self):
        student = make_student('ajax1')
        self.client.force_login(student.user)
        self.set_status(student, DROPPED)
        r = self.client.get(reverse('studentstatus:list'), headers={'x-requested-with': 'XMLHttpRequest'})
        self.assertEqual(r.status_code, 403)
        self.assertEqual(r.json()['status'], 'error')

    def test_staff_session_unaffected(self):
        self.client.force_login(self.admin)
        self.assertEqual(self.client.get(reverse('studentstatus:list')).status_code, 200)

    def test_status_changed_outside_the_front_end_is_still_enforced(self):
        student = make_student('raw1')
        self.client.force_login(student.user)
        Student.objects.filter(pk=student.pk).update(student_status=GRADUATED)  # bulk update, no signals
        r = self.client.get(reverse('studentstatus:list'))
        self.assertEqual(r.status_code, 302)