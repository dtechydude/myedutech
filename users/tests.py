import unittest
from types import SimpleNamespace as NS

from django.contrib.auth import get_user_model
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from .portal_access import portal_access

User = get_user_model()


def model_for(relation):
    """The model behind user.<relation> (profile, student, parent, teacher), wherever it lives."""
    return User._meta.get_field(relation).related_model


def make(relation, user=None, **fields):
    """Create one of those records, or skip the test if this project's model needs more required fields."""
    model = model_for(relation)
    if user is not None:
        fields['user'] = user
    try:
        return model.objects.create(**fields)
    except Exception as exc:  # pragma: no cover
        raise unittest.SkipTest(f'Cannot create a {model.__name__} automatically: {exc}')


def fake(**kw):
    base = dict(is_active=True, is_superuser=False, is_staff=False, teacher=None, student=None, parent=None, staff=None)
    base.update(kw)
    return NS(**base)


def student(status):
    return NS(student_status=status, get_student_status_display=lambda: status.title())


class PortalAccessRuleTests(TestCase):
    def test_disabled_account_wins_over_everything(self):
        s = portal_access(fake(is_active=False, is_superuser=True))
        self.assertEqual((s['code'], s['can_login']), ('disabled', False))

    def test_admins_and_teachers_can_log_in(self):
        self.assertEqual(portal_access(fake(is_superuser=True))['label'], 'Superuser')
        self.assertEqual(portal_access(fake(is_staff=True))['label'], 'Admin (Staff)')
        self.assertEqual(portal_access(fake(teacher=object()))['label'], 'Teacher')
        self.assertEqual(portal_access(fake(staff=object()))['label'], 'Staff')
        self.assertEqual(portal_access(fake())['label'], 'Active')

    def test_active_student_ok_every_other_status_is_blocked_even_though_is_active_is_true(self):
        self.assertTrue(portal_access(fake(student=student('active')))['can_login'])
        expected_tone = {'inactive': 'text-warning', 'graduated': 'text-muted',
                         'suspended': 'text-danger', 'dropped': 'text-danger', 'expelled': 'text-danger'}
        for status, tone in expected_tone.items():
            s = portal_access(fake(student=student(status), is_active=True))
            self.assertFalse(s['can_login'], status)
            self.assertEqual(s['text_class'], tone, status)
            self.assertTrue(s['label'].startswith('Blocked'), status)
        self.assertIn('Suspended', portal_access(fake(student=student('suspended')))['label'])
        self.assertIn('no longer', portal_access(fake(student=student('graduated')))['reason'])

    def test_parent_needs_at_least_one_active_child(self):
        parent = NS(pk=7)
        self.assertEqual(portal_access(fake(parent=parent), {7: 2})['label'], 'Active (Parent)')
        self.assertIn('2 active children', portal_access(fake(parent=parent), {7: 2})['reason'])
        self.assertIn('1 active child.', portal_access(fake(parent=parent), {7: 1})['reason'])
        blocked = portal_access(fake(parent=parent), {})
        self.assertEqual((blocked['code'], blocked['can_login']), ('parent_blocked', False))

    def test_a_teacher_who_is_also_a_parent_is_a_teacher(self):
        self.assertEqual(portal_access(fake(teacher=object(), parent=NS(pk=1)), {})['code'], 'teacher')


class AllUsersViewTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user('admin', is_staff=True, password='x')
        self.boss = User.objects.create_superuser('boss', 'b@x.com', 'x')   # superuser; is_staff is also True
        self.plain = User.objects.create_user('plain', password='x')

    def make_people(self):
        susp = User.objects.create_user('susp', first_name='Sam', last_name='Suspended', password='x')
        make('student', susp, student_status='suspended')
        ok = User.objects.create_user('okstudent', password='x')
        child = make('student', ok, student_status='active')
        happy = User.objects.create_user('happyparent', password='x'); p1 = make('parent', happy)
        sad = User.objects.create_user('sadparent', password='x'); p2 = make('parent', sad)
        child.parent = p1; child.save()
        make('student', None, student_status='dropped', parent=p2)          # sad parent's only child is dropped
        teacher = User.objects.create_user('teach', password='x'); make('teacher', teacher)
        profile = getattr(teacher, 'profile', None) or make('profile', teacher)
        profile.phone, profile.state_of_origin, profile.user_type = '0803', 'Lagos', 'teacher'
        profile.save()

    def test_non_admins_are_sent_to_the_portal_home(self):
        self.client.force_login(self.plain)
        self.assertRedirects(self.client.get(reverse('all_users')), reverse('pages:portal-home'),
                             fetch_redirect_response=False)
        self.assertRedirects(self.client.get(reverse('all_users') + '?export=csv'), reverse('pages:portal-home'),
                             fetch_redirect_response=False)

    def test_staff_and_superusers_can_open_it_and_see_the_real_status(self):
        self.make_people()
        for who in (self.admin, self.boss):
            self.client.force_login(who)
            page = self.client.get(reverse('all_users'))
            self.assertEqual(page.status_code, 200)
        html = page.content.decode()
        def cell(username):
            row = html.split(f'data-user="{username}"')[1].split('</tr>')[0]
            return ' '.join(row.split())
        self.assertIn('Blocked \u2014 Suspended', cell('susp'))
        self.assertIn('text-danger', cell('susp'))
        self.assertIn('Active (Student)', cell('okstudent'))
        self.assertIn('Active (Parent)', cell('happyparent'))
        self.assertIn('Blocked \u2014 no active children', cell('sadparent'))
        self.assertIn('Teacher', cell('teach'))
        self.assertIn('Admin (Staff)', cell('admin'))
        self.assertEqual(page.context['total_count'], User.objects.count())

    def test_account_switched_off_in_admin_shows_disabled(self):
        User.objects.create_user('gone', is_active=False, password='x')
        self.client.force_login(self.admin)
        self.assertIn('Account disabled', self.client.get(reverse('all_users')).content.decode())

    def test_csv_export_has_bom_new_columns_and_survives_missing_profiles(self):
        self.make_people()
        User.objects.create_user('=cmd', first_name='=HYPERLINK("x")', password='x')
        self.client.force_login(self.admin)
        r = self.client.get(reverse('all_users') + '?export=csv')
        self.assertEqual(r['Content-Type'], 'text/csv; charset=utf-8')
        self.assertTrue(r.content.startswith(b'\xef\xbb\xbf'))
        text = r.content.decode('utf-8-sig')
        self.assertTrue(text.splitlines()[0].endswith('Portal Access,Can Log In'))
        self.assertIn('susp,Sam,Suspended', text)
        self.assertIn('Blocked \u2014 Suspended,No', text)
        self.assertIn('Teacher,Yes', text)
        self.assertIn("'=cmd", text)             # formula injection neutralised
        self.assertIn('0803,Lagos,teacher', text)  # existing columns unchanged

    def test_number_of_queries_does_not_grow_with_the_number_of_users(self):
        self.client.force_login(self.admin)
        def queries():
            with CaptureQueriesContext(connection) as ctx:
                self.client.get(reverse('all_users'))
            return len(ctx)
        base = queries()
        for i in range(25):
            u = User.objects.create_user(f'bulk{i}', password='x')
            if getattr(u, 'profile', None) is None:
                make('profile', u)
            make('student', u, student_status='suspended' if i % 2 else 'active')
        self.assertEqual(queries(), base)