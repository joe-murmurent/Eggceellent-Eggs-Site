import tempfile
from datetime import date

from django.contrib.auth.models import Group, User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse

from config.hashers import LegacySHA256PasswordHasher
from .models import Organization, TripEntry, TripEntryFile


class TripSiteTests(TestCase):
    def setUp(self):
        temporary_media = tempfile.TemporaryDirectory()
        self.addCleanup(temporary_media.cleanup)
        media_settings = override_settings(MEDIA_ROOT=temporary_media.name)
        media_settings.enable()
        self.addCleanup(media_settings.disable)

        self.admin = User.objects.create_user("admin", password="FarmRoad!2026")
        self.admin.groups.add(Group.objects.get(name="ADMIN"))
        self.viewer = User.objects.create_user("viewer", password="FarmRoad!2026")
        self.viewer.groups.add(Group.objects.get(name="USER"))

    def test_home_page_shows_trip_sign_in_not_egg_placeholder(self):
        response = self.client.get(reverse("home"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Make room for")
        self.assertContains(response, "MEMBER SIGN IN")
        self.assertNotContains(response, "Fresh from our little corner")

    def test_legacy_sha256_login_upgrades_password_hash(self):
        user = User.objects.create(username="legacy-user")
        user.password = LegacySHA256PasswordHasher().encode("old-trip-password", "")
        user.save(update_fields=["password"])

        response = self.client.post(
            reverse("home"),
            {"username": "legacy-user", "password": "old-trip-password"},
        )

        self.assertRedirects(response, reverse("home"))
        user.refresh_from_db()
        self.assertTrue(user.password.startswith("pbkdf2_sha256$"))
        self.assertContains(self.client.get(reverse("home")), "Hello,")

    def test_trip_journal_requires_sign_in(self):
        response = self.client.get(reverse("trip_index"))

        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.url.startswith("/?next="))

    def test_user_can_create_and_download_private_trip_file(self):
        self.client.force_login(self.viewer)
        response = self.client.post(
            reverse("create_trip_entry"),
            {
                "event_title": "Arrive in London",
                "event_date": "2027-06-10",
                "event_description": "First day of the trip.",
                "file_descriptions": ["Train ticket"],
                "files": [SimpleUploadedFile("ticket.txt", b"ticket contents", "text/plain")],
            },
        )

        entry = TripEntry.objects.get(event_title="Arrive in London")
        trip_file = TripEntryFile.objects.get(trip_entry=entry)
        self.assertRedirects(response, reverse("trip_entry", args=[entry.pk]))
        self.assertEqual(trip_file.description, "Train ticket")

        self.client.logout()
        denied = self.client.get(reverse("download_trip_file", args=[trip_file.pk]))
        self.assertEqual(denied.status_code, 302)

        self.client.force_login(self.viewer)
        download = self.client.get(reverse("download_trip_file", args=[trip_file.pk]))
        self.assertEqual(download.status_code, 200)
        self.assertEqual(b"".join(download.streaming_content), b"ticket contents")
        self.assertEqual(download["X-Content-Type-Options"], "nosniff")

    def test_admin_can_manage_organizations_and_users_cannot(self):
        self.client.force_login(self.viewer)
        denied = self.client.get(reverse("admin_users"))
        self.assertEqual(denied.status_code, 302)

        self.client.force_login(self.admin)
        response = self.client.post(
            reverse("admin_organizations"),
            {"action": "create", "business_name": "Joe's Trip", "city": "London"},
        )
        self.assertRedirects(response, reverse("admin_organizations"))
        self.assertTrue(Organization.objects.filter(business_name="Joe's Trip", city="London").exists())
        self.assertEqual(self.client.get(reverse("admin_roles")).status_code, 200)

    def test_eggs_route_is_role_restricted(self):
        self.client.force_login(self.viewer)
        self.assertEqual(self.client.get(reverse("eggs")).status_code, 302)

        eggs_user = User.objects.create_user("eggs", password="FarmRoad!2026")
        eggs_user.groups.add(Group.objects.get(name="EGGS"))
        self.client.force_login(eggs_user)
        self.assertContains(self.client.get(reverse("eggs")), "EGGS area")

    def test_authenticated_journal_and_admin_pages_render(self):
        entry = TripEntry.objects.create(
            event_date=date(2027, 6, 10),
            event_title="First day",
            event_description="A new city.",
        )
        TripEntryFile.objects.create(
            trip_entry=entry,
            file=SimpleUploadedFile("arrival.jpg", b"image-bytes", "image/jpeg"),
            file_name="arrival.jpg",
            file_type="image/jpeg",
            description="First morning",
        )
        Organization.objects.create(business_name="Trip office", city="London")
        self.client.force_login(self.admin)

        for route in [
            "trip_index",
            "admin_users",
            "admin_roles",
            "admin_organizations",
        ]:
            with self.subTest(route=route):
                self.assertEqual(self.client.get(reverse(route)).status_code, 200)
        detail = self.client.get(reverse("trip_entry", args=[entry.pk]))
        self.assertContains(detail, "First day")
        self.assertContains(detail, "arrival.jpg")
        self.assertContains(detail, "First morning")

    def test_admin_can_create_user_and_role(self):
        self.client.force_login(self.admin)
        user_response = self.client.post(
            reverse("admin_users"),
            {
                "action": "create",
                "username": "new-member",
                "first_name": "New",
                "last_name": "Member",
                "password": "DifferentSecure!2026",
                "roles": [Group.objects.get(name="USER").pk],
            },
        )
        self.assertRedirects(user_response, reverse("admin_users"))
        self.assertTrue(User.objects.get(username="new-member").groups.filter(name="USER").exists())

        role_response = self.client.post(
            reverse("admin_roles"),
            {"action": "create", "name": "TRAVEL"},
        )
        self.assertRedirects(role_response, reverse("admin_roles"))
        self.assertTrue(Group.objects.filter(name="TRAVEL").exists())
