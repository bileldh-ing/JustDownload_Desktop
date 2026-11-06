import unittest
from unittest.mock import patch

from justdownload.media.remote import RemoteMediaError, inspect_remote


class FakeResponse:
    def __init__(self, status, headers, url):
        self.status = status
        self.headers = headers
        self._url = url
        self.closed = False

    def getcode(self):
        return self.status

    def geturl(self):
        return self._url

    def read(self, _amount=-1):
        return b"x"

    def close(self):
        self.closed = True


class RemoteInspectionTests(unittest.TestCase):
    @patch("justdownload.media.remote.validate_url", side_effect=lambda value: value)
    @patch("justdownload.media.remote._request")
    def test_range_inspection_reads_total_size_and_sanitizes_filename(self, request, _validate):
        head = FakeResponse(405, {}, "https://media.example/clip.mp4")
        ranged = FakeResponse(206, {
            "Content-Type": "video/mp4",
            "Content-Length": "1",
            "Content-Range": "bytes 0-0/123456",
        }, "https://media.example/folder/clip%5Cbad.mp4")
        request.side_effect = [head, ranged]
        result = inspect_remote("https://media.example/folder/clip.mp4")
        self.assertEqual(result.size_bytes, 123456)
        self.assertEqual(result.media_kind, "video")
        self.assertEqual(result.filename, "bad.mp4")
        self.assertIn("verified after acquisition", result.status)

    @patch("justdownload.media.remote.validate_url", side_effect=lambda value: value)
    @patch("justdownload.media.remote._request")
    def test_executable_extension_is_not_reused_for_media_output(self, request, _validate):
        response = FakeResponse(200, {"Content-Type": "video/mp4", "Content-Length": "100"}, "https://media.example/download.exe")
        request.return_value = response
        result = inspect_remote("https://media.example/download.exe")
        self.assertEqual(result.filename, "download.mp4")

    @patch("justdownload.media.remote.validate_url", side_effect=lambda value: value)
    @patch("justdownload.media.remote._request")
    def test_html_page_is_not_accepted_even_with_media_extension(self, request, _validate):
        request.return_value = FakeResponse(200, {"Content-Type": "text/html", "Content-Length": "100"}, "https://media.example/watch.mp4")
        with self.assertRaises(RemoteMediaError):
            inspect_remote("https://media.example/watch.mp4")


if __name__ == "__main__":
    unittest.main()
