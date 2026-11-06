import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from justdownload.media.pipeline import JobRequest, process_job
from justdownload.media.probe import probe_media


@unittest.skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe"), "FFmpeg/FFprobe are required")
class PipelineIntegrationTests(unittest.TestCase):
    def test_real_wav_to_mp3_conversion_and_validation(self):
        with tempfile.TemporaryDirectory(prefix="jd-test-") as temp:
            root = Path(temp)
            source = root / "fixture.wav"
            output = root / "out"
            generated = subprocess.run([
                shutil.which("ffmpeg"), "-hide_banner", "-loglevel", "error", "-y",
                "-f", "lavfi", "-i", "sine=frequency=440:duration=1",
                "-c:a", "pcm_s16le", str(source),
            ], capture_output=True, text=True, timeout=30)
            self.assertEqual(generated.returncode, 0, generated.stderr)
            info = probe_media(source)
            self.assertTrue(info.has_audio)
            events = []
            request = JobRequest("local", str(source), None, "mp3", output, "converted")
            result = process_job(request, __import__("threading").Event(), events.append, "test-job")
            self.assertTrue(result.path.is_file())
            self.assertGreater(result.size_bytes, 0)
            self.assertEqual(result.media.audio_codec, "mp3")
            self.assertEqual(events[-1].state, "ready")
            self.assertEqual(len(result.sha256), 64)

    def test_real_video_to_mp4_h264_conversion_and_validation(self):
        with tempfile.TemporaryDirectory(prefix="jd-video-test-") as temp:
            root = Path(temp)
            source = root / "fixture.mp4"
            output = root / "out"
            generated = subprocess.run([
                shutil.which("ffmpeg"), "-hide_banner", "-loglevel", "error", "-y",
                "-f", "lavfi", "-i", "color=c=navy:s=320x240:r=24:d=1",
                "-f", "lavfi", "-i", "sine=frequency=880:duration=1",
                "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", "-shortest", str(source),
            ], capture_output=True, text=True, timeout=30)
            self.assertEqual(generated.returncode, 0, generated.stderr)
            info = probe_media(source)
            self.assertTrue(info.has_video)
            events = []
            request = JobRequest("local", str(source), None, "mp4", output, "video-result")
            result = process_job(request, __import__("threading").Event(), events.append, "video-test-job")
            self.assertTrue(result.path.is_file())
            self.assertGreater(result.size_bytes, 0)
            self.assertEqual(result.media.video_codec, "h264")
            self.assertEqual(events[-1].state, "ready")


if __name__ == "__main__":
    unittest.main()
