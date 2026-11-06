import unittest

from justdownload.core.filename import safe_stem, with_extension
from justdownload.core.url_guard import URLRejected, validate_url


class FilenameTests(unittest.TestCase):
    def test_removes_path_and_reserved_characters(self):
        self.assertEqual(safe_stem(r"../CON:bad/name?"), "_CON_bad_name_")

    def test_windows_reserved_device_name(self):
        self.assertEqual(safe_stem("NUL"), "_NUL")

    def test_extension_is_normalized(self):
        self.assertEqual(with_extension("My Video.webm", ".MP3"), "My Video.mp3")


class URLGuardTests(unittest.TestCase):
    def test_rejects_non_http_schemes(self):
        with self.assertRaises(URLRejected):
            validate_url("file:///etc/passwd")

    def test_rejects_loopback_literal(self):
        with self.assertRaises(URLRejected):
            validate_url("http://127.0.0.1/media.mp4")

    def test_rejects_private_ipv6(self):
        with self.assertRaises(URLRejected):
            validate_url("http://[::1]/media.mp4")

    def test_rejects_embedded_credentials(self):
        with self.assertRaises(URLRejected):
            validate_url("https://user:pass@example.com/video.mp4")

    def test_rejects_non_standard_port(self):
        with self.assertRaises(URLRejected):
            validate_url("https://example.com:8443/video.mp4")


if __name__ == "__main__":
    unittest.main()
