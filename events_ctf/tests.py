from django.test import TestCase
from django.templatetags.static import static
from django.urls import resolve
from django.conf import settings
import os


class StaticImageTest(TestCase):
    def test_static_logo_path_exists(self):
        """
        Ensure the favicon/logo image exists in STATIC_ROOT / STATICFILES_DIRS
        """
        static_path = os.path.join(settings.STATIC_ROOT, 'images', 'logo.ico')
        self.assertTrue(
            os.path.exists(static_path),
            f"Static image not found at {static_path}"
        )

    def test_static_logo_url(self):
        """
        Ensure Django generates the correct static URL for favicon/logo
        """
        url = static('images/logo.png')
        self.assertEqual(url, '/static/images/logo.jpeg')

    def test_static_logo_http_response(self):
        """
        Ensure favicon/logo is accessible via HTTP
        NOTE: Works only if static serving is enabled (DEBUG=True or nginx)
        """
        response = self.client.get('/static/images/logo.jpeg')
        self.assertIn(response.status_code, [200, 304])
