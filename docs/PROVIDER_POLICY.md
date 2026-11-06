# Provider and source policy

| Source type | Capability | Behavior |
|---|---|---|
| Local media file | `authorized_download` is not applicable; local conversion | Full FFprobe inspection and local conversion |
| Direct HTTP(S) media file | `authorized_download` only for files the user is authorized to retrieve | Header inspection, bounded direct fetch, FFprobe and conversion |
| Generic website page | `disabled` | Explain that a direct media file URL is required |
| YouTube, Facebook, TikTok and other platform pages | `disabled` by default | No page scraping or media extraction; use the platform's official download/export flow where available |
| DRM, paywalled, private or login-protected content | `disabled` | Reject; no bypass feature |

This build contains no platform-specific extractor adapters. Provider support must not be inferred from the presence of a media-looking URL. Only direct media file responses are accepted. Content type and file extension are preliminary indicators; FFprobe is the final stream-level inspection.

If platform integrations are considered in a later release, each needs documented API/terms permission, a server/application-side capability decision, an owner, a verification date, a support boundary and regression tests. A user checkbox alone does not enable a restricted provider.
