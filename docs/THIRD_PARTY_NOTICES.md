# Third-party notices

## Python

The application uses Python standard-library modules at runtime, including Tkinter/Tcl-Tk, `urllib`, `subprocess`, `threading`, `queue`, `pathlib`, `hashlib` and `json`. Review the Python distribution's bundled license notices for the exact runtime being shipped.

## FFmpeg / FFprobe

FFmpeg and FFprobe are external runtime dependencies by default and are not redistributed in this source archive. If an operator adds binaries to `vendor/ffmpeg/`, they must document the exact build, version, configure flags and license (LGPL or GPL depending on enabled components and build options), and comply with applicable redistribution obligations.

## PyInstaller

PyInstaller is an optional build-time dependency pinned in `requirements.txt` and is not required to run from source. Review its license and bundled bootloader notices when distributing a packaged application.

No third-party media extractor is included.
