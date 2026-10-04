from django.core import mail
from django.test import TestCase, override_settings
from django.urls import reverse


class StorefrontTests(TestCase):
    def test_home_page_renders_products_and_enquiry_form(self):
        response = self.client.get(reverse("home"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "A GOOD DAY STARTS HERE")
        self.assertContains(response, "The baker's box")
        self.assertContains(response, 'name="email"')

    @override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
    def test_valid_enquiry_sends_email_and_redirects(self):
        response = self.client.post(
            reverse("home"),
            {
                "name": "Alex Farmer",
                "email": "alex@example.com",
                "quantity": "12 eggs",
                "message": "Could I collect a dozen on Saturday?",
            },
        )

        self.assertRedirects(response, reverse("home"))
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].reply_to, ["alex@example.com"])
        self.assertIn("12 eggs", mail.outbox[0].body)
