# Security notes

## Included controls

- Only HTTP and HTTPS schemes are accepted for remote sources.
- URLs with embedded credentials, localhost suffixes, non-standard ports, or private/non-public DNS destinations are rejected.
- Every redirect destination is passed through the URL validator before being followed.
- Desktop proxy environment settings are not used by the URL fetcher.
- Remote download size is bounded by `JUSTDOWNLOAD_MAX_REMOTE_BYTES` (2 GiB by default).
- Redirect and response content type are checked; the downloaded file is subsequently parsed by FFprobe.
- FFmpeg and FFprobe are invoked with argument arrays and without shell command construction.
- Output filenames are normalized and sanitized; output collisions receive a numeric suffix.
- Each job gets a separate temporary workspace that is removed after success, failure or cancellation.
- The final artifact is checked with FFprobe and moved into the output directory only after validation.
- No third-party passwords, cookies, browser sessions, private tokens or platform credentials are collected.

## Important limitations

This is a desktop client, not a network-isolated worker sandbox. DNS is resolved and checked before requests, but the client does not pin a socket to the checked address; DNS rebinding protection is therefore not equivalent to an egress firewall. A redirect handler validates each target, but users operating in managed/untrusted environments should also apply OS-level egress rules and keep FFmpeg updated.

## Not implemented

- DRM decryption, paywall bypass, authentication automation, browser-cookie import, private-account access, signature circumvention, anti-bot evasion or unrestricted website scraping.
- Multi-user tenancy, remote public API, or cloud storage.

## Recommended release checks

- Run the app under a standard non-admin user account.
- Use Windows Defender Firewall or equivalent egress controls where appropriate.
- Keep FFmpeg/FFprobe builds patched and validate their provenance/licensing.
- Run dependency and static-analysis scans before release.
- Review the behavior with a qualified security engineer before public deployment.
